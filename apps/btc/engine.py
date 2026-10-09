"""Causal BTC research engine: local Laya signals and auditable spot paper accounts.

All decisions, fills and animation events originate in SQLite.  No exchange
order is submitted.  The old Pulse JSONL paper account is deliberately not
loaded into this database.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
import time
from pathlib import Path

import pulse

try:
    from . import paper_engine
except ImportError:  # imported with apps/btc on sys.path by workbench.py
    import paper_engine


ROOT = Path(__file__).resolve().parents[2]
from runtime_config import DATA_DIR, MODEL_ID, MODEL_REVISION
DB_PATH = DATA_DIR / "btc_system.sqlite3"

PERIOD = 5
CAPITAL = 10_000.0
BASE_SPEC = {
    "schema": "btc-strategy-v1", "name": "exploration-v0", "model": MODEL_ID,
    "checkpoint_revision": MODEL_REVISION,
    "signal_interval_s": 5, "portfolio_interval_s": 30,
    "signal_lookback_s": 60, "threshold_higher_of_six": 4,
    "threshold_lower_of_six": 2, "target_weight_max": .05,
    "order_equity_max": .01, "cooldown_s": 120, "daily_orders_max": 24,
    "daily_turnover_max": .50, "daily_fee_max": .002,
    "daily_loss_stop": .01, "fee_bps": 80.0, "slippage_bps": 2.0,
    "signal_rule_bps_15s": 1.5,
    "prompt_hash": hashlib.sha256(b"btc-5s-v0-price-path-v1-structured-momentum-v1").hexdigest(),
    "feature_code_hash": hashlib.sha256(Path(pulse.__file__).read_bytes()).hexdigest(),
    "execution_code_hash": hashlib.sha256(Path(paper_engine.__file__).read_bytes()).hexdigest(),
    "engine_code_hash": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "teacher": "ChatGPT assisted this research session; no runtime OpenAI API is connected",
}
CANDIDATE_SPEC = {**BASE_SPEC, "name": "shadow-conservative-v1",
                  "threshold_higher_of_six": 5, "threshold_lower_of_six": 1}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def dumps(value):
    return canonical(value)


def loads(value, fallback=None):
    if value is None:
        return fallback
    return json.loads(value)


def account_initial():
    return {"cash": CAPITAL, "btc": 0.0, "basis": 0.0,
            "realized": 0.0, "fees": 0.0, "trades": 0,
            "buys": 0, "sells": 0, "last_fill_at": None,
            "day_orders": 0, "day_turnover": 0.0, "day_fees": 0.0,
            "day_start_equity": CAPITAL, "mark_price": None,
            "mark_at": None, "equity": CAPITAL, "pnl": 0.0,
            "filled_order_ids": []}


def finite_number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


class BTCSystem:
    def __init__(self, cache, db_path=DB_PATH, clock=None):
        self.cache = cache
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or time
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None, timeout=.5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=500")
        self.db.execute("PRAGMA synchronous=FULL")
        self._init_schema()
        self.manifest = BASE_SPEC
        self.manifest_hash = digest(BASE_SPEC)
        self.model_error = None
        self.paused_reason = None
        self.last_wall = self.clock.time()
        self.last_mono = self.clock.monotonic()
        self.last_trades_poll = 0.0
        self.last_book_poll = 0.0
        self.ready_after = self.clock.time() + 60
        self.last_mark_at = 0.0
        self.last_mark_attempt_at = 0.0
        self.last_candidate_at = 0.0
        self._recover_and_register()

    def _init_schema(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(
          seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL,
          kind TEXT NOT NULL, round_id INTEGER, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS events_at_idx ON events(at);
        CREATE TABLE IF NOT EXISTS trades(
          trade_id TEXT PRIMARY KEY, event_time REAL NOT NULL,
          received_at REAL NOT NULL, price REAL NOT NULL,
          volume REAL NOT NULL, side TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS trades_event_idx ON trades(event_time);
        CREATE INDEX IF NOT EXISTS trades_received_idx ON trades(received_at);
        CREATE TABLE IF NOT EXISTS snapshots(
          snapshot_id TEXT PRIMARY KEY, round_start INTEGER UNIQUE NOT NULL,
          frozen_at REAL NOT NULL, market_json TEXT NOT NULL,
          manifest_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rounds(
          start INTEGER PRIMARY KEY, end INTEGER NOT NULL, status TEXT NOT NULL,
          snapshot_id TEXT, frozen_at REAL, locked_at REAL,
          baseline_json TEXT, optimized_json TEXT, candidate_json TEXT,
          truth TEXT, move_bps REAL, label_tier TEXT,
          p0_json TEXT, p1_json TEXT, reason TEXT,
          manifest_hash TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS rounds_status_idx ON rounds(status,start);
        CREATE TABLE IF NOT EXISTS evaluations(
          at INTEGER PRIMARY KEY, status TEXT NOT NULL,
          baseline_json TEXT, optimized_json TEXT,
          candidate_json TEXT, reason TEXT, manifest_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS orders(
          order_id TEXT PRIMARY KEY, eval_at INTEGER NOT NULL,
          account_key TEXT NOT NULL, intent_at REAL NOT NULL,
          side TEXT NOT NULL, status TEXT NOT NULL,
          intent_json TEXT NOT NULL, reason TEXT, fill_id TEXT);
        CREATE INDEX IF NOT EXISTS orders_eval_idx ON orders(eval_at);
        CREATE TABLE IF NOT EXISTS fills(
          fill_id TEXT PRIMARY KEY, order_id TEXT NOT NULL UNIQUE,
          account_key TEXT NOT NULL, filled_at REAL NOT NULL,
          fill_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS accounts(
          account_key TEXT PRIMARY KEY, state_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS marks(
          at REAL PRIMARY KEY, price REAL NOT NULL,
          baseline REAL NOT NULL, optimized REAL NOT NULL,
          buy_hold REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS candidates(
          candidate_id TEXT PRIMARY KEY, created_at REAL NOT NULL,
          status TEXT NOT NULL, proposer TEXT NOT NULL,
          parent_hash TEXT NOT NULL, spec_hash TEXT NOT NULL,
          spec_json TEXT NOT NULL, visible_data_end REAL NOT NULL,
          forward_start REAL NOT NULL, forward_end REAL NOT NULL,
          attempts_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS shadow_signals(
          candidate_id TEXT NOT NULL, round_start INTEGER NOT NULL,
          choice TEXT NOT NULL, truth TEXT,
          PRIMARY KEY(candidate_id,round_start));
        CREATE TABLE IF NOT EXISTS depth_probes(
          eval_at INTEGER PRIMARY KEY, requested_at REAL NOT NULL,
          received_at REAL, valid_time INTEGER NOT NULL, reason TEXT NOT NULL,
          best_bid REAL, best_ask REAL);
        CREATE TABLE IF NOT EXISTS qualified_policy_evaluations(
          at INTEGER PRIMARY KEY, manifest_hash TEXT NOT NULL,
          status TEXT NOT NULL, reason TEXT NOT NULL,
          locked_signals INTEGER NOT NULL, window_start INTEGER NOT NULL,
          window_end INTEGER NOT NULL, spec_json TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS warmup_intervals(
          start REAL PRIMARY KEY, end REAL NOT NULL, reason TEXT NOT NULL);
        """)

    def _tx(self, work):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                result = work(self.db)
                self.db.commit()
                return result
            except BaseException:
                self.db.rollback()
                raise

    def _event(self, db, kind, round_id=None, **payload):
        db.execute("INSERT INTO events(at,kind,round_id,payload) VALUES(?,?,?,?)",
                   (self.clock.time(), kind, round_id, dumps(payload)))

    def _recover_and_register(self):
        now = self.clock.time()
        def write(db):
            row = db.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
            if row and row[0] != "1":
                raise RuntimeError("Unsupported BTC database schema")
            db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
            for key in ("baseline", "optimized"):
                db.execute("INSERT OR IGNORE INTO accounts(account_key,state_json) VALUES(?,?)",
                           (key, dumps(account_initial())))
            # Earlier paper_engine versions recorded each durable fill but did
            # not increment the direction counters. Rebuild only those two
            # derived fields from the immutable fill/order ledger. Repeating
            # recovery is idempotent and cannot change cash, BTC or P&L.
            fill_counts = {}
            for counted in db.execute(
                "SELECT f.account_key,"
                "SUM(CASE WHEN o.side='buy' THEN 1 ELSE 0 END),"
                "SUM(CASE WHEN o.side='sell' THEN 1 ELSE 0 END),"
                "SUM(CASE WHEN o.side NOT IN ('buy','sell') OR o.side IS NULL THEN 1 ELSE 0 END) "
                "FROM fills f LEFT JOIN orders o ON o.order_id=f.order_id "
                "GROUP BY f.account_key").fetchall():
                fill_counts[counted[0]] = (counted[1] or 0, counted[2] or 0, counted[3] or 0)
            for account_row in db.execute("SELECT account_key,state_json FROM accounts").fetchall():
                key, account = account_row[0], loads(account_row[1])
                buys, sells, unknown = fill_counts.get(key, (0, 0, 0))
                if unknown:
                    self._event(db, "account_count_reconcile_skipped", None,
                                account=key, unknown_fill_sides=unknown)
                    continue
                before = {"buys": account.get("buys", 0), "sells": account.get("sells", 0)}
                if before != {"buys": buys, "sells": sells}:
                    account.update(buys=buys, sells=sells)
                    db.execute("UPDATE accounts SET state_json=? WHERE account_key=?",
                               (dumps(account), key))
                    self._event(db, "account_counts_reconciled", None,
                                account=key, before=before, after={"buys": buys, "sells": sells})
            db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('active_manifest',?)",
                       (dumps(BASE_SPEC),))
            db.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('manifest_activated_at',?)",
                       (str(now),))
            row = db.execute("SELECT value FROM meta WHERE key='active_manifest'").fetchone()
            stored = loads(row[0])
            if digest(stored) != self.manifest_hash:
                if stored.get("model") != BASE_SPEC["model"] or stored.get("checkpoint_revision") != BASE_SPEC["checkpoint_revision"]:
                    raise RuntimeError("Frozen model revision differs from current local checkpoint")
                # A software upgrade starts a new cohort; prior rounds retain
                # their manifest hashes rather than being relabelled.
                self.manifest = {**stored, **{k: BASE_SPEC[k] for k in
                                 ("checkpoint_revision", "prompt_hash", "feature_code_hash",
                                  "execution_code_hash", "engine_code_hash")}}
                self.manifest_hash = digest(self.manifest)
                db.execute("UPDATE meta SET value=? WHERE key='active_manifest'", (dumps(self.manifest),))
                db.execute("UPDATE meta SET value=? WHERE key='manifest_activated_at'", (str(now),))
                self._event(db, "manifest_upgrade", None, previous_hash=digest(stored),
                            current_hash=self.manifest_hash)
            else:
                self.manifest = stored
                self.manifest_hash = digest(stored)
            self.manifest_activated_at = float(db.execute(
                "SELECT value FROM meta WHERE key='manifest_activated_at'").fetchone()[0])
            db.execute("INSERT OR IGNORE INTO warmup_intervals VALUES(?,?,?)",
                       (now, self.ready_after, "service_start_or_restart"))
            # A crash cannot turn a stale partial prediction into a live lock.
            for old in db.execute("SELECT start FROM rounds WHERE status IN ('frozen','partial')").fetchall():
                db.execute("UPDATE rounds SET status='missed',reason='restart_before_pair_lock' WHERE start=?",
                           (old[0],))
                self._event(db, "missed", old[0], reason="restart_before_pair_lock")
        self._tx(write)

    def _ingest(self):
        with self.cache.lock:
            raw = list(self.cache.trades or [])
            poll_at = float(self.cache.times.get("trades", 0))
        if poll_at <= self.last_trades_poll:
            return
        if self.last_trades_poll and poll_at - self.last_trades_poll > 7:
            self.ready_after = poll_at + 60
            self.paused_reason = "trade_poll_gap"
            self._tx(lambda db: db.execute("INSERT OR IGNORE INTO warmup_intervals VALUES(?,?,?)",
                                           (poll_at, self.ready_after, "trade_poll_gap")))
        self.last_trades_poll = poll_at
        parsed = pulse.parse_trades(raw)
        new = []
        def write(db):
            previous = db.execute("SELECT value FROM meta WHERE key='last_trade_batch_ids'").fetchone()
            current_ids = {x["id"] for x in parsed}
            if previous and not current_ids.intersection(loads(previous[0], [])):
                self.paused_reason = "possible_cursor_gap"
                self.ready_after = poll_at + 60
                db.execute("INSERT OR IGNORE INTO warmup_intervals VALUES(?,?,?)",
                           (poll_at, self.ready_after, "possible_cursor_gap"))
                self._event(db, "source_gap", None, reason="possible_cursor_gap", received_at=poll_at)
            db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('last_trade_batch_ids',?)",
                       (dumps([x["id"] for x in parsed[-80:]]),))
            for x in parsed:
                if not (poll_at - 90 <= x["time"] <= poll_at + 1):
                    continue
                if not all(finite_number(x[k]) for k in ("price", "volume", "time")) or x["price"] <= 0:
                    continue
                changed = db.execute("INSERT OR IGNORE INTO trades VALUES(?,?,?,?,?,?)",
                                     (x["id"], x["time"], poll_at, x["price"], x["volume"], x["side"]))
                if changed.rowcount:
                    new.append(x)
            if new:
                last = new[-1]
                self._event(db, "new_trade_received", None, count=len(new),
                            last_price=last["price"], last_trade_at=last["time"],
                            received_at=poll_at, trade_id=last["id"])
            else:
                self._event(db, "poll_heartbeat", None, source="trades", received_at=poll_at)
        self._tx(write)

    def _available_trades(self, cutoff):
        with self.lock:
            rows = self.db.execute(
                "SELECT trade_id,event_time,received_at,price,volume,side FROM trades "
                "WHERE received_at<=? AND event_time<=? AND event_time>=? ORDER BY event_time",
                (cutoff, cutoff, cutoff - 95)).fetchall()
        return [{"id": r[0], "time": r[1], "received_at": r[2], "price": r[3],
                 "volume": r[4], "side": r[5]} for r in rows]

    def _predict_one(self, lane, f):
        pts = ", ".join(f"{p:.1f}" for p in f["points"])
        if lane == "baseline":
            state = (f"BTC/USD Kraken spot trade prices at 60,45,30,20,15,10,5,0 seconds ago: {pts}. "
                     f"Last 30 seconds: {f['trade_count_30s']} trades, buyer share "
                     f"{f['buy_share_30s']:.1%}.")
            instructions = "Will BTC/USD be higher or lower in the next five seconds? Pick a direction."
        else:
            state = (f"BTC/USD spot USD {f['price']:.2f}; returns bps 5s {f['mom_5s_bps']:+.2f}, "
                     f"15s {f['mom_15s_bps']:+.2f}, 30s {f['mom_30s_bps']:+.2f}, "
                     f"60s {f['mom_60s_bps']:+.2f}; aggressive buyer share "
                     f"{f['buy_share_30s']:.1%}; {f['trade_count_30s']} trades in 30s. "
                     "Noisy microstructure signal, not a profit forecast.")
            instructions = "Choose higher or lower for the next five-second BTC/USD spot return."
        question = {"direction": {"type": "choice", "instructions": instructions,
                                  "criteria": ["higher", "lower"]}}
        with pulse.MODEL_LOCK:
            agent = pulse.get_agent()
            started = self.clock.monotonic()
            raw = agent.predict(state, question)
            elapsed_ms = (self.clock.monotonic() - started) * 1000
        answer = raw["answers"]["direction"]
        choice = answer["choice"]
        probs = answer.get("probabilities") or {}
        if choice not in ("higher", "lower"):
            raise ValueError("Laya returned invalid direction")
        if any(not finite_number(v) for v in probs.values()):
            raise ValueError("Laya returned invalid probability")
        result = {"choice": choice, "probabilities": probs,
                  "confidence": answer.get("confidence"),
                  "model_ms": round(elapsed_ms, 2), "state": state,
                  "model_choice": choice, "route": "laya"}
        if lane == "optimized" and abs(f["mom_15s_bps"]) >= self.manifest["signal_rule_bps_15s"]:
            result["choice"] = "higher" if f["mom_15s_bps"] > 0 else "lower"
            result["route"] = "15s_momentum_rule"
        return result

    def _freeze_predict(self, start):
        now = self.clock.time()
        if now < self.ready_after or now - self.last_trades_poll > 3.5:
            return
        trades = self._available_trades(now)
        f = pulse.features(trades, now)
        if not f:
            return
        snapshot = {"features": f, "trade_ids": [x["id"] for x in trades],
                    "received_cutoff": now, "latest_received_at": max(x["received_at"] for x in trades)}
        snapshot_id = digest(snapshot)
        def freeze(db):
            if db.execute("SELECT 1 FROM rounds WHERE start=?", (start,)).fetchone():
                return False
            db.execute("INSERT INTO snapshots VALUES(?,?,?,?,?)",
                       (snapshot_id, start, now, dumps(snapshot), self.manifest_hash))
            db.execute("INSERT INTO rounds(start,end,status,snapshot_id,frozen_at,manifest_hash) "
                       "VALUES(?,?,?,?,?,?)",
                       (start, start + PERIOD, "frozen", snapshot_id, now, self.manifest_hash))
            self._event(db, "snapshot_frozen", start, snapshot_id=snapshot_id,
                        price=f["price"], received_cutoff=now)
            return True
        if not self._tx(freeze):
            return
        order = ("baseline", "optimized") if start // PERIOD % 2 == 0 else ("optimized", "baseline")
        for lane in order:
            if self.clock.time() >= start:
                break
            try:
                result = self._predict_one(lane, f)
                self.model_error = None
            except Exception as exc:
                self.model_error = str(exc)
                self._tx(lambda db: self._event(db, "model_error", start, lane=lane, message=str(exc)))
                break
            def save_result(db):
                col = "baseline_json" if lane == "baseline" else "optimized_json"
                db.execute(f"UPDATE rounds SET {col}=?,status='partial' WHERE start=? AND status IN ('frozen','partial')",
                           (dumps(result), start))
                self._event(db, "baseline_model_done" if lane == "baseline" else "candidate_model_done",
                            start, lane=lane, choice=result["choice"], raw_choice=result["model_choice"],
                            route=result["route"], model_ms=result["model_ms"])
            self._tx(save_result)
        # Commit completion, rather than model return, determines the lock deadline.
        if self.clock.time() < start:
            def lock_pair(db):
                row = db.execute("SELECT baseline_json,optimized_json,status FROM rounds WHERE start=?", (start,)).fetchone()
                if row and row[0] and row[1] and row[2] == "partial":
                    db.execute("UPDATE rounds SET status='locked',locked_at=? WHERE start=?", (self.clock.time(), start))
                    self._event(db, "decision_locked", start, snapshot_id=snapshot_id,
                                baseline=loads(row[0])["choice"], optimized=loads(row[1])["choice"])
                    candidate = db.execute("SELECT candidate_id,spec_json,forward_start,forward_end FROM candidates "
                                           "WHERE status='frozen_shadow' ORDER BY created_at DESC LIMIT 1").fetchone()
                    if candidate and candidate[2] <= start < candidate[3]:
                        spec = loads(candidate[1])
                        choice = self._candidate_choice(loads(row[1]), f, spec)
                        db.execute("UPDATE rounds SET candidate_json=? WHERE start=?",
                                   (dumps({"candidate_id": candidate[0], "choice": choice,
                                           "spec_hash": digest(spec)}), start))
                        db.execute("INSERT OR IGNORE INTO shadow_signals VALUES(?,?,?,NULL)",
                                   (candidate[0], start, choice))
                        self._event(db, "shadow_candidate_decision", start,
                                    candidate_id=candidate[0], choice=choice)
                    return True
                return False
            paired = self._tx(lock_pair)
            if paired and self.clock.time() >= start:
                self._tx(lambda db: (db.execute("UPDATE rounds SET status='missed',reason='late_commit' WHERE start=?", (start,)),
                                     self._event(db, "missed", start, reason="late_commit")))

    def _mark_missed(self, start):
        def write(db):
            row = db.execute("SELECT status FROM rounds WHERE start=?", (start,)).fetchone()
            if row and row[0] in ("locked", "settled", "tie", "void", "missed"):
                return
            if row:
                db.execute("UPDATE rounds SET status='missed',reason='not_locked_before_start' WHERE start=?", (start,))
            else:
                db.execute("INSERT INTO rounds(start,end,status,reason,manifest_hash) VALUES(?,?,?,?,?)",
                           (start, start + PERIOD, "missed", "no_qualified_snapshot", self.manifest_hash))
            self._event(db, "missed", start, reason="not_locked_before_start" if row else "no_qualified_snapshot")
        self._tx(write)

    def _settle(self):
        now = self.clock.time()
        with self.lock:
            pending = self.db.execute("SELECT start,end,baseline_json,optimized_json FROM rounds "
                                      "WHERE status='locked' AND end+8<? ORDER BY start LIMIT 20", (now,)).fetchall()
        for row in pending:
            start, end = row[0], row[1]
            if self.last_trades_poll < end + 2:
                # Do not finalize a label from a feed snapshot taken before
                # the round ended. Recovery can settle it once a later poll lands.
                continue
            with self.lock:
                source = self.db.execute("SELECT event_time,price,received_at FROM trades "
                                         "WHERE event_time>=? AND event_time<=? ORDER BY event_time",
                                         (start - 10, end)).fetchall()
            before = [x for x in source if x[0] <= start]
            after = [x for x in source if x[0] <= end]
            intra = [x for x in source if start < x[0] <= end]
            p0, p1 = before[-1] if before else None, after[-1] if after else None
            tier = None
            truth = None
            reason = None
            move_bps = None
            if not p0 or not p1 or not intra or start - p0[0] > 10 or end - p1[0] > 10:
                status, reason = "void", "missing_boundary_trade"
            else:
                move_bps = round((p1[1] / p0[1] - 1) * 10_000, 4)
                status = "tie" if p1[1] == p0[1] else "settled"
                truth = "higher" if p1[1] > p0[1] else "lower" if p1[1] < p0[1] else "tie"
                tier = "primary" if start - p0[0] <= 2 and end - p1[0] <= 2 else "reference"
            def write(db):
                changed = db.execute("UPDATE rounds SET status=?,truth=?,move_bps=?,label_tier=?,"
                                     "p0_json=?,p1_json=?,reason=? WHERE start=? AND status='locked'",
                                     (status, truth, move_bps, tier,
                                      dumps(dict(p0)) if p0 else None, dumps(dict(p1)) if p1 else None,
                                      reason, start))
                if not changed.rowcount:
                    return
                self._event(db, status, start, truth=truth, move_bps=move_bps,
                            label_tier=tier, reason=reason)
                db.execute("UPDATE shadow_signals SET truth=? WHERE round_start=?",
                           (truth, start))
            self._tx(write)

    def _candidate_choice(self, optimized, features, spec):
        # Candidate only routes an already frozen Laya result; no third model call.
        momentum = features["mom_15s_bps"]
        if abs(momentum) >= spec["signal_rule_bps_15s"]:
            return "higher" if momentum >= 0 else "lower"
        return optimized["model_choice"]

    def _maybe_generate_candidate(self):
        with self.lock:
            active = self.db.execute("SELECT status,forward_end FROM candidates ORDER BY created_at DESC LIMIT 1").fetchone()
            if active and (active[0] == "frozen_shadow" or self.clock.time() <= active[1]):
                return
            training = self.db.execute(
                "SELECT r.start,r.end,r.truth,r.optimized_json,s.market_json "
                "FROM rounds r JOIN snapshots s ON s.round_start=r.start "
                "WHERE r.status='settled' AND r.label_tier='primary' "
                "AND r.manifest_hash=? ORDER BY r.start DESC LIMIT 160",
                (self.manifest_hash,)).fetchall()
        if len(training) < 40:
            return
        training = list(reversed(training))
        attempts = []
        for threshold in (0.0, 0.6, 3.0, 5.0):
            spec = {**self.manifest, "signal_rule_bps_15s": threshold}
            wins = 0
            for row in training:
                features = loads(row[4])["features"]
                choice = self._candidate_choice(loads(row[3]), features, spec)
                wins += choice == row[2]
            attempts.append({"threshold_bps": threshold, "wins": wins,
                             "rounds": len(training), "accuracy": round(wins / len(training), 4)})
        selected = sorted(attempts, key=lambda x: (-x["accuracy"], x["threshold_bps"]))[0]
        now = self.clock.time()
        spec = {**self.manifest, "name": "local-grid-shadow",
                "signal_rule_bps_15s": selected["threshold_bps"],
                "source_window_start": training[0][0],
                "source_window_end": training[-1][1],
                "teacher": "local grid on settled training rows; runtime OpenAI teacher not connected"}
        spec_hash = digest(spec)
        candidate_id = "local-grid-" + spec_hash[:12]
        forward_start = int(math.ceil(max(now + .001, training[-1][1] + 60) / PERIOD) * PERIOD)
        def write(db):
            active = db.execute("SELECT status,forward_end FROM candidates ORDER BY created_at DESC LIMIT 1").fetchone()
            if active and (active[0] == "frozen_shadow" or now <= active[1]):
                return
            inserted = db.execute("INSERT OR IGNORE INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                                  (candidate_id, now, "frozen_shadow", "local_grid",
                                   self.manifest_hash, spec_hash, dumps(spec), training[-1][1],
                                   forward_start, forward_start + 7 * 86400, dumps(attempts)))
            if not inserted.rowcount:
                return
            self._event(db, "candidate_frozen", None, candidate_id=candidate_id,
                        spec_hash=spec_hash, parent_hash=self.manifest_hash,
                        training_rounds=len(training), forward_start=forward_start,
                        forward_end=forward_start + 7 * 86400,
                        note="exploratory training selected; no forward result yet")
        self._tx(write)

    def _candidate_progress(self):
        with self.lock:
            candidate = self.db.execute("SELECT candidate_id,status,forward_start,forward_end FROM candidates "
                                        "ORDER BY created_at DESC LIMIT 1").fetchone()
        if not candidate or candidate[1] != "frozen_shadow" or self.clock.time() < candidate[3]:
            return
        with self.lock:
            rows = self.db.execute(
                "SELECT s.round_start,s.choice,s.truth,r.optimized_json "
                "FROM shadow_signals s JOIN rounds r ON r.start=s.round_start "
                "WHERE s.candidate_id=? AND s.round_start>=? AND s.round_start<? "
                "ORDER BY s.round_start", (candidate[0], candidate[2], candidate[3])).fetchall()
            total = self.db.execute("SELECT count(*) FROM rounds WHERE start>=? AND start<?",
                                    (candidate[2], candidate[3])).fetchone()[0]
        valid = [r for r in rows if r[2] in ("higher", "lower")]
        coverage = len(rows) / total if total else 0
        if len(valid) < 5000 or coverage < .8:
            result, reason = "rejected", "insufficient_forward_samples_or_coverage"
        else:
            candidate_wins = sum(r[1] == r[2] for r in valid)
            incumbent_wins = sum(loads(r[3])["choice"] == r[2] for r in valid)
            always_high = sum(r[2] == "higher" for r in valid)
            always_low = len(valid) - always_high
            gain = (candidate_wins - incumbent_wins) / len(valid)
            # One-hour block bootstrap of three paired comparisons, using the
            # same fixed resamples and no repeated interim significance peek.
            blocks = {}
            for r in valid:
                key = int(r[0] // 3600)
                candidate_hit = int(r[1] == r[2])
                blocks.setdefault(key, []).append((candidate_hit - int(loads(r[3])["choice"] == r[2]),
                                                   candidate_hit - int(r[2] == "higher"),
                                                   candidate_hit - int(r[2] == "lower")))
            import random
            rng = random.Random(int(hashlib.sha256(candidate[0].encode()).hexdigest()[:12], 16))
            samples = list(blocks.values())
            draws = [[], [], []]
            for _ in range(1000):
                chosen = [samples[rng.randrange(len(samples))] for _ in samples]
                flattened = [delta for block in chosen for delta in block]
                for comparator in range(3):
                    draws[comparator].append(sum(x[comparator] for x in flattened) / len(flattened))
            lower = [sorted(values)[24] for values in draws]
            passed = (gain >= .01 and all(x > 0 for x in lower)
                      and candidate_wins > always_high and candidate_wins > always_low)
            result, reason = ("eligible", "predeclared_signal_gate_passed") if passed else (
                "rejected", "paired_gain_or_baseline_gate_failed")
        def write(db):
            changed = db.execute("UPDATE candidates SET status=? WHERE candidate_id=? AND status='frozen_shadow'",
                                 (result, candidate[0]))
            if changed.rowcount:
                self._event(db, "candidate_forward_complete", None,
                            candidate_id=candidate[0], status=result, reason=reason,
                            valid=len(valid), coverage=round(coverage, 4))
                if result == "eligible":
                    row = db.execute("SELECT spec_json FROM candidates WHERE candidate_id=?", (candidate[0],)).fetchone()
                    promoted_spec = loads(row[0])
                    promoted_hash = digest(promoted_spec)
                    db.execute("UPDATE meta SET value=? WHERE key='active_manifest'", (dumps(promoted_spec),))
                    db.execute("UPDATE meta SET value=? WHERE key='manifest_activated_at'", (str(self.clock.time()),))
                    db.execute("UPDATE candidates SET status='promoted' WHERE candidate_id=?", (candidate[0],))
                    self._event(db, "candidate_promoted", None, candidate_id=candidate[0],
                                previous_manifest=self.manifest_hash, manifest_hash=promoted_hash,
                                scope="signal_harness_only", trade_qualified=False)
                    self.manifest, self.manifest_hash = promoted_spec, promoted_hash
                    self.manifest_activated_at = self.clock.time()
        self._tx(write)

    def _clock_check(self):
        wall, mono = self.clock.time(), self.clock.monotonic()
        drift = abs((wall - self.last_wall) - (mono - self.last_mono))
        self.last_wall, self.last_mono = wall, mono
        if drift > .5:
            self.paused_reason = "clock_jump"
            self.ready_after = wall + 60
            self._tx(lambda db: (db.execute("INSERT OR IGNORE INTO warmup_intervals VALUES(?,?,?)",
                                            (wall, self.ready_after, "clock_jump")),
                                 self._event(db, "clock_jump", None, drift_s=round(drift, 3))))
        elif self.paused_reason in ("clock_jump", "trade_poll_gap", "possible_cursor_gap") and wall >= self.ready_after:
            self.paused_reason = None

    def _accounts(self):
        with self.lock:
            rows = self.db.execute("SELECT account_key,state_json FROM accounts").fetchall()
        return {r[0]: loads(r[1]) for r in rows}

    def _latest_observed_price(self, cutoff=None):
        cutoff = self.clock.time() if cutoff is None else cutoff
        with self.lock:
            row = self.db.execute("SELECT price,received_at,event_time FROM trades "
                                  "WHERE received_at<=? ORDER BY received_at DESC,event_time DESC LIMIT 1",
                                  (cutoff,)).fetchone()
        return {"price": row[0], "received_at": row[1], "event_time": row[2]} if row else None

    def _asset_config(self):
        with self.cache.lock:
            rules = getattr(self.cache, "asset_rules", None)
        config = {"initial_capital": CAPITAL, "fee_bps": BASE_SPEC["fee_bps"],
                  "latency_slippage_bps": BASE_SPEC["slippage_bps"],
                  "policy_id": self.manifest_hash[:16]}
        if isinstance(rules, dict):
            config.update({k: rules.get(k) for k in ("min_order_btc", "min_order_usd", "lot_decimals", "status")})
        return config

    def _qualified_policy_evaluate(self, at):
        start = at - 3600
        def write(db):
            if db.execute("SELECT 1 FROM qualified_policy_evaluations WHERE at=?", (at,)).fetchone():
                return
            count = db.execute("SELECT count(*) FROM rounds WHERE start>=? AND start<? "
                               "AND locked_at<start AND status IN ('locked','settled','tie','void')",
                               (start, at)).fetchone()[0]
            reason = "uncalibrated_one_hour_gross_return_vs_total_cost"
            db.execute("INSERT INTO qualified_policy_evaluations VALUES(?,?,?,?,?,?,?,?)",
                       (at, self.manifest_hash, "hold", reason, count, start, at,
                        dumps({"interval_s": 900, "minimum_holding_s": 3600,
                               "qualified_for_trade": False, "required_evidence": "independent calibrated gross return"})))
            self._event(db, "qualified_policy_evaluation", at, status="hold",
                        qualified_for_trade=False, reason=reason, locked_signals=count,
                        window_start=start, window_end=at)
        self._tx(write)

    def _evaluate(self, at):
        price = self._latest_observed_price(at)
        if price and not (0 <= at - price["event_time"] <= 5):
            price = {**price, "received_at": None}
        with self.lock:
            existing = self.db.execute("SELECT 1 FROM evaluations WHERE at=?", (at,)).fetchone()
            rows = self.db.execute("SELECT start,status,locked_at,baseline_json,optimized_json FROM rounds "
                                   "WHERE start>=? AND start<? AND manifest_hash=? ORDER BY start",
                                   (at - 30, at, self.manifest_hash)).fetchall()
        if existing:
            return
        locked = []
        for row in rows:
            if row[1] not in ("locked", "settled", "tie", "void") or not row[2] or row[2] >= row[0]:
                continue
            locked.append({"start": row[0], "status": row[1], "locked_at": row[2],
                           "baseline": loads(row[3]), "optimized": loads(row[4])})
        if at < self.manifest_activated_at + 30:
            locked = []
        config = self._asset_config()
        observed = price or {"price": None, "received_at": None}
        intents = []
        def write(db):
            if db.execute("SELECT 1 FROM evaluations WHERE at=?", (at,)).fetchone():
                return False
            account_rows = db.execute("SELECT account_key,state_json FROM accounts").fetchall()
            accounts = {r[0]: loads(r[1]) for r in account_rows}
            marked = paper_engine.mark_accounts(accounts, observed, at, config)
            accounts = marked["accounts"]
            evaluation = paper_engine.evaluate_exploration(locked, accounts, at, config)
            if not isinstance(evaluation, dict):
                raise ValueError("paper engine returned invalid evaluation")
            for key in ("baseline", "optimized"):
                db.execute("UPDATE accounts SET state_json=? WHERE account_key=?",
                           (dumps(accounts[key]), key))
                action = dict(evaluation.get(key) or {"side": "hold", "reason": "missing_action"})
                if action.get("side") in ("buy", "sell"):
                    action.update(account_key=key)
                    intents.append(action)
                evaluation[key] = action
            db.execute("INSERT INTO evaluations VALUES(?,?,?,?,?,?,?)",
                       (at, "evaluated", dumps(evaluation["baseline"]),
                        dumps(evaluation["optimized"]), None, None, self.manifest_hash))
            self._event(db, "portfolio_evaluation", at, baseline=evaluation["baseline"],
                        optimized=evaluation["optimized"], price=observed.get("price"))
            now = self.clock.time()
            for action in intents:
                action["intent_at"] = now
                action["order_id"] = f"{at}:{action['account_key']}"
                db.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?)",
                       (action["order_id"], at, action["account_key"], now,
                            action["side"], "intent", dumps(action), None, None))
                self._event(db, "order_intent", at, order_id=action["order_id"],
                            account=action["account_key"], side=action["side"],
                            notional_usd=action.get("notional_usd"))
            return True
        if not self._tx(write):
            return
        # Probe every slot, including all-hold slots, to measure quote coverage
        # without selecting only moments when a strategy wanted to trade.
        threading.Thread(target=self._fill_worker, args=(at, intents), daemon=True).start()

    def _fill_worker(self, at, intents):
        probe_at = self.clock.time()
        deadline = probe_at + 2
        quote = None
        try:
            quote = self.cache.fresh_depth_after(probe_at, deadline)
        except Exception as exc:
            self._tx(lambda db: self._event(db, "quote_error", at, message=str(exc)))
        now = self.clock.time()
        config = self._asset_config()
        mark_ref = self._latest_observed_price(at)
        def write(db):
            valid_time = bool(now <= deadline and quote and quote.get("valid_time") and
                              quote.get("request_started_at", 0) > probe_at and
                              quote.get("response_received_at", float("inf")) <= deadline)
            bids, asks = (quote.get("bids") or [], quote.get("asks") or []) if quote else ([], [])
            reason = "ok" if valid_time else "quote_timeout_or_invalid_time"
            if bids and asks:
                bid, ask = float(bids[0][0]), float(asks[0][0])
                spread_bps = (ask - bid) / ((ask + bid) / 2) * 10_000 if 0 < bid < ask else float("inf")
                if spread_bps > config.get("max_spread_bps", 10.0):
                    valid_time, reason = False, "invalid_or_wide_book"
                bid_depth = sum(float(x[0]) * float(x[1]) for x in bids)
                ask_depth = sum(float(x[0]) * float(x[1]) for x in asks)
                if bid_depth < 100 or ask_depth < 100:
                    valid_time, reason = False, "insufficient_probe_depth"
                if not mark_ref or not (0 <= at - mark_ref["event_time"] <= 5):
                    valid_time, reason = False, "stale_probe_mark"
                elif abs((bid + ask) / 2 / mark_ref["price"] - 1) * 10_000 > 25:
                    valid_time, reason = False, "probe_price_jump"
            else:
                valid_time, reason = False, "empty_book"
            db.execute("INSERT OR IGNORE INTO depth_probes VALUES(?,?,?,?,?,?,?)",
                       (at, probe_at, quote.get("response_received_at") if quote else None,
                        int(valid_time), reason, float(bids[0][0]) if bids else None,
                        float(asks[0][0]) if asks else None))
            self._event(db, "depth_probe", at, valid_time=valid_time, reason=reason,
                        latency_s=(quote["response_received_at"] - probe_at) if quote else None)
            if valid_time and not db.execute("SELECT 1 FROM meta WHERE key='benchmark_entry'").fetchone():
                benchmark_intent = {"side": "buy", "intent_at": probe_at,
                                    "mark_price": mark_ref["price"], "notional_usd": CAPITAL * .05,
                                    "order_id": f"benchmark:{at}", "account_key": "benchmark"}
                benchmark_fill = paper_engine.validate_quote(benchmark_intent, quote, now, config)
                if benchmark_fill["valid"]:
                    benchmark = {"source": "first_qualified_post_intent_depth", "quote_received_at": quote["response_received_at"],
                                 "cash": CAPITAL - benchmark_fill["cash_debit_usd"],
                                 "btc": benchmark_fill["quantity_btc"],
                                 "fee_usd": benchmark_fill["fee_usd"],
                                 "simulated_fill_price": benchmark_fill["simulated_fill_price"],
                                 "target_weight": .05}
                    db.execute("INSERT INTO meta(key,value) VALUES('benchmark_entry',?)", (dumps(benchmark),))
                    self._event(db, "benchmark_entry", at, **benchmark)
            for intent in intents:
                order_id = intent["order_id"]
                row = db.execute("SELECT status FROM orders WHERE order_id=?", (order_id,)).fetchone()
                if not row or row[0] != "intent":
                    continue
                valid = (paper_engine.validate_quote(intent, quote, now, config) if valid_time
                         else {"valid": False, "reason": "quote_timeout"})
                if not valid.get("valid"):
                    reason = valid.get("reason", "quote_invalid")
                    db.execute("UPDATE orders SET status='unfilled',reason=? WHERE order_id=?", (reason, order_id))
                    self._event(db, "timeout" if reason == "quote_timeout" else "blocked", at,
                                order_id=order_id, account=intent["account_key"], reason=reason)
                    continue
                key = intent["account_key"]
                account_row = db.execute("SELECT state_json FROM accounts WHERE account_key=?", (key,)).fetchone()
                account = loads(account_row[0])
                applied = paper_engine.apply_fill(account, intent, quote, config)
                updated = applied.get("account", account)
                fill = applied.get("fill")
                if not fill or fill.get("status") != "filled":
                    fill_reason = fill.get("reason", "fill_rejected") if fill else "fill_rejected"
                    db.execute("UPDATE orders SET status='unfilled',reason=? WHERE order_id=?", (fill_reason, order_id))
                    self._event(db, "blocked", at, order_id=order_id, reason=fill_reason)
                    continue
                fill_id = f"fill:{order_id}"
                db.execute("INSERT INTO fills VALUES(?,?,?,?,?)",
                           (fill_id, order_id, key, quote["response_received_at"], dumps(fill)))
                db.execute("UPDATE accounts SET state_json=? WHERE account_key=?", (dumps(updated), key))
                db.execute("UPDATE orders SET status='filled',fill_id=? WHERE order_id=?", (fill_id, order_id))
                self._event(db, "gate_pass", at, order_id=order_id, account=key)
                self._event(db, "paper_fill", at, order_id=order_id, account=key,
                            fill_id=fill_id, fill=fill)
        self._tx(write)
        self._mark_accounts()

    def _mark_accounts(self):
        price = self._latest_observed_price()
        if not price:
            return
        now = self.clock.time()
        if not (0 <= now - price["event_time"] <= 5):
            price = {**price, "received_at": None}
        if now - self.last_mark_attempt_at < 4.5:
            return
        self.last_mark_attempt_at = now
        config = self._asset_config()
        def write(db):
            account_rows = db.execute("SELECT account_key,state_json FROM accounts").fetchall()
            accounts = {r[0]: loads(r[1]) for r in account_rows}
            marked = paper_engine.mark_accounts(accounts, price, now, config)
            updated = marked["accounts"]
            for key in ("baseline", "optimized"):
                db.execute("UPDATE accounts SET state_json=? WHERE account_key=?",
                           (dumps(updated[key]), key))
            if not marked["comparison_eligible"]:
                self._event(db, "mark_stale", None, reason=marked["reason"],
                            last_price=price["price"], price_received_at=price["received_at"])
                return False
            initial = db.execute("SELECT value FROM meta WHERE key='benchmark_entry'").fetchone()
            saved = loads(initial[0]) if initial else None
            hold = saved["cash"] + saved["btc"] * price["price"] if saved else CAPITAL
            db.execute("INSERT OR REPLACE INTO marks VALUES(?,?,?,?,?)",
                       (now, price["price"], updated["baseline"].get("equity", CAPITAL),
                        updated["optimized"].get("equity", CAPITAL), hold))
            self._event(db, "account_mark", None, price=price["price"],
                        baseline=updated["baseline"].get("equity", CAPITAL),
                        optimized=updated["optimized"].get("equity", CAPITAL))
            return True
        if self._tx(write):
            self.last_mark_at = now

    def _tick(self):
        self._clock_check()
        self._ingest()
        now = self.clock.time()
        self._settle()
        self._candidate_progress()
        self._maybe_generate_candidate()
        current = int(math.floor(now / PERIOD) * PERIOD)
        if now >= current + .25:
            self._mark_missed(current)
        next_start = current + PERIOD
        if not self.paused_reason and 1.9 <= next_start - now <= 2.3:
            self._freeze_predict(next_start)
        if not self.paused_reason and now >= math.floor(now / 30) * 30 + .15:
            slot = int(math.floor(now / 30) * 30)
            if now < slot + 2:
                self._evaluate(slot)
        if now >= math.floor(now / 900) * 900 + .15:
            slot_15m = int(math.floor(now / 900) * 900)
            if now < slot_15m + 5:
                self._qualified_policy_evaluate(slot_15m)
        self._mark_accounts()

    def run(self):
        while True:
            try:
                self._tick()
            except Exception as exc:
                self.paused_reason = f"engine_error:{exc}"
                try:
                    self._tx(lambda db: self._event(db, "engine_error", None, message=str(exc)))
                except Exception:
                    pass
            time.sleep(.2)

    def _round_dict(self, row):
        return {"start": row["start"], "end": row["end"], "status": row["status"],
                "snapshot_id": row["snapshot_id"], "frozen_at": row["frozen_at"],
                "locked_at": row["locked_at"], "baseline": loads(row["baseline_json"]),
                "optimized": loads(row["optimized_json"]), "truth": row["truth"],
                "move_bps": row["move_bps"], "label_tier": row["label_tier"],
                "reason": row["reason"], "manifest_hash": row["manifest_hash"]}

    def _metrics(self, rows):
        paired = [r for r in rows if r["locked_at"] and r["locked_at"] < r["start"]]
        primary = [r for r in paired if r["label_tier"] == "primary" and r["truth"] in ("higher", "lower")]
        def one(key):
            wins = sum((r[key] or {}).get("choice") == r["truth"] for r in primary)
            return {"eligible": len(primary), "wins": wins,
                    "accuracy": round(wins / len(primary), 4) if primary else None}
        return {"baseline": one("baseline"), "optimized": one("optimized"),
                "rounds": len(rows), "paired": len(paired),
                "paired_coverage": round(len(paired) / len(rows), 4) if rows else None,
                "primary_labels": len(primary),
                "ties": sum(r["truth"] == "tie" for r in paired),
                "voids": sum(r["status"] == "void" for r in paired),
                "missed": sum(r["status"] == "missed" for r in rows)}

    def _metrics_all(self):
        with self.lock:
            r = self.db.execute("""
              SELECT count(*),
                coalesce(sum(CASE WHEN locked_at<start THEN 1 ELSE 0 END),0),
                coalesce(sum(CASE WHEN status='missed' THEN 1 ELSE 0 END),0),
                coalesce(sum(CASE WHEN status='void' THEN 1 ELSE 0 END),0),
                coalesce(sum(CASE WHEN truth='tie' THEN 1 ELSE 0 END),0),
                coalesce(sum(CASE WHEN label_tier='primary' AND truth IN ('higher','lower') THEN 1 ELSE 0 END),0),
                coalesce(sum(CASE WHEN label_tier='primary' AND truth IN ('higher','lower')
                  AND json_extract(baseline_json,'$.choice')=truth THEN 1 ELSE 0 END),0),
                coalesce(sum(CASE WHEN label_tier='primary' AND truth IN ('higher','lower')
                  AND json_extract(optimized_json,'$.choice')=truth THEN 1 ELSE 0 END),0)
              FROM rounds WHERE manifest_hash=?""", (self.manifest_hash,)).fetchone()
            post = self.db.execute("""
              SELECT count(*),coalesce(sum(CASE WHEN r.locked_at<r.start THEN 1 ELSE 0 END),0)
              FROM rounds r WHERE r.manifest_hash=? AND r.start>=?
              AND NOT EXISTS(SELECT 1 FROM warmup_intervals w WHERE r.start>=w.start AND r.start<w.end)
              """, (self.manifest_hash, self.manifest_activated_at + 60)).fetchone()
            latest_warmup_end = self.db.execute("SELECT max(end) FROM warmup_intervals").fetchone()[0]
            warmups = self.db.execute("SELECT start,end FROM warmup_intervals ORDER BY start").fetchall()
        total, paired, missed, voids, ties, labels, base_wins, opt_wins = r
        post_total, post_paired = post
        # Count every scheduled slot, including downtime that has no row. A
        # restart cannot silently make an outage disappear from coverage.
        end_exclusive = math.floor((self.clock.time() - .25) / PERIOD) * PERIOD + PERIOD
        def slot_count(lo, hi, period=PERIOD):
            return max(0, math.ceil(hi / period) - math.ceil(lo / period))
        expected = slot_count(self.manifest_activated_at, end_exclusive)
        implicit_missed = max(0, expected - total)
        total = max(total, expected)
        missed += implicit_missed
        post_start = self.manifest_activated_at + 60
        warmup_overlap = 0
        merged = []
        for start, end in warmups:
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        for start, end in merged:
            warmup_overlap += slot_count(max(post_start, start), min(end_exclusive, end))
        post_expected = max(0, slot_count(post_start, end_exclusive) - warmup_overlap)
        post_implicit_missed = max(0, post_expected - post_total)
        post_total = max(post_total, post_expected)
        qualification_start = max(self.manifest_activated_at + 60, latest_warmup_end or 0) + 300
        with self.lock:
            qualification = self.db.execute(
                "SELECT count(*),coalesce(sum(CASE WHEN locked_at<start THEN 1 ELSE 0 END),0) "
                "FROM rounds WHERE manifest_hash=? AND start>=?",
                (self.manifest_hash, qualification_start)).fetchone()
        qualification_total = max(qualification[0], slot_count(qualification_start, end_exclusive))
        return {"window": "current_manifest_all_time", "manifest_hash": self.manifest_hash,
                "rounds": total, "paired": paired,
                "paired_coverage": round(paired / total, 4) if total else None,
                "unrecorded_slots": implicit_missed,
                "post_warmup_rounds": post_total, "post_warmup_paired": post_paired,
                "post_warmup_paired_coverage": round(post_paired / post_total, 4) if post_total else None,
                "post_warmup_unrecorded_slots": post_implicit_missed,
                "qualification_window_start": qualification_start,
                "qualification_rounds": qualification_total, "qualification_paired": qualification[1],
                "qualification_paired_coverage": round(qualification[1] / qualification_total, 4) if qualification_total else None,
                "missed": missed, "voids": voids, "ties": ties,
                "primary_labels": labels,
                "baseline": {"eligible": labels, "wins": base_wins,
                             "accuracy": round(base_wins / labels, 4) if labels else None},
                "optimized": {"eligible": labels, "wins": opt_wins,
                              "accuracy": round(opt_wins / labels, 4) if labels else None}}

    def _events(self, after=0, limit=120):
        limit = min(1000, max(1, int(limit)))
        with self.lock:
            rows = self.db.execute("SELECT seq,at,kind,round_id,payload FROM events "
                                   "WHERE seq>? ORDER BY seq LIMIT ?", (int(after), limit)).fetchall()
        return [{"seq": r[0], "time": r[1], "kind": r[2], "round_id": r[3],
                 **loads(r[4], {})} for r in rows]

    def events_after(self, after=0, limit=200):
        return {"events": self._events(after, limit), "event_seq": self._latest_seq()}

    def _latest_seq(self):
        with self.lock:
            row = self.db.execute("SELECT max(seq) FROM events").fetchone()
        return row[0] or 0

    def round_detail(self, start):
        start = int(start)
        next_eval = int(math.ceil((start + PERIOD) / 30) * 30)
        with self.lock:
            row = self.db.execute("SELECT * FROM rounds WHERE start=?", (start,)).fetchone()
            snapshot = self.db.execute("SELECT market_json FROM snapshots WHERE round_start=?", (start,)).fetchone()
            events = self.db.execute("SELECT seq,at,kind,payload FROM events WHERE round_id=? ORDER BY seq",
                                     (start,)).fetchall()
            trade_window = self.db.execute("SELECT trade_id,event_time,received_at,price,volume,side FROM trades "
                                           "WHERE event_time>=? AND event_time<=? ORDER BY event_time",
                                           (start - 60, start + PERIOD + 10)).fetchall()
            marks = self.db.execute("SELECT at,price,baseline,optimized,buy_hold FROM marks "
                                    "WHERE at>=? AND at<=? ORDER BY at", (start - 30, start + 35)).fetchall()
            evaluation = self.db.execute("SELECT * FROM evaluations WHERE at=?", (next_eval,)).fetchone()
            orders = self.db.execute("SELECT o.*,f.fill_json,f.filled_at FROM orders o "
                                     "LEFT JOIN fills f ON f.order_id=o.order_id WHERE o.eval_at=? ORDER BY account_key",
                                     (next_eval,)).fetchall()
        if not row:
            return None
        return {"round": self._round_dict(row), "snapshot": loads(snapshot[0]) if snapshot else None,
                "events": [{"seq": r[0], "time": r[1], "kind": r[2], **loads(r[3])} for r in events],
                "trade_window": [{"id": r[0], "time": r[1], "received_at": r[2],
                                  "price": r[3], "volume": r[4], "side": r[5]} for r in trade_window],
                "marks": [{"time": r[0], "price": r[1], "baseline": r[2],
                           "optimized": r[3], "buy_hold": r[4]} for r in marks],
                "evaluation": {"time": evaluation[0], "status": evaluation[1],
                               "baseline": loads(evaluation[2]), "optimized": loads(evaluation[3])} if evaluation else None,
                "orders": [{"order_id": r[0], "time": r[3], "account": r[2], "side": r[4],
                            "status": r[5], "intent": loads(r[6]), "reason": r[7],
                            "fill": loads(r[9]), "quote_received_at": r[10]} for r in orders]}

    def snapshot(self):
        now = self.clock.time()
        market = self.cache.snapshot()
        with self.lock:
            round_rows = self.db.execute("SELECT * FROM rounds ORDER BY start DESC LIMIT 360").fetchall()
            latest_row = self.db.execute(
                "SELECT * FROM rounds WHERE manifest_hash=? AND locked_at<start "
                "AND baseline_json IS NOT NULL AND optimized_json IS NOT NULL "
                "AND status IN ('locked','settled','tie','void') "
                "ORDER BY start DESC LIMIT 1", (self.manifest_hash,)).fetchone()
            eval_rows = self.db.execute("SELECT * FROM evaluations ORDER BY at DESC LIMIT 20").fetchall()
            order_rows = self.db.execute("SELECT o.*,f.fill_json,f.filled_at FROM orders o "
                                         "LEFT JOIN fills f ON f.order_id=o.order_id "
                                         "ORDER BY o.eval_at DESC LIMIT 40").fetchall()
            marks = self.db.execute("SELECT * FROM marks ORDER BY at DESC LIMIT 720").fetchall()
            candidates = self.db.execute("SELECT * FROM candidates ORDER BY created_at DESC LIMIT 10").fetchall()
            qualified = self.db.execute("SELECT * FROM qualified_policy_evaluations ORDER BY at DESC LIMIT 5").fetchall()
            recent_events = self.db.execute("SELECT seq,at,kind,round_id,payload FROM events ORDER BY seq DESC LIMIT 120").fetchall()
            trade = self.db.execute("SELECT max(event_time) FROM trades").fetchone()[0]
            count = self.db.execute("SELECT count(*) FROM rounds").fetchone()[0]
            total_eval = self.db.execute("SELECT count(*) FROM evaluations").fetchone()[0]
            total_orders = self.db.execute("SELECT count(*) FROM orders").fetchone()[0]
            total_fills = self.db.execute("SELECT count(*) FROM fills").fetchone()[0]
            probes = self.db.execute("SELECT count(*),coalesce(sum(valid_time),0) FROM depth_probes "
                                     "WHERE eval_at>=?", (self.manifest_activated_at,)).fetchone()
            benchmark_row = self.db.execute("SELECT value FROM meta WHERE key='benchmark_entry'").fetchone()
        rounds = [self._round_dict(r) for r in round_rows]
        events = [{"seq": r[0], "time": r[1], "kind": r[2], "round_id": r[3],
                   **loads(r[4], {})} for r in reversed(recent_events)]
        accounts = self._accounts()
        points = [{"time": r[0], "baseline": r[2], "optimized": r[3],
                   "buy_hold": r[4], "cash": CAPITAL, "price": r[1]} for r in reversed(marks)]
        evaluations = [{"time": r[0], "status": r[1], "baseline": loads(r[2]),
                        "optimized": loads(r[3]), "reason": r[5]} for r in eval_rows]
        orders = [{"order_id": r[0], "time": r[3], "account": r[2], "side": r[4],
                   "action": r[4], "status": r[5], "intent": loads(r[6]), "reason": r[7],
                   "fill_id": r[8], "fill": loads(r[9]), "quote_received_at": r[10]} for r in order_rows]
        candidate_view = [{"candidate_id": r[0], "created_at": r[1], "status": r[2],
                           "proposer": r[3], "parent_hash": r[4], "spec_hash": r[5],
                           "spec": loads(r[6]), "attempts": loads(r[10]) if len(r) > 10 else loads(r[9]),
                           "visible_data_end": r[7], "forward_start": r[8],
                           "forward_end": r[9]} for r in candidates]
        for item in candidate_view:
            with self.lock:
                progress = self.db.execute("SELECT count(*),sum(CASE WHEN truth IN ('higher','lower') THEN 1 ELSE 0 END),"
                                           "sum(CASE WHEN truth=choice THEN 1 ELSE 0 END) FROM shadow_signals "
                                           "WHERE candidate_id=?", (item["candidate_id"],)).fetchone()
            item["progress"] = {"paired": progress[0] or 0, "valid_labels": progress[1] or 0,
                                "wins": progress[2] or 0, "required_valid": 5000,
                                "required_days": 7,
                                "reason": "collecting_forward_evidence" if item["status"] == "frozen_shadow" else item["status"]}
        qualified_view = [{"time": r[0], "manifest_hash": r[1], "status": r[2],
                           "reason": r[3], "locked_signals": r[4], "window_start": r[5],
                           "window_end": r[6], "spec": loads(r[7])} for r in qualified]
        health = {"feed_age_s": round(max(0, now - self.last_trades_poll), 2) if self.last_trades_poll else None,
                  "trade_age_s": round(max(0, now - trade), 2) if trade else None,
                  "trade_clock_ahead_s": round(max(0, trade - now), 3) if trade else 0,
                  "book_age_s": market.get("source_age_s", {}).get("book"),
                  "model_status": "error" if self.model_error else "online" if count else "warming",
                  "model_error": self.model_error, "db_status": "online",
                  "clock_status": "paused" if self.paused_reason == "clock_jump" else "ok",
                  "teacher_status": "offline_research", "paused_reason": self.paused_reason,
                  "ready_after": self.ready_after}
        latest = self._round_dict(latest_row) if latest_row else None
        current_rounds = [r for r in rounds if r["manifest_hash"] == self.manifest_hash]
        last_price = points[-1]["price"] if points else None
        benchmark_entry = loads(benchmark_row[0]) if benchmark_row else None
        benchmark = {"cash": CAPITAL, "buy_hold": points[-1]["buy_hold"] if points else CAPITAL,
                     "last_price": last_price,
                     "method": "5% static BTC from first qualifying post-intent Depth; same fee/slippage assumptions",
                     "entry": benchmark_entry, "eligible": bool(benchmark_entry)}
        probe_first = math.ceil(self.manifest_activated_at / 30) * 30
        probe_last = math.floor((now - .15) / 30) * 30
        probe_slots = max(0, (probe_last - probe_first) // 30 + 1)
        stats = {"evaluations": total_eval, "orders": total_orders,
                 "fills": total_fills, "depth_probes": probes[0],
                 "depth_probe_slots": probe_slots,
                 "depth_probe_2s_rate": round(probes[1] / probe_slots, 4) if probe_slots else None,
                 "depth_probe_attempt_rate": round(probes[0] / probe_slots, 4) if probe_slots else None,
                 "depth_probe_quality_given_probe": round(probes[1] / probes[0], 4) if probes[0] else None,
                 "paper_only": True, "capital_each": CAPITAL,
                 "cost_bps_one_way": BASE_SPEC["fee_bps"]}
        return {"server_time": now, "market": market, "health": health,
                "signal": {"rounds": rounds[:80], "metrics": self._metrics_all(),
                           "recent_metrics": {**self._metrics(current_rounds), "window": "latest_360_current_manifest_rounds_about_30m"},
                           "latest": latest},
                "portfolio": {"accounts": accounts, "points": points,
                              "evaluations": evaluations, "orders": orders,
                              "benchmark": benchmark, "stats": stats},
                "evolution": {"teacher_mode": "offline", "active_manifest": {"hash": self.manifest_hash,
                              "spec": self.manifest}, "candidates": candidate_view,
                              "shadow": {"status": "collecting_forward_evidence" if candidate_view else "awaiting_40_primary_training_rounds",
                                         "trade_qualified": False},
                              "qualified_policy": qualified_view},
                "events": events, "event_seq": events[-1]["seq"] if events else 0,
                "legacy_paper_excluded": True}

    def export(self):
        with self.lock:
            rows = self.db.execute("SELECT * FROM rounds ORDER BY start DESC LIMIT 5000").fetchall()
            events = self.db.execute("SELECT seq,at,kind,round_id,payload FROM events ORDER BY seq DESC LIMIT 10000").fetchall()
            orders = self.db.execute("SELECT * FROM orders ORDER BY eval_at DESC LIMIT 5000").fetchall()
            fills = self.db.execute("SELECT * FROM fills ORDER BY filled_at DESC LIMIT 5000").fetchall()
        return {"schema": "btc-system-export-v1", "paper_only": True,
                "manifest": self.manifest, "manifest_hash": self.manifest_hash,
                "rounds": [self._round_dict(r) for r in rows],
                "orders": [dict(r) for r in orders], "fills": [dict(r) for r in fills],
                "events": [{"seq": r[0], "time": r[1], "kind": r[2], "round_id": r[3],
                            **loads(r[4])} for r in events]}
