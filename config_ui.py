"""Local-only configuration UI; no credential ever returned to the browser."""
import html
import json
import os
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from runtime_config import ENV_FILE, read_env

PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BTC 本机配置</title>
<style>body{background:#0b1f29;color:#dbfff5;font:18px system-ui;max-width:660px;margin:50px auto;padding:24px}input,button{font:inherit;padding:12px;box-sizing:border-box}input[type=password],input[type=number]{display:block;width:100%;margin:10px 0 24px}button{background:#72e6ca;border:0;border-radius:8px;cursor:pointer}small{display:block;color:#a4bec6;margin:10px 0 24px}label{display:block;margin-top:20px}#result{white-space:pre-wrap;color:#ffd486}</style>
<h1>BTC 决策地图 · 本机配置</h1><p>Laya 和公开行情无需 API Key。Jev 使用你自己的云端额度，启用后会实际调用。</p>
<form id="form"><label><input id="enabled" type="checkbox"> 启用 Jev（会消耗自己的额度）</label>
<label for="key">Gateway Key</label><input id="key" type="password" autocomplete="off" placeholder="有现存 Key 时，留空即可保留"><small id="key-status"></small>
<label><input id="clear" type="checkbox"> 删除本机已保存的 Key</label>
<label for="limit">Jev 累计请求上限</label><input id="limit" type="number" min="1" max="10000" value="60"><small>本版配置入口要求 1–10000。达到上限后停止新请求；费用及剩余额度以提供方账户为准。</small>
<label for="port">工作台端口</label><input id="port" type="number" min="1024" max="65535" value="8780">
<button>保存本机配置</button></form><p id="result"></p>
<script>const token=__TOKEN__;fetch('/status').then(r=>r.json()).then(s=>{document.querySelector('#enabled').checked=s.enabled;document.querySelector('#limit').value=s.max_calls;document.querySelector('#port').value=s.port;document.querySelector('#key-status').textContent=s.key_configured?'已保存 Key。页面不回显密钥。':'尚未配置 Key。'});
document.querySelector('#form').onsubmit=async e=>{e.preventDefault();let data={enabled:document.querySelector('#enabled').checked,key:document.querySelector('#key').value,clear_key:document.querySelector('#clear').checked,max_calls:Number(document.querySelector('#limit').value),port:Number(document.querySelector('#port').value)};try{let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json','X-Setup-Token':token},body:JSON.stringify(data)});let s=await r.json();document.querySelector('#result').textContent=s.message;document.querySelector('#key').value='';}catch(e){document.querySelector('#result').textContent='保存失败，请检查本机配置程序是否仍在运行。'}};</script></html>'''

def save_config(payload, path=ENV_FILE):
    port, limit = int(payload["port"]), int(payload["max_calls"])
    if not 1024 <= port <= 65535 or not 1 <= limit <= 10000:
        raise ValueError("端口或调用上限超出范围")
    values = read_env(path)
    if payload.get("clear_key"):
        values["AI_GATEWAY_API_KEY"] = ""
    elif payload.get("key", "").strip():
        values["AI_GATEWAY_API_KEY"] = payload["key"].strip()
    if payload.get("enabled") and not values.get("AI_GATEWAY_API_KEY"):
        raise ValueError("启用 Jev 前请填写自己的 Key，或先关闭 Jev")
    values.update(BTC_PORT=str(port), JEV_MAX_CALLS=str(limit),
                  JEV_ENABLED="true" if payload.get("enabled") else "false")
    values.setdefault("BTC_DATA_DIR", "data")
    values.setdefault("LAYA_MODEL_DIR", "models/laya")
    temporary = path.with_suffix(".pending")
    try:
        descriptor = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(descriptor,"w") as stream:
            for name in ("BTC_PORT","BTC_DATA_DIR","LAYA_MODEL_DIR","JEV_ENABLED","JEV_MAX_CALLS","AI_GATEWAY_API_KEY"):
                stream.write(name+"="+json.dumps(values.get(name,""),ensure_ascii=False)+"\n")
        os.replace(temporary,path)
        os.chmod(path,0o600)
    finally:
        temporary.unlink(missing_ok=True)

class ConfigHandler(BaseHTTPRequestHandler):
    token = ""
    def log_message(self,*args):
        pass
    def reply(self,status,body,mime="application/json; charset=utf-8"):
        data=body.encode() if isinstance(body,str) else json.dumps(body,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type",mime)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers();self.wfile.write(data)
    def valid_host(self):
        return self.headers.get("Host")==f"127.0.0.1:{self.server.server_port}"
    def do_GET(self):
        if not self.valid_host():
            return self.reply(403,{"message":"仅允许本机访问"})
        if self.path=="/":
            return self.reply(200,PAGE.replace("__TOKEN__",json.dumps(self.token)),"text/html; charset=utf-8")
        if self.path=="/status":
            values=read_env()
            return self.reply(200,{"enabled":values.get("JEV_ENABLED")=="true",
                "key_configured":bool(values.get("AI_GATEWAY_API_KEY")),
                "max_calls":values.get("JEV_MAX_CALLS","60"),"port":values.get("BTC_PORT","8780")})
        self.reply(404,{"message":"未找到"})
    def do_POST(self):
        origin=f"http://127.0.0.1:{self.server.server_port}"
        if (not self.valid_host() or self.headers.get("Origin")!=origin or
            self.headers.get("X-Setup-Token")!=self.token or
            self.headers.get("Content-Type","").split(';')[0]!="application/json"):
            return self.reply(403,{"message":"仅允许本机配置页保存"})
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0<length<=4096 or self.path!="/save":
                raise ValueError("请求无效")
            save_config(json.loads(self.rfile.read(length)))
        except (ValueError,KeyError,TypeError):
            return self.reply(400,{"message":"配置无效：请检查 Key、端口和调用上限。"})
        except OSError:
            return self.reply(500,{"message":"无法保存：请检查项目目录写入权限。"})
        self.reply(200,{"message":"已保存到本机。请先停止并重新启动工作台，使新配置生效。可以关闭这个配置窗口。"})

if __name__=="__main__":
    ConfigHandler.token=secrets.token_urlsafe(32)
    server=ThreadingHTTPServer(("127.0.0.1",0),ConfigHandler)
    url=f"http://127.0.0.1:{server.server_port}/"
    print("本机配置页："+url,flush=True)
    webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
