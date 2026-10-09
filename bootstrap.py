"""Install the project in its own environment; safe to resume."""
import argparse
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-model", action="store_true", help="Prepare dependencies only; not a complete installation")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise SystemExit("本版支持 Apple 芯片 Mac。请使用支持的电脑，不以模拟模型代替。")
    if tuple(map(int, platform.mac_ver()[0].split('.')[:1])) < (14,):
        raise SystemExit("需要 macOS 14 或更新版本")
    if not (3, 11) <= sys.version_info < (3, 14):
        raise SystemExit("需要 Python 3.11–3.13，推荐 Python 3.12。")
    if shutil.disk_usage(ROOT).free < 2 * 1024**3:
        raise SystemExit("可用磁盘不足 2 GB，请先准备安装空间。")
    env = ROOT / ".venv"
    if env.is_symlink():
        raise SystemExit(".venv 是外部链接，请使用新的独立安装目录。")
    python = env / "bin/python"
    usable = python.exists() and subprocess.run(
        [str(python), "-m", "pip", "--version"], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL).returncode == 0
    if not usable:
        print("正在创建项目独立环境…", flush=True)
        venv.EnvBuilder(with_pip=True, symlinks=True).create(env)
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
    if not (ROOT / ".env").exists():
        with (ROOT / ".env").open("x") as stream:
            stream.write((ROOT / ".env.example").read_text())
        os.chmod(ROOT / ".env", 0o600)
    if args.skip_model:
        print("依赖准备完成；模型尚未下载和验证。")
        return
    subprocess.run([str(python), str(ROOT / "scripts/download_model.py")], check=True)
    subprocess.run([str(python), str(ROOT / "scripts/doctor.py"), "--model", "--market"], check=True)
    print("安装和检查通过。运行 ./start.command；配置 Jev 可运行 ./configure.command。")

if __name__ == "__main__":
    main()
