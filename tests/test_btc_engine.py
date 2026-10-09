"""Deterministic integration checks for causal locks and paper fills."""

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "apps"
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE / "pulse"))
sys.path.insert(0, str(HERE / "btc"))

from engine import BTCSystem, dumps


class Clock:
    def __init__(self, at):
        self.at = at

    def time(self):
        return self.at

    def monotonic(self):
        return self.at


class Cache:
    def __init__(self, clock, trades):
        self.clock = clock
        self.lock = threading.Lock()
        self.trades = trades
        self.times = {"trades": clock.time()}
        self.asset_rules = {"min_order_btc": .00005, "min_order_usd": .5,
                            "lot_decimals": 8, "status": "online"}
        self.quote_calls = 0

    def snapshot(self):
        return {"ready": True, "source_age_s": {"book": .1}}

    def fresh_depth_after(self, intent_at, deadline_at):
        self.quote_calls += 1
        self.clock.at = max(self.clock.at, intent_at + .3)
        return {"request_started_at": intent_at + .1,
                "response_received_at": intent_at + .2,
                "valid_time": True,
                "bids": [[99999.0, 1.0]], "asks": [[100001.0, 1.0]]}


def trade(price, at, identifier):
    return [str(price), ".001", at, "b", None, None, identifier]


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "btc.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_late_second_model_cannot_lock_or_recover_as_prediction(self):
        start = 1_800_000_005
        clock = Clock(start - 2.2)
        raw = [trade(100000 + i, clock.at - 100 + i, str(i)) for i in range(100)]
        cache = Cache(clock, raw)
        system = BTCSystem(cache, self.db_path, clock)
        system.ready_after = 0
        system._ingest()
        calls = []

        def predict(lane, _features):
            calls.append(lane)
            if len(calls) == 2:
                clock.at = start + .1
            return {"choice": "higher", "model_choice": "higher",
                    "probabilities": {"higher": .6, "lower": .4},
                    "model_ms": 1.0, "route": "laya"}

        system._predict_one = predict
        system._freeze_predict(start)
        self.assertEqual(len(calls), 2)
        self.assertEqual(system.round_detail(start)["round"]["status"], "partial")
        system.db.close()
        restarted = BTCSystem(cache, self.db_path, clock)
        restarted._predict_one = lambda *_: self.fail("Restart re-ran a past model call")
        restarted._freeze_predict(start)
        detail = restarted.round_detail(start)
        self.assertEqual(detail["round"]["status"], "missed")
        self.assertIsNone(detail["round"]["locked_at"])
        self.assertEqual(restarted.db.execute("SELECT count(*) FROM orders").fetchone()[0], 0)
        self.assertEqual(restarted.db.execute("SELECT count(*) FROM fills").fetchone()[0], 0)
        restarted.db.close()

    def test_stale_event_time_does_not_create_order(self):
        at = 1_800_000_030
        clock = Clock(at + .2)
        cache = Cache(clock, [trade(100000, at - 60, "old")])
        cache.times["trades"] = at - .1
        system = BTCSystem(cache, self.db_path, clock)
        system.manifest_activated_at = at - 100
        system._ingest()
        for start in range(at - 30, at, 5):
            system.db.execute("INSERT INTO rounds(start,end,status,locked_at,baseline_json,optimized_json,manifest_hash) "
                              "VALUES(?,?,?,?,?,?,?)", (start, start + 5, "locked", start - 1,
                              dumps({"choice": "higher"}), dumps({"choice": "higher"}), system.manifest_hash))
        system._evaluate(at)
        for _ in range(50):
            with system.lock:
                done = system.db.execute("SELECT count(*) FROM depth_probes").fetchone()[0]
            if done:
                break
            time.sleep(.01)
        self.assertEqual(system.db.execute("SELECT count(*) FROM orders").fetchone()[0], 0)
        accounts = system._accounts()
        self.assertTrue(accounts["baseline"]["mark_stale"])
        self.assertEqual(accounts["baseline"]["cash"], 10000)
        self.assertEqual(accounts["baseline"]["btc"], 0)
        system.db.close()

    def test_one_causal_depth_fill_remains_unique_after_repeat(self):
        at = 1_800_000_060
        clock = Clock(at + .2)
        cache = Cache(clock, [trade(100000, at - .5, "recent")])
        cache.times["trades"] = at - .1
        system = BTCSystem(cache, self.db_path, clock)
        system.manifest_activated_at = at - 100
        system._ingest()
        for start in range(at - 30, at, 5):
            system.db.execute("INSERT INTO rounds(start,end,status,locked_at,baseline_json,optimized_json,manifest_hash) "
                              "VALUES(?,?,?,?,?,?,?)", (start, start + 5, "locked", start - 1,
                              dumps({"choice": "higher"}), dumps({"choice": "higher"}), system.manifest_hash))
        system._evaluate(at)
        for _ in range(100):
            with system.lock:
                done = system.db.execute("SELECT count(*) FROM events WHERE kind='account_mark'").fetchone()[0]
            if done:
                break
            time.sleep(.01)
        orders = system.db.execute("SELECT intent_json FROM orders ORDER BY order_id").fetchall()
        self.assertEqual(len(orders), 2)
        self.assertEqual(system.db.execute("SELECT count(*) FROM fills").fetchone()[0], 2)
        intents = [__import__("json").loads(r[0]) for r in orders]
        system._fill_worker(at, intents)
        self.assertEqual(system.db.execute("SELECT count(*) FROM fills").fetchone()[0], 2)
        accounts = system._accounts()
        self.assertEqual(accounts["baseline"]["trades"], 1)
        self.assertGreater(accounts["baseline"]["btc"], 0)
        self.assertGreater(accounts["baseline"]["fees"], 0)
        system.db.close()

    def test_local_candidate_uses_settled_training_and_future_embargo(self):
        start0 = 1_800_000_000
        clock = Clock(start0 + 40 * 5 + 12)
        system = BTCSystem(Cache(clock, []), self.db_path, clock)
        for i in range(40):
            start = start0 + i * 5
            sid = f"sample-{i}"
            system.db.execute("INSERT INTO snapshots VALUES(?,?,?,?,?)",
                              (sid, start, start - 2,
                               dumps({"features": {"mom_15s_bps": 0.5 if i % 2 else -0.5}}),
                               system.manifest_hash))
            system.db.execute("INSERT INTO rounds(start,end,status,snapshot_id,locked_at,optimized_json,truth,label_tier,manifest_hash) "
                              "VALUES(?,?,?,?,?,?,?,?,?)",
                              (start, start + 5, "settled", sid, start - 1,
                               dumps({"choice": "higher" if i % 2 else "lower",
                                      "model_choice": "higher" if i % 2 else "lower", "route": "laya"}),
                               "higher" if i % 2 else "lower", "primary", system.manifest_hash))
        system._maybe_generate_candidate()
        row = system.db.execute("SELECT proposer,status,visible_data_end,forward_start,attempts_json "
                                "FROM candidates").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "local_grid")
        self.assertEqual(row[1], "frozen_shadow")
        self.assertGreaterEqual(row[3] - row[2], 60)
        self.assertEqual(len(__import__("json").loads(row[4])), 4)
        self.assertEqual(system.db.execute("SELECT count(*) FROM shadow_signals").fetchone()[0], 0)
        system.db.execute("UPDATE candidates SET status='rejected',forward_end=?", (clock.at - 1,))
        frozen_events = system.db.execute("SELECT count(*) FROM events WHERE kind='candidate_frozen'").fetchone()[0]
        system._maybe_generate_candidate()
        self.assertEqual(system.db.execute("SELECT count(*) FROM events WHERE kind='candidate_frozen'").fetchone()[0], frozen_events)
        system.db.close()

    def test_downtime_remains_in_coverage_denominator(self):
        start = 1_800_000_000
        clock = Clock(start)
        system = BTCSystem(Cache(clock, []), self.db_path, clock)
        clock.at = start + 140
        metrics = system._metrics_all()
        self.assertEqual(metrics["rounds"], 28)
        self.assertEqual(metrics["unrecorded_slots"], 28)
        self.assertEqual(metrics["post_warmup_rounds"], 16)
        self.assertEqual(metrics["post_warmup_unrecorded_slots"], 16)
        self.assertEqual(metrics["paired_coverage"], 0)
        stats = system.snapshot()["portfolio"]["stats"]
        self.assertEqual(stats["depth_probe_slots"], 5)
        self.assertEqual(stats["depth_probe_2s_rate"], 0)
        system.db.close()

    def test_latest_locked_decision_never_crosses_manifest_cohort(self):
        start = 1_800_000_000
        clock = Clock(start + 10)
        system = BTCSystem(Cache(clock, []), self.db_path, clock)
        choice = dumps({"choice": "higher", "model_choice": "higher"})
        system.db.execute(
            "INSERT INTO rounds(start,end,status,locked_at,baseline_json,optimized_json,manifest_hash) "
            "VALUES(?,?,?,?,?,?,?)",
            (start, start + 5, "settled", start - 1, choice, choice, "previous-manifest"))
        state = system.snapshot()
        self.assertIsNone(state["signal"]["latest"])
        self.assertEqual(state["signal"]["recent_metrics"]["paired"], 0)
        system.db.execute(
            "INSERT INTO rounds(start,end,status,locked_at,baseline_json,optimized_json,manifest_hash) "
            "VALUES(?,?,?,?,?,?,?)",
            (start + 5, start + 10, "locked", start + 4, choice, choice, system.manifest_hash))
        self.assertEqual(system.snapshot()["signal"]["latest"]["start"], start + 5)
        system.db.close()

    def test_restart_reconciles_legacy_direction_counts_only_once(self):
        start = 1_800_000_000
        clock = Clock(start + 20)
        cache = Cache(clock, [])
        system = BTCSystem(cache, self.db_path, clock)
        original = system._accounts()["baseline"]
        original.update(cash=9701.25, btc=.0021, basis=215.43,
                        realized=3.17, fees=1.28, trades=2, buys=0, sells=0)
        system.db.execute("UPDATE accounts SET state_json=? WHERE account_key='baseline'", (dumps(original),))
        for i, side in enumerate(("buy", "sell")):
            order_id = f"legacy-{i}"
            system.db.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?)",
                              (order_id, start, "baseline", start + i, side,
                               "filled", dumps({"side": side}), None, f"fill:{order_id}"))
            system.db.execute("INSERT INTO fills VALUES(?,?,?,?,?)",
                              (f"fill:{order_id}", order_id, "baseline", start + i + .2,
                               dumps({"side": side, "status": "filled"})))
        system.db.close()
        recovered = BTCSystem(cache, self.db_path, clock)
        account = recovered._accounts()["baseline"]
        self.assertEqual((account["buys"], account["sells"]), (1, 1))
        self.assertEqual({k: v for k, v in account.items() if k not in ("buys", "sells")},
                         {k: v for k, v in original.items() if k not in ("buys", "sells")})
        events = recovered.db.execute(
            "SELECT count(*) FROM events WHERE kind='account_counts_reconciled'").fetchone()[0]
        self.assertEqual(events, 1)
        recovered.db.close()
        restarted = BTCSystem(cache, self.db_path, clock)
        self.assertEqual(restarted._accounts()["baseline"], account)
        self.assertEqual(restarted.db.execute(
            "SELECT count(*) FROM events WHERE kind='account_counts_reconciled'").fetchone()[0], 1)
        restarted.db.close()


if __name__ == "__main__":
    unittest.main()
