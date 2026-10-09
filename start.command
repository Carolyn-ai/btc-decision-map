#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "请先运行 setup.command 完成安装。"
  exit 1
fi
exec .venv/bin/python service.py start --open "$@"
