"""Report real local health. Never sends paid model requests."""
import argparse
import importlib.metadata
import json
import os
import platform
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_config import DATA_DIR, MODEL_DIR, MODEL_ID, MODEL_REVISION, PORT, setting

def check_model():
    receipt = json.loads((MODEL_DIR / "verified-revision.json").read_text())
    if receipt.get("revision") != MODEL_REVISION:
        raise ValueError("模型下载校验尚未完成，请运行 setup.command")
    os.environ["HF_HUB_OFFLINE"] = "1"
    import laya_mlx as laya
    started = time.perf_counter()
    agent = laya.load(str(MODEL_DIR), dtype="float16", batch_size=16)
    loaded = time.perf_counter()
    answer = agent.predict("客户说发票重复扣款，请退款。", {
        "department": {"type": "choice", "instructions": "应该由哪个团队处理？",
                       "criteria": ["billing", "technical", "sales"]}})["answers"]["department"]
    if answer.get("choice") not in ("billing", "technical", "sales"):
        raise ValueError("真实模型输出未通过结构检查")
    return {"status": "PASS", "model": MODEL_ID, "revision": MODEL_REVISION,
            "choice": answer["choice"], "load_ms": round((loaded-started)*1000, 2),
            "inference_ms": round((time.perf_counter()-loaded)*1000, 2)}

def check_market():
    url = "https://api.kraken.com/0/public/Trades?pair=XBTUSD&count=10"
    started = time.perf_counter()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "BTCDecisionMap/0.1"}), timeout=15) as response:
        payload = json.load(response)
    if payload.get("error"):
        raise ValueError("Kraken: " + ", ".join(payload["error"]))
    trades = next(v for k,v in payload["result"].items() if k != "last")
    if not trades:
        raise ValueError("交易所返回空成交列表")
    age = time.time() - float(trades[-1][2])
    if not -2 <= age < 30:
        raise ValueError(f"公开成交过旧或时钟异常，age={age:.1f}s")
    return {"status": "PASS", "source": "Kraken", "count": len(trades),
            "latest_price": float(trades[-1][0]), "age_s": round(age,2),
            "latency_ms": round((time.perf_counter()-started)*1000,2)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="store_true")
    parser.add_argument("--market", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    checks = {"platform": {"status": "PASS" if platform.system()=="Darwin" and platform.machine()=="arm64" else "UNSUPPORTED", "system": platform.system(), "chip": platform.machine()},
              "python": {"status": "PASS" if (3,11)<=sys.version_info<(3,14) else "UNSUPPORTED", "version": platform.python_version()},
              "jev": {"status": "NOT_CALLED", "enabled": setting("JEV_ENABLED", "false")=="true", "key_configured": bool(setting("AI_GATEWAY_API_KEY")), "max_calls": setting("JEV_MAX_CALLS", "60")}}
    for name in ("laya-mlx", "mlx"):
        try:
            checks[name] = {"status": "PASS", "version": importlib.metadata.version(name)}
        except importlib.metadata.PackageNotFoundError:
            checks[name] = {"status": "MISSING"}
    jobs = []
    if args.model: jobs.append(("model",check_model))
    if args.market: jobs.append(("market",check_market))
    if args.live:
        def live():
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/btc/state",timeout=10) as r:
                state=json.load(r)
            return {"status":"PASS", "server_time":state.get("server_time"), "health":state.get("health"), "signal_count":len(state.get("signal",{}).get("rounds",[]))}
        jobs.append(("workbench",live))
    for name, job in jobs:
        try:
            checks[name] = job()
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            key = setting("AI_GATEWAY_API_KEY")
            checks[name] = {"status": "FAIL", "error": message.replace(key,"[REDACTED]") if key else message}
    report = {"checked_at":time.time(), "checks":checks}
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    (DATA_DIR/"doctor-last.json").write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
    if any(v["status"] in ("FAIL","MISSING","UNSUPPORTED") for v in checks.values()):
        raise SystemExit(1)

if __name__ == "__main__":
    main()
