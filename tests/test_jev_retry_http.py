import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workbench import Handler


class RetryHTTPTest(unittest.TestCase):
    def test_only_same_origin_json_can_resume(self):
        fake = Mock()
        fake.request_retry.return_value = {"status": "waiting_for_future_snapshot"}
        handler = type("TestHandler", (Handler,), {"jev": fake, "log_message": lambda *args: None})
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f"http://127.0.0.1:{server.server_port}"
        try:
            for attempted_origin in ("https://unrelated.example", origin):
                req = urllib.request.Request(origin + "/api/btc/jev/retry", data=b"{}",
                    headers={"Origin": attempted_origin, "Content-Type": "application/json"})
                if attempted_origin != origin:
                    with self.assertRaises(urllib.error.HTTPError) as failure:
                        urllib.request.urlopen(req)
                    self.assertEqual(failure.exception.code, 403)
                    fake.request_retry.assert_not_called()
                else:
                    with urllib.request.urlopen(req) as response:
                        self.assertEqual(json.load(response)["status"], "waiting_for_future_snapshot")
                    fake.request_retry.assert_called_once()
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
