"""Read-only dashboard snapshots, isolated from the decision writer's locks.

The strategy engine source/hash and its paper accounts are untouched. Read
methods run on a shallow view with a query-only connection. A single publisher
serves all browser tabs; cumulative scores carry their own computation time.
"""

import copy
from pathlib import Path
import sqlite3
import threading
import time


class DashboardReader:
    def __init__(self, system, jev, score_interval=10):
        self.system, self.jev = system, jev
        self.score_interval = score_interval
        self.lock = threading.RLock()
        self.db = sqlite3.connect(Path(system.db_path).resolve().as_uri() + '?mode=ro',
                                  uri=True, check_same_thread=False, timeout=.5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA query_only=ON')
        self.score_db = sqlite3.connect(Path(system.db_path).resolve().as_uri() + '?mode=ro',
                                       uri=True, check_same_thread=False, timeout=.5)
        self.score_db.row_factory = sqlite3.Row
        self.score_db.execute('PRAGMA query_only=ON')
        self.score_db_lock = threading.RLock()
        self.score_lock = threading.Lock()
        self.score_pending = False
        self.score_error = None
        self.metrics = self.summary = None
        self.scores_monotonic = None
        self.scores_at = None

    def _refresh_scores(self):
        began = time.monotonic()
        try:
            view, jview = copy.copy(self.system), copy.copy(self.jev)
            view.db, view.lock = self.score_db, self.score_db_lock
            jview.db, jview.lock = self.score_db, self.score_db_lock
            scores_at = self.system.clock.time()
            metrics, summary = view._metrics_all(), jview.score_summary()
            with self.score_lock:
                self.metrics, self.summary = metrics, summary
                self.scores_at, self.scores_monotonic = scores_at, began
                self.score_error = None
        except Exception as exc:
            with self.score_lock:
                self.score_error = f'{type(exc).__name__}: {exc}'
                self.scores_monotonic = began
            raise
        finally:
            with self.score_lock:
                self.score_pending = False

    def _refresh_scores_in_background(self):
        try:
            self._refresh_scores()
        except Exception as exc:
            print(f'[btc-dashboard-scores] {type(exc).__name__}: {exc}', flush=True)

    def snapshot(self):
        with self.lock:
            # Only snapshot/read methods are called on these views. query_only
            # also enforces the boundary if a read method later starts writing.
            view = copy.copy(self.system)
            view.db, view.lock = self.db, self.lock
            jview = copy.copy(self.jev)
            jview.db, jview.lock = self.db, self.lock
            if self.metrics is None:
                self._refresh_scores()
            else:
                with self.score_lock:
                    due = (not self.score_pending and
                           time.monotonic() - self.scores_monotonic >= self.score_interval)
                    if due:
                        self.score_pending = True
                if due:
                    self.score_thread = threading.Thread(target=self._refresh_scores_in_background,
                                                         daemon=True, name='btc-dashboard-scores')
                    self.score_thread.start()
            with self.score_lock:
                metrics, summary = dict(self.metrics), dict(self.summary)
                scores_at, score_error = self.scores_at, self.score_error
            view._metrics_all = lambda: metrics
            payload = jview.enrich(view.snapshot(), summary=summary)
            payload['dashboard'] = {'scores_updated_at': scores_at,
                                    'score_interval_s': self.score_interval,
                                    'last_score_error': score_error}
            return payload


class StatePublisher:
    def __init__(self, snapshot, interval=1):
        self.snapshot = snapshot
        self.interval = interval
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.payload = None
        self.last_error = None

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True,
                                       name='btc-read-only-dashboard')
        self.thread.start()

    def run(self):
        while not self.stop_event.is_set():
            try:
                payload = self.snapshot()
                with self.lock:
                    self.payload = payload
                    self.last_error = None
            except Exception as exc:
                error = f'{type(exc).__name__}: {exc}'
                with self.lock:
                    self.last_error = error
                print(f'[btc-dashboard] {error}', flush=True)
            self.stop_event.wait(self.interval)

    def response(self):
        with self.lock:
            payload, error = self.payload, self.last_error
        if payload is None:
            return 503, {'error': error or 'state_warming',
                         'message': '实时状态正在准备；没有补造数据。'}
        now = time.time()
        age = max(0, now - payload['server_time'])
        return 200, {**payload, 'dashboard': {**payload.get('dashboard', {}),
                    'served_at': now, 'snapshot_age_s': round(age, 3),
                    'stale': age > 5, 'last_error': error}}
