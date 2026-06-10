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
if [ -f venv/bin/activate ]; then
    source venv/bin/activate
elif [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

exec python badminton-booking/main.py "$@"