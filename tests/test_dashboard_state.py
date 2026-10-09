import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard_state import DashboardReader, StatePublisher


class SourceView:
    def _metrics_all(self):
        return {'count': self.db.execute('SELECT count(*) FROM samples').fetchone()[0]}

    def snapshot(self):
        with self.lock:
            count = self.db.execute('SELECT count(*) FROM samples').fetchone()[0]
        return {'server_time': time.time(), 'count': count, 'metrics': self._metrics_all()}


class JevView:
    def score_summary(self):
        with self.lock:
            return {'count': self.db.execute('SELECT count(*) FROM samples').fetchone()[0]}

    def enrich(self, payload, summary=None):
        return {**payload, 'jev_comparison': summary}


class DashboardTest(unittest.TestCase):
    def test_reader_does_not_wait_for_writer_lock_or_allow_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            source = SourceView()
            source.db_path = Path(folder) / 'ledger.sqlite3'
            source.db = sqlite3.connect(source.db_path)
            source.db.execute('PRAGMA journal_mode=WAL')
            source.db.execute('CREATE TABLE samples(value INTEGER)')
            source.db.execute('INSERT INTO samples VALUES(1)')
            source.db.commit()
            source.lock, source.clock = threading.Lock(), time
            jev = JevView()
            jev.db, jev.lock = source.db, source.lock
            reader = DashboardReader(source, jev)
            source.lock.acquire()
            source.db.execute('BEGIN IMMEDIATE')
            source.db.execute('INSERT INTO samples VALUES(2)')
            try:
                result = reader.snapshot()
                self.assertEqual(result['count'], 1)
                self.assertEqual(result['metrics']['count'], 1)
                with self.assertRaises(sqlite3.OperationalError):
                    reader.db.execute('DELETE FROM samples')
                self.assertIs(jev.db, source.db)
                self.assertIs(jev.lock, source.lock)
            finally:
                source.db.rollback()
                source.lock.release()
                reader.db.close()
                reader.score_db.close()
                source.db.close()

    def test_slow_score_refresh_does_not_block_new_state(self):
        with tempfile.TemporaryDirectory() as folder:
            source = SourceView()
            source.db_path = Path(folder) / 'ledger.sqlite3'
            source.db = sqlite3.connect(source.db_path)
            source.db.execute('PRAGMA journal_mode=WAL')
            source.db.execute('CREATE TABLE samples(value INTEGER)')
            source.db.execute('INSERT INTO samples VALUES(1)')
            source.db.commit()
            source.lock, source.clock = threading.RLock(), time
            jev = JevView()
            reader = DashboardReader(source, jev, score_interval=0)
            first = reader.snapshot()
            entered, release = threading.Event(), threading.Event()

            def slow():
                entered.set()
                release.wait(2)
                return {'count': 2}

            source._metrics_all = slow
            try:
                began = time.perf_counter()
                second = reader.snapshot()
                self.assertLess(time.perf_counter() - began, .1)
                self.assertTrue(entered.wait(1))
                self.assertGreater(second['server_time'], first['server_time'])
                self.assertEqual(second['metrics']['count'], 1)
                self.assertEqual(second['dashboard']['scores_updated_at'],
                                 first['dashboard']['scores_updated_at'])
            finally:
                release.set()
                reader.score_thread.join(2)
                reader.db.close()
                reader.score_db.close()
                source.db.close()

    def test_initial_state_is_an_honest_503(self):
        publisher = StatePublisher(lambda: {})
        status, response = publisher.response()
        self.assertEqual(status, 503)
        self.assertEqual(response['error'], 'state_warming')
        self.assertNotIn('signal', response)

    def test_response_does_not_wait_for_slow_snapshot(self):
        entered, release = threading.Event(), threading.Event()

        def slow():
            entered.set()
            release.wait(2)
            return {'server_time': time.time(), 'actual': 2}

        publisher = StatePublisher(slow)
        captured_at = time.time()
        publisher.payload = {'server_time': captured_at, 'actual': 1}
        publisher.start()
        self.assertTrue(entered.wait(1))
        try:
            began = time.perf_counter()
            status, response = publisher.response()
            self.assertLess(time.perf_counter() - began, .05)
            self.assertEqual(status, 200)
            self.assertEqual(response['server_time'], captured_at)
            self.assertEqual(response['actual'], 1)
        finally:
            publisher.stop_event.set()
            release.set()
            publisher.thread.join(2)

    def test_old_state_retains_timestamp_and_real_error(self):
        publisher = StatePublisher(lambda: {})
        old = time.time() - 30
        publisher.payload = {'server_time': old, 'actual': 1}
        publisher.last_error = 'OperationalError: database is locked'
        status, response = publisher.response()
        self.assertEqual(status, 200)
        self.assertEqual(response['server_time'], old)
        self.assertTrue(response['dashboard']['stale'])
        self.assertIn('locked', response['dashboard']['last_error'])
        self.assertNotIn('dashboard', publisher.payload)
