import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "btc"))
import jev_comparison as jc


FEATURES = {"points": [100.0] * 8, "trade_count_30s": 8,
            "buy_share_30s": 0.5}


class JevComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "test.sqlite3"
        db = sqlite3.connect(self.db_path)
        db.executescript("""CREATE TABLE rounds(start INTEGER PRIMARY KEY,snapshot_id TEXT,frozen_at REAL,
            locked_at REAL,label_tier TEXT,truth TEXT,baseline_json TEXT,optimized_json TEXT);
            CREATE TABLE snapshots(round_start INTEGER PRIMARY KEY,market_json TEXT);""")
        db.execute("INSERT INTO rounds VALUES(101,'same-snapshot',99,100.5,'primary','higher',?,?)",
                   (json.dumps({'choice': 'higher'}), json.dumps({'choice': 'lower'})))
        db.execute("INSERT INTO snapshots VALUES(101,?)",
                   (json.dumps({"features": FEATURES}),))
        db.commit()
        db.close()
        self.comparison = jc.JevComparison(self.db_path)
        self.comparison.key = "test-only"
        self.comparison.disabled_reason = None

    def tearDown(self):
        self.comparison.db.close()
        self.temp.cleanup()

    @staticmethod
    def response():
        return {"http_status": 200, "latency_ms": 40, "error": None,
                "choice": "higher", "probabilities": {"higher": .6, "lower": .4},
                "confidence": .6, "usage": {"inputTokens": 100}, "model": jc.MODEL}

    @staticmethod
    def payload():
        row = {"start": 101, "snapshot_id": "same-snapshot", "locked_at": 100.5,
               "label_tier": "primary", "truth": "higher",
               "baseline": {"choice": "higher"}, "optimized": {"choice": "lower"}}
        return {"signal": {"rounds": [row], "latest": row.copy()}}

    def test_on_time_answer_enters_only_shared_primary_score(self):
        with patch.object(jc.time, "time", side_effect=[100, 100.1, 100.2, 100.3, 100.4]), \
             patch.object(jc, "call_jev", return_value=self.response()):
            self.comparison.tick()
        state = self.comparison.enrich(self.payload())
        self.assertEqual(state["jev_comparison"]["shared_primary"], 1)
        self.assertEqual(state["jev_comparison"]["wins"],
                         {"jev": 1, "baseline": 1, "optimized": 0})
        self.assertEqual(state["signal"]["latest"]["jev"]["status"], "on_time")

    def test_late_answer_is_saved_but_cannot_score(self):
        with patch.object(jc.time, "time", side_effect=[100, 100.1, 101.2]), \
             patch.object(jc, "call_jev", return_value=self.response()):
            self.comparison.tick()
        state = self.comparison.enrich(self.payload())
        self.assertEqual(state["signal"]["latest"]["jev"]["status"], "late")
        self.assertEqual(state["jev_comparison"]["shared_primary"], 0)

    def test_unlimited_mode_continues_new_requests(self):
        self.comparison.max_calls = 0
        with patch.object(jc.time, "time", side_effect=[100, 100.1, 100.2, 100.3, 100.4]), \
             patch.object(jc, "call_jev", return_value=self.response()) as call:
            self.comparison.tick()
        call.assert_called_once()
        state = self.comparison.enrich(self.payload())['jev_comparison']
        self.assertTrue(state['unlimited_calls'])
        self.assertIsNone(state['disabled_reason'])
        self.comparison.disabled_reason = 'previous failure'
        with patch.object(jc, 'load_key', return_value='test-key'):
            self.assertEqual(self.comparison.request_retry()['status'], 'waiting_for_future_snapshot')

    def test_scores_remain_after_round_leaves_page_window(self):
        with patch.object(jc.time, "time", side_effect=[100, 100.1, 100.2, 100.3, 100.4]), \
             patch.object(jc, "call_jev", return_value=self.response()):
            self.comparison.tick()
        state = self.comparison.enrich({'signal': {'rounds': [], 'latest': None}})
        self.assertEqual(state['jev_comparison']['shared_primary'], 1)
        self.assertEqual(state['jev_comparison']['recent_scored'][0]['start'], 101)
        self.comparison.db.execute("UPDATE rounds SET label_tier='reference'")
        self.comparison.db.commit()
        self.assertEqual(self.comparison.enrich(self.payload())['jev_comparison']['shared_primary'], 0)

    def test_sqlite_commit_after_deadline_cannot_score(self):
        with patch.object(jc.time, "time", side_effect=[100, 100.1, 100.2, 101.1]), \
             patch.object(jc, "call_jev", return_value=self.response()):
            self.comparison.tick()
        state = self.comparison.enrich(self.payload())
        self.assertEqual(state["signal"]["latest"]["jev"]["status"], "late")
        self.assertEqual(state["jev_comparison"]["shared_primary"], 0)

    def test_aggregate_keeps_all_calls_but_excludes_invalid_common_questions(self):
        with patch.object(jc.time, "time", side_effect=[100, 100.1, 100.2, 100.3, 100.4]), \
             patch.object(jc, "call_jev", return_value=self.response()):
            self.comparison.tick()
        db = self.comparison.db
        for start, snapshot, status, tier, blue in (
                (102, 'wrong-snapshot', 'on_time', 'primary', 'higher'),
                (103, 'same-snapshot', 'late', 'primary', 'higher'),
                (104, 'same-snapshot', 'on_time', 'reference', 'higher'),
                (105, 'same-snapshot', 'on_time', 'primary', 'sideways')):
            db.execute("INSERT INTO rounds VALUES(?, 'same-snapshot',99,100.5,?,'higher',?,?)",
                       (start, tier, json.dumps({'choice': blue}), json.dumps({'choice': 'lower'})))
            db.execute("""INSERT INTO jev_decisions SELECT ?,?,submitted_at,completed_at,?,
                choice,probabilities_json,confidence,latency_ms,http_status,error,state_hash,model,
                usage_json FROM jev_decisions WHERE start=101""", (start, snapshot, status))
        db.commit()
        summary = self.comparison.enrich({'signal': {'rounds': [], 'latest': None}})['jev_comparison']
        self.assertEqual(summary['calls'], 5)
        self.assertEqual(summary['on_time'], 4)
        self.assertEqual(summary['late'], 1)
        self.assertEqual(summary['shared_primary'], 1)
        self.assertEqual(summary['wins'], {'jev': 1, 'baseline': 1, 'optimized': 0})
        self.assertEqual(summary['latest']['start'], 105)

    def test_transient_write_lock_retries_receipt_without_another_api_call(self):
        future = int(time.time()) + 10
        self.comparison.db.execute("UPDATE rounds SET start=?", (future,))
        self.comparison.db.execute("UPDATE snapshots SET round_start=?", (future,))
        self.comparison.db.commit()
        self.comparison.db.execute("PRAGMA busy_timeout=10")
        writer = sqlite3.connect(self.db_path, check_same_thread=False)
        writer.execute("BEGIN IMMEDIATE")
        timer = threading.Timer(.15, writer.rollback)
        timer.start()
        try:
            with patch.object(jc, "call_jev", return_value=self.response()) as provider:
                self.comparison.tick()
            provider.assert_called_once()
            self.assertIsNone(self.comparison.disabled_reason)
            self.assertGreater(self.comparison.storage_retry_count, 0)
            self.assertEqual(self.comparison.detail(future)["status"], "on_time")
            log = self.db_path.with_suffix(".jev-worker-errors.jsonl").read_text()
            self.assertIn("locked", log)
            self.assertIn('"http_status": 200', log)
        finally:
            timer.join()
            writer.close()

    def test_exhausted_storage_retry_keeps_receipt_and_does_not_recall(self):
        future = int(time.time()) + 10
        self.comparison.db.execute("UPDATE rounds SET start=?", (future,))
        self.comparison.db.execute("UPDATE snapshots SET round_start=?", (future,))
        self.comparison.db.commit()
        real_db = self.comparison.db
        class FailWrites:
            def execute(self, sql, *args):
                if sql.startswith("INSERT"):
                    raise sqlite3.OperationalError("database is locked")
                return real_db.execute(sql, *args)
            def rollback(self):
                return real_db.rollback()
        with patch.object(self.comparison, "db", FailWrites()), \
             patch.object(jc, "call_jev", return_value=self.response()) as provider, \
             patch.object(jc.time, "sleep"):
            self.comparison.tick()
            self.comparison.tick()
        provider.assert_called_once()
        self.assertIsNone(self.comparison.detail(future))
        self.assertIn(future, self.comparison.failed_save_starts)
        self.assertEqual(self.comparison.storage_retry_count, 4)
        self.assertIn('"http_status": 200',
                      self.db_path.with_suffix(".jev-worker-errors.jsonl").read_text())

    def test_deadline_during_status_commit_stays_late(self):
        with patch.object(jc.time, "time", side_effect=[100, 100.1, 100.2, 100.3, 101.2]), \
             patch.object(jc, "call_jev", return_value=self.response()):
            self.comparison.tick()
        self.assertEqual(self.comparison.detail(101)["status"], "late")
        self.assertEqual(self.comparison.enrich(self.payload())["jev_comparison"]["shared_primary"], 0)

    def test_worker_keeps_running_after_transient_read_lock(self):
        with patch.object(self.comparison, "tick", side_effect=[
                sqlite3.OperationalError("database is locked"), SystemExit]), \
             patch.object(jc.time, "sleep"):
            with self.assertRaises(SystemExit):
                self.comparison.run()
        self.assertIsNone(self.comparison.disabled_reason)
        self.assertEqual(self.comparison.storage_retry_count, 1)
        self.assertTrue(self.db_path.with_suffix(".jev-worker-errors.jsonl").is_file())

    def test_provider_denial_is_preserved_and_pauses_calls(self):
        failed = {**self.response(), "http_status": 403, "choice": None,
                  "error": "Free tier users do not have access to this model"}
        with patch.object(jc.time, "time", side_effect=[100, 100.1, 100.2]), \
             patch.object(jc, "call_jev", return_value=failed):
            self.comparison.tick()
        state = self.comparison.enrich(self.payload())
        self.assertEqual(state["jev_comparison"]["shared_primary"], 0)
        self.assertIn("HTTP 403", state["jev_comparison"]["disabled_reason"])
        self.assertEqual(state["signal"]["latest"]["jev"]["status"], "error")
        with patch.object(jc, "load_key", return_value="new-process-key"):
            restarted = jc.JevComparison(self.db_path)
        self.assertIn("HTTP 403", restarted.disabled_reason)
        restarted.db.close()

    def test_permission_retry_keeps_history_and_limits_repeated_requests(self):
        failed = {**self.response(), "http_status": 403, "choice": None,
                  "error": "Free tier users do not have access to this model"}
        with patch.object(jc.time, "time", side_effect=[100, 100.1, 100.2]), \
             patch.object(jc, "call_jev", return_value=failed):
            self.comparison.tick()
        with patch.object(jc, "load_key", return_value="paid-key"), \
             patch.object(jc.time, "monotonic", return_value=200):
            self.assertEqual(self.comparison.request_retry()["status"], "waiting_for_future_snapshot")
            self.assertIsNone(self.comparison.disabled_reason)
            self.assertEqual(self.comparison.detail(101)["http_status"], 403)
            self.comparison.disabled_reason = "HTTP 403"
            self.assertEqual(self.comparison.request_retry()["status"], "cooldown")


if __name__ == "__main__":
    unittest.main()
