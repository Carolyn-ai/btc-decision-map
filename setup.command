#!/bin/zsh
set -e
cd "$(dirname "$0")"
for candidate in python3.12 python3.13 python3; do
  if command -v "$candidate" >/dev/null && "$candidate" -c "import sys; assert (3,12) <= sys.version_info < (3,14)" 2>/dev/null; then
    exec "$candidate" bootstrap.py "$@"
  fi
done
echo "未找到 Python 3.12–3.13。请让 ChatGPT 安装 Python 3.12 后重试。"
exit 1
