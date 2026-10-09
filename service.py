"""Start/stop this checkout only. No global service installation."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from runtime_config import ROOT, DATA_DIR, MODEL_DIR, PORT, read_env

PID_FILE=DATA_DIR/"server.json"

def owned_process(record):
    try:
        output=subprocess.check_output(["ps","-p",str(record["pid"]),"-o","command="],text=True).strip()
        return str(ROOT/"workbench.py") in output
    except (subprocess.CalledProcessError,KeyError):
        return False

def read_record():
    try: return json.loads(PID_FILE.read_text())
    except (OSError,ValueError): return {}

def probe(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health",timeout=2) as response:
            return json.load(response).get("project")=="btc-decision-map"
    except Exception: return False

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["start","stop","status"])
    parser.add_argument("--open",action="store_true")
    args=parser.parse_args()
    record=read_record()
    active=owned_process(record)
    if args.action=="stop":
        if active:
            os.kill(record["pid"],signal.SIGTERM)
            for _ in range(50):
                if not owned_process(record): break
                time.sleep(.1)
            if owned_process(record):
                raise SystemExit("程序仍未退出，请保留记录并检查。")
        PID_FILE.unlink(missing_ok=True)
        print("本目录工作台已停止，数据保留。")
        return
    if args.action=="status":
        print(json.dumps({"running":active,"http_ready":probe(record.get("port",PORT)) if active else False,
                          "port":record.get("port",PORT)},ensure_ascii=False))
        return
    if active:
        if record.get("port")!=PORT:
            raise SystemExit("工作台正在使用旧端口，请先运行 stop.command 再启动。")
        print(f"本目录已运行：http://127.0.0.1:{PORT}/")
        if args.open: webbrowser.open(f"http://127.0.0.1:{PORT}/")
        return
    python=ROOT/".venv/bin/python"
    if not python.is_file() or not (MODEL_DIR/"verified-revision.json").is_file():
        raise SystemExit("安装或模型校验未完成。请先运行 setup.command。")
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1",PORT))==0:
            raise SystemExit("端口已被其他程序占用。请在 configure.command 修改端口。")
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ)
    for key in ("AI_GATEWAY_API_KEY","JEV_ENV_FILE","JEV_ENABLED","JEV_MAX_CALLS"):
        env.pop(key,None)
    env.update(read_env())
    env["HF_HUB_OFFLINE"]="1"
    with (DATA_DIR/"workbench.log").open("a") as log:
        process=subprocess.Popen([str(python),str(ROOT/"workbench.py"),"--port",str(PORT)],
            cwd=ROOT,env=env,stdout=log,stderr=log,start_new_session=True)
    PID_FILE.write_text(json.dumps({"pid":process.pid,"port":PORT}))
    for _ in range(100):
        if process.poll() is not None:
            raise SystemExit("启动失败，真实错误保存在 data/workbench.log。")
        if probe(PORT):
            print(f"工作台已启动：http://127.0.0.1:{PORT}/；新行情窗口约需 60 秒。")
            if args.open: webbrowser.open(f"http://127.0.0.1:{PORT}/")
            return
        time.sleep(.2)
    raise SystemExit("服务仍在准备，请查看 data/workbench.log 和 status。")

if __name__=="__main__": main()
