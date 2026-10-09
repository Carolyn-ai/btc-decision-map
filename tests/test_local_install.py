import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import http.client
from http.server import ThreadingHTTPServer
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config_ui import save_config, ConfigHandler
from runtime_config import read_env

class LocalConfigTest(unittest.TestCase):
    def test_configuration_http_hides_key_and_rejects_foreign_origin(self):
        handler=type('TestConfigHandler',(ConfigHandler,),{'token':'test-setup-token'})
        server=ThreadingHTTPServer(('127.0.0.1',0),handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        secret='fixture-private-value'
        with patch('config_ui.read_env',return_value={'AI_GATEWAY_API_KEY':secret}), patch('config_ui.save_config') as save:
            thread.start()
            try:
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                conn.request('GET','/status')
                response=conn.getresponse();body=response.read().decode()
                self.assertEqual(response.status,200)
                self.assertNotIn(secret,body)
                self.assertTrue(json.loads(body)['key_configured'])
                headers={'Content-Type':'application/json','X-Setup-Token':handler.token,'Origin':'https://foreign.example'}
                conn.request('POST','/save',body='{}',headers=headers)
                response=conn.getresponse();response.read()
                self.assertEqual(response.status,403);save.assert_not_called()
                headers['Origin']=f'http://127.0.0.1:{server.server_port}'
                conn.request('POST','/save',body='{}',headers=headers)
                response=conn.getresponse();response.read()
                self.assertEqual(response.status,200);save.assert_called_once_with({})
                conn.close()
            finally:
                server.shutdown();thread.join();server.server_close()

    def test_save_never_clears_existing_key_when_password_left_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'.env'
            payload={"port":8780,"max_calls":2,"enabled":True,"key":"fixture-not-a-real-key"}
            save_config(payload,path)
            save_config({**payload,"key":"","max_calls":3},path)
            self.assertEqual(read_env(path)["AI_GATEWAY_API_KEY"],payload["key"])
            self.assertEqual(read_env(path)["JEV_MAX_CALLS"],"3")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o600)
            save_config({**payload,"key":"","enabled":False,"clear_key":True},path)
            self.assertEqual(read_env(path)["AI_GATEWAY_API_KEY"],"")

    def test_enabling_requires_key_and_finite_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'.env'
            base={"port":8780,"max_calls":2,"enabled":True,"key":""}
            with self.assertRaises(ValueError): save_config(base,path)
            with self.assertRaises(ValueError): save_config({**base,"key":"fixture","max_calls":0},path)
            self.assertFalse(path.exists())

    def test_provider_is_disabled_by_default_even_if_environment_has_a_key(self):
        from workbench import JevComparison
        import jev_comparison
        with patch.dict(os.environ,{"AI_GATEWAY_API_KEY":"fixture","JEV_ENABLED":"false"}):
            self.assertIsNone(jev_comparison.load_key())

if __name__=="__main__":unittest.main()
