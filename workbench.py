"""Single local BTC decision and paper-trading workbench."""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "apps" / "market"))
sys.path.insert(0, str(ROOT / "apps" / "pulse"))
sys.path.insert(0, str(ROOT / "apps" / "btc"))

from runtime_config import DATA_DIR, PORT, apply_runtime_env
apply_runtime_env()

import market
from engine import BTCSystem
from jev_comparison import JevComparison
from dashboard_state import DashboardReader, StatePublisher


class Handler(BaseHTTPRequestHandler):
    system: BTCSystem
    jev: JevComparison
    dashboard: StatePublisher

    def log_message(self, fmt, *args):
        print("[btc-workbench]", fmt % args, flush=True)

    def _json(self, status: int, payload):
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path: Path, mime: str):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/btc/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/btc/style.css": ("style.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
        }
        try:
            if path == "/api/health":
                self._json(200, {"project": "btc-decision-map", "version": "0.1.0"})
            elif path in files:
                filename, mime = files[path]
                self._file(ROOT / "apps" / "btc" / filename, mime)
            elif path == "/api/btc/state":
                self._json(*self.dashboard.response())
            elif path == "/api/btc/events":
                q = parse_qs(parsed.query)
                after = max(0, int(q.get("after", ["0"])[0]))
                limit = min(300, max(1, int(q.get("limit", ["100"])[0])))
                self._json(200, self.system.events_after(after, limit))
            elif path == "/api/btc/round":
                q = parse_qs(parsed.query)
                start = float(q.get("start", ["0"])[0])
                row = self.system.round_detail(start)
                if row:
                    row["round"]["jev"] = self.jev.detail(start)
                self._json(200 if row else 404, row or {"error": "round_not_found"})
            elif path == "/api/btc/export":
                payload = self.system.export()
                decisions = {r["start"]: r for r in self.jev.export()}
                for round_row in payload["rounds"]:
                    round_row["jev"] = decisions.get(round_row["start"])
                payload["jev_decisions"] = list(decisions.values())
                self._json(200, payload)
            elif path == "/api/market":
                self._json(200, market.CACHE.snapshot())
            else:
                self._json(404, {"error": "not_found"})
        except (BrokenPipeError, ConnectionResetError):
            # A closed browser connection cannot accept a second error reply.
            return
        except (ValueError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            self._json(500, {"error": f"本机服务错误: {exc}"})

    def do_POST(self):
        if urlparse(self.path).path != "/api/btc/jev/retry":
            self._json(404, {"error": "not_found"})
            return
        expected_origin = f"http://127.0.0.1:{self.server.server_port}"
        if (self.headers.get("Origin") != expected_origin or
                self.headers.get("Content-Type", "").split(";")[0] != "application/json"):
            self._json(403, {"error": "same_origin_json_required"})
            return
        self._json(200, self.jev.request_retry())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    lock_path = DATA_DIR / "btc-workbench.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = lock_path.open("w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise SystemExit("BTC 工作台已有一个本机实例在运行") from exc
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    Handler.system = BTCSystem(market.CACHE)
    Handler.jev = JevComparison(Handler.system.db_path)
    reader = DashboardReader(Handler.system, Handler.jev)
    Handler.dashboard = StatePublisher(reader.snapshot)
    threading.Thread(target=market.CACHE.poll_forever, daemon=True, name="kraken-public-cache").start()
    threading.Thread(target=Handler.system.run, daemon=True, name="btc-decision-engine").start()
    threading.Thread(target=Handler.jev.run, daemon=True, name="jev-remote-comparison").start()
    Handler.dashboard.start()
    print(f"BTC Decision Workbench: http://127.0.0.1:{args.port}", flush=True)
    import signal
    def shutdown(signum, frame):
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        server.serve_forever()
    finally:
        server.server_close()
        with Handler.system.lock:
            Handler.system.db.execute("PRAGMA wal_checkpoint(PASSIVE)")
        lock_file.close()
