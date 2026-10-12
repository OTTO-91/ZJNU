#!/bin/bash
# ZJNU 体育场馆预约 - 快捷启动脚本
# 用法:
#   ./run.sh              # 立即预约明天场地
#   ./run.sh --loop       # 等到 07:00 准时抢
#   ./run.sh --scan       # 只看不约
#   ./run.sh --setup      # 重新配置

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# 激活虚拟环境
# Linux/macOS 用 <venv>/bin/activate，Windows(Git Bash) 用 <venv>/Scripts/activate
for d in venv .venv; do
    if [ -f "$d/bin/activate" ]; then
        source "$d/bin/activate"
        break
    elif [ -f "$d/Scripts/activate" ]; then
        source "$d/Scripts/activate"
        break
    fi
done

exec python badminton-booking/main.py "$@"
