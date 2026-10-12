#!/bin/bash
# ZJNU 体育场馆预约 - 快捷启动脚本
#
# 用法:
#   ./run.sh              # 立即预约明天场地
#   ./run.sh --loop       # 等到 07:00 准时抢
#   ./run.sh --scan       # 只看不约
#   ./run.sh --setup      # 重新配置
#
# 环境有问题? 先跑 ./check_env.sh

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ── 定位虚拟环境 ──
# Linux/macOS 用 <venv>/bin/activate，Windows(Git Bash) 用 <venv>/Scripts/activate
VENV=""
ACTIVATE=""
for d in venv .venv; do
    if [ -f "$d/bin/activate" ]; then
        VENV="$d"; ACTIVATE="$d/bin/activate"; break
    elif [ -f "$d/Scripts/activate" ]; then
        VENV="$d"; ACTIVATE="$d/Scripts/activate"; break
    fi
done

if [ -z "$VENV" ]; then
    echo "错误: 未找到虚拟环境 (venv/ 或 .venv/)" >&2
    echo "" >&2
    echo "请先创建并安装依赖:" >&2
    echo "  python3 -m venv venv" >&2
    echo "  venv/bin/pip install -r badminton-booking/requirements.txt \\" >&2
    echo "      -i https://pypi.tuna.tsinghua.edu.cn/simple" >&2
    echo "" >&2
    echo "若创建时报 \"ensurepip is not available\"，运行 ./check_env.sh --fix" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$ACTIVATE"

# ── 运行前的最小健全性检查 ──
# 只做最关键的检查，完整的自检交给 ./check_env.sh
if ! command -v node >/dev/null 2>&1; then
    echo "错误: 未找到 node —— 登录需要它执行密码加密 (ez.js)" >&2
    echo "  Debian/Ubuntu: sudo apt install -y nodejs" >&2
    echo "  CentOS/Fedora: sudo dnf install -y nodejs" >&2
    exit 1
fi

exec python badminton-booking/main.py "$@"
