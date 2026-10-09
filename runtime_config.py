"""Portable local configuration. Secret values never enter status output."""
from pathlib import Path
import json
import os

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
MODEL_ID = "aac6fef/laya-multilingual-mlx"
MODEL_REVISION = "f2b4faf51023039425946074e2cf1361d2db11d5"

def read_env(path=ENV_FILE):
    result = {}
    if Path(path).is_file():
        for line in Path(path).read_text().splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name and not name.startswith("#"):
                value = value.strip()
                if value.startswith('"'):
                    try:
                        value = json.loads(value)
                    except ValueError:
                        raise ValueError("本机配置格式错误，请重新保存配置") from None
                result[name.strip()] = value
    return result

def setting(name, default=""):
    return os.environ.get(name, read_env().get(name, default))

def local_path(name, default):
    path = Path(setting(name, default)).expanduser()
    return path if path.is_absolute() else ROOT / path

DATA_DIR = local_path("BTC_DATA_DIR", "data")
MODEL_DIR = local_path("LAYA_MODEL_DIR", "models/laya")
PORT = int(setting("BTC_PORT", "8780"))
if not 1024 <= PORT <= 65535:
    raise ValueError("BTC_PORT 应在 1024–65535 之间")

def apply_runtime_env():
    values = read_env()
    for name in ("JEV_ENABLED", "JEV_MAX_CALLS", "AI_GATEWAY_API_KEY"):
        if name in values:
            os.environ.setdefault(name, values[name])
    os.environ.setdefault("JEV_MAX_CALLS", "60")
    os.environ.setdefault("JEV_ENABLED", "false")
