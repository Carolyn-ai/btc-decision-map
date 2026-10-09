"""Separate, strictly timed Jev decision ledger for the BTC paper workbench.

Jev is called through Vercel AI Gateway. It never sends orders and never
changes the two existing Laya paper accounts. Only public, frozen market
features are sent. A response that commits at or after the round start is
saved as late and is excluded from the three-way score.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


ENDPOINT = "https://ai-gateway.vercel.sh/v1/evaluate"
MODEL = "typesafe-ai/jev"
INSTRUCTIONS = "Will BTC/USD be higher or lower in the next five seconds? Pick a direction."
CRITERIA = {
    "higher": "BTC/USD spot trade price is higher five seconds later",
    "lower": "BTC/USD spot trade price is lower five seconds later",
}


def load_key():
    if os.environ.get("JEV_ENABLED", "false").lower() != "true":
        return None
    key = os.environ.get("AI_GATEWAY_API_KEY", "").strip()
    if key:
        return key
    filename = os.environ.get("JEV_ENV_FILE", "").strip()
    if not filename:
        return None
    path = Path(filename).expanduser()
    if not path.is_file():
        return None
    for line in path.read_text().splitlines():
        name, sep, value = line.strip().removeprefix("export ").partition("=")
        if sep and name.strip() == "AI_GATEWAY_API_KEY":
            return value.strip().strip("\"'") or None
    return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError("Gateway redirect refused")


def frozen_state(features):
    """The blue Laya question uses this exact public input format."""
    pts = ", ".join(f"{p:.1f}" for p in features["points"])
    return (f"BTC/USD Kraken spot trade prices at 60,45,30,20,15,10,5,0 seconds ago: {pts}. "
            f"Last 30 seconds: {features['trade_count_30s']} trades, buyer share "
            f"{features['buy_share_30s']:.1%}.")


def call_jev(state, key, timeout=3):
    body = {"model": MODEL, "state": state,
            "questions": {"direction": {"type": "choice", "instructions": INSTRUCTIONS,
                                        "criteria": CRITERIA}}}
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + key,
                                              "Content-Type": "application/json"}, method="POST")
    start = time.perf_counter()
    status, payload, error = None, None, None
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            status = response.status
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read(1200).decode(errors="replace")
        try:
            error = json.loads(raw).get("error", {}).get("message", raw)
        except (ValueError, AttributeError):
            error = raw
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    if error:
        error = error.replace(key, "[REDACTED]")
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    result = {"http_status": status, "latency_ms": elapsed, "error": error,
              "choice": None, "probabilities": None, "confidence": None,
              "usage": None, "model": None}
    if status == 200 and isinstance(payload, dict):
        answer = (payload or {}).get("answers", {}).get("direction", {})
        choice, probs = answer.get("choice"), answer.get("probabilities")
        if (payload.get("model") != MODEL or answer.get("type") != "choice" or
                choice not in CRITERIA or not isinstance(probs, dict) or
                set(probs) != set(CRITERIA) or
                any(not isinstance(v, (int, float)) or not 0 <= v <= 1 for v in probs.values())):
            result["error"] = "Jev response failed model or choice schema validation"
        else:
            result.update(choice=choice, probabilities=probs,
                          confidence=answer.get("confidence"),
                          usage=payload.get("usage"), model=payload.get("model"))
    elif status == 200:
        result["error"] = "Jev response is not an object"
    return result


class JevComparison:
    def __init__(self, db_path, max_calls=None):
        self.db_path = Path(db_path)
        self.key = load_key()
        self.max_calls = int(max_calls if max_calls is not None else os.environ.get("JEV_MAX_CALLS", "60"))
        if not 0 <= self.max_calls <= 10000:
            raise ValueError("JEV_MAX_CALLS must be 0 (unlimited) or between 1 and 10000")
        self.disabled_reason = None if self.key else "AI_GATEWAY_API_KEY 未配置"
        self.db = sqlite3.connect(self.db_path, check_same_thread=False, timeout=1)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=1000")
        self.lock = threading.RLock()
        self.retry_not_before = 0.0
        self.last_worker_error = None
        self.storage_retry_count = 0
        self.failed_save_starts = set()
        with self.lock:
            self.db.execute("""CREATE TABLE IF NOT EXISTS jev_decisions(
              start INTEGER PRIMARY KEY, snapshot_id TEXT NOT NULL,
              submitted_at REAL NOT NULL, completed_at REAL NOT NULL,
              status TEXT NOT NULL, choice TEXT, probabilities_json TEXT,
              confidence REAL, latency_ms REAL, http_status INTEGER,
              error TEXT, state_hash TEXT NOT NULL, model TEXT,
              usage_json TEXT)""")
            self.db.commit()
            if self.key and os.environ.get("JEV_RETRY_AUTH") != "1":
                denied = self.db.execute("""SELECT http_status,error FROM jev_decisions
                    ORDER BY start DESC LIMIT 1""").fetchone()
                if denied and denied["http_status"] in (401, 402, 403):
                    self.disabled_reason = f"HTTP {denied['http_status']}: {denied['error']}"

    def request_retry(self):
        """Resume only future questions; preserve every prior error and answer."""
        with self.lock:
            if not self.disabled_reason:
                return {"status": "already_running"}
            now = time.monotonic()
            if now < self.retry_not_before:
                return {"status": "cooldown", "retry_after_s": round(self.retry_not_before - now, 1)}
            calls = self.db.execute("SELECT count(*) FROM jev_decisions").fetchone()[0]
            if self.max_calls and calls >= self.max_calls:
                return {"status": "call_limit", "max_calls": self.max_calls}
            key = load_key()
            if not key:
                return {"status": "missing_key"}
            self.key = key
            self.retry_not_before = now + 30
            self.disabled_reason = None
            return {"status": "waiting_for_future_snapshot"}

    def run(self):
        while True:
            if self.disabled_reason:
                time.sleep(1)
                continue
            try:
                self.tick()
            except sqlite3.OperationalError as exc:
                with self.lock:
                    self.db.rollback()
                if self._is_busy(exc):
                    self._record_storage_error(exc)
                    time.sleep(1)
                    continue
                self.disabled_reason = f"Jev worker error: {type(exc).__name__}: {exc}"
            except Exception as exc:
                self.disabled_reason = f"Jev worker error: {type(exc).__name__}: {exc}"
            time.sleep(.05)

    @staticmethod
    def _is_busy(exc):
        return any(word in str(exc).lower() for word in ("locked", "busy"))

    def _record_storage_error(self, exc, receipt=None):
        self.storage_retry_count += 1
        self.last_worker_error = {"at": time.time(), "error": f"{type(exc).__name__}: {exc}",
                                  "kind": "sqlite_busy", "receipt": receipt}
        # Keep the real failure (and any response not yet in SQLite) outside
        # the locked database. This log never contributes to scores.
        with self.db_path.with_suffix(".jev-worker-errors.jsonl").open("a") as stream:
            stream.write(json.dumps(self.last_worker_error, ensure_ascii=False) + "\n")

    def tick(self):
        now = time.time()
        with self.lock:
            row = self.db.execute("""SELECT r.start,r.snapshot_id,s.market_json
                FROM rounds r JOIN snapshots s ON s.round_start=r.start
                LEFT JOIN jev_decisions j ON j.start=r.start
                WHERE j.start IS NULL AND r.start>? AND r.frozen_at IS NOT NULL
                ORDER BY r.start LIMIT 1""", (now,)).fetchone()
            calls = self.db.execute("SELECT count(*) FROM jev_decisions").fetchone()[0]
        if self.max_calls and calls >= self.max_calls:
            self.disabled_reason = f"Jev 调用上限 {self.max_calls} 次已到；停止新请求"
            return
        if not row:
            return
        if row["start"] in self.failed_save_starts:
            return
        state = frozen_state(json.loads(row["market_json"])["features"])
        submitted = time.time()
        result = call_jev(state, self.key)
        completed = time.time()
        status = ("on_time" if result["choice"] and completed < row["start"] else
                  "late" if result["choice"] else "error")
        receipt = {"start": row["start"], "snapshot_id": row["snapshot_id"],
                   "submitted_at": submitted, "completed_at": completed, "result": result}
        # Retry storing this same response, never call the paid provider again
        # just to retry a write. Start as late until the durable commit passes.
        for attempt in range(4):
            try:
                with self.lock:
                    self.db.execute("""INSERT OR IGNORE INTO jev_decisions VALUES(
                      ?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                      (row["start"], row["snapshot_id"], submitted, completed,
                       "late" if status == "on_time" else status,
                       result["choice"], json.dumps(result["probabilities"]),
                       result["confidence"], result["latency_ms"], result["http_status"],
                       result["error"], hashlib.sha256(state.encode()).hexdigest(),
                       result["model"], json.dumps(result["usage"])))
                    self.db.execute("UPDATE jev_decisions SET status=? WHERE start=?",
                                    ("late" if status == "on_time" else status, row["start"]))
                    self.db.commit()
                    if status == "on_time" and time.time() < row["start"]:
                        self.db.execute("UPDATE jev_decisions SET status='on_time' WHERE start=?",
                                        (row["start"],))
                        self.db.commit()
                        if time.time() >= row["start"]:
                            self.db.execute("UPDATE jev_decisions SET status='late' WHERE start=?",
                                            (row["start"],))
                            self.db.commit()
                break
            except sqlite3.OperationalError as exc:
                with self.lock:
                    self.db.rollback()
                if not self._is_busy(exc):
                    raise
                self._record_storage_error(exc, receipt)
                if attempt == 3:
                    self.failed_save_starts.add(row["start"])
                    break
                time.sleep(.1 * (attempt + 1))
        if result["http_status"] in (401, 402, 403, 429):
            self.disabled_reason = f"HTTP {result['http_status']}: {result['error']}"

    def _row(self, row):
        if not row:
            return None
        item = dict(row)
        item["probabilities"] = json.loads(item.pop("probabilities_json"))
        item["usage"] = json.loads(item.pop("usage_json"))
        return item

    def detail(self, start):
        with self.lock:
            row = self.db.execute("SELECT * FROM jev_decisions WHERE start=?", (int(start),)).fetchone()
        return self._row(row)

    def score_summary(self):
        """Aggregate the complete ledger without decoding every saved response."""
        eligible = """FROM rounds r JOIN jev_decisions j ON j.start=r.start
            WHERE r.locked_at<r.start AND r.label_tier='primary'
              AND r.truth IN ('higher','lower') AND j.status='on_time'
              AND j.completed_at<r.start AND j.snapshot_id=r.snapshot_id
              AND json_extract(r.baseline_json,'$.choice') IN ('higher','lower')
              AND json_extract(r.optimized_json,'$.choice') IN ('higher','lower')"""
        with self.lock:
            counts = self.db.execute("""SELECT count(*),
                coalesce(sum(status='on_time'),0),coalesce(sum(status='late'),0),
                coalesce(sum(status='error'),0) FROM jev_decisions""").fetchone()
            totals = self.db.execute("""SELECT count(*),
                coalesce(sum(j.choice=r.truth),0),
                coalesce(sum(json_extract(r.baseline_json,'$.choice')=r.truth),0),
                coalesce(sum(json_extract(r.optimized_json,'$.choice')=r.truth),0)
                """ + eligible).fetchone()
            recent = self.db.execute("""SELECT r.start,r.truth,
                json_extract(r.baseline_json,'$.choice') AS baseline,
                json_extract(r.optimized_json,'$.choice') AS optimized,j.choice AS jev
                """ + eligible + " ORDER BY r.start DESC LIMIT 8").fetchall()
        wins = dict(zip(('jev', 'baseline', 'optimized'), totals[1:]))
        return {"calls": counts[0], "on_time": counts[1], "late": counts[2],
                "errors": counts[3], "shared_primary": totals[0], "wins": wins,
                "score_scope": "all_saved_shared_primary_rounds",
                "recent_scored": [dict(r) for r in recent],
                "accuracy": {key: round(value / totals[0], 4) if totals[0] else None
                             for key, value in wins.items()}}

    def enrich(self, payload, summary=None):
        rounds = payload.get("signal", {}).get("rounds", [])
        latest = payload.get("signal", {}).get("latest")
        starts = {row['start'] for row in rounds}
        if latest:
            starts.add(latest['start'])
        with self.lock:
            records = {r['start']: self._row(r) for r in self.db.execute(
                f"SELECT * FROM jev_decisions WHERE start IN ({','.join('?' for _ in starts)})",
                tuple(starts))} if starts else {}
            latest_record = self._row(self.db.execute(
                "SELECT * FROM jev_decisions ORDER BY start DESC LIMIT 1").fetchone())
        for row in rounds:
            row["jev"] = records.get(row["start"])
        if latest:
            latest["jev"] = records.get(latest["start"])
        payload["jev_comparison"] = {
            **(self.score_summary() if summary is None else summary),
            "provider": "Vercel AI Gateway", "model": MODEL,
            "local_model": False, "paper_account": False,
            "disabled_reason": self.disabled_reason,
            "last_worker_error": self.last_worker_error,
            "storage_retry_count": self.storage_retry_count,
            "max_calls": self.max_calls,
            "unlimited_calls": self.max_calls == 0,
            "latest": latest_record,
        }
        return payload

    def export(self):
        with self.lock:
            rows = self.db.execute("SELECT * FROM jev_decisions ORDER BY start DESC").fetchall()
        return [self._row(r) for r in rows]
