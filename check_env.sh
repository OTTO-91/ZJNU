#!/bin/bash
# ZJNU 体育场馆预约 - 环境自检脚本
#
# 用法:
#   ./check_env.sh          只检查，不改动系统
#   ./check_env.sh --fix    检查并自动安装缺失的依赖（需要 sudo 时会询问）
#   ./check_env.sh --help   显示帮助
#
# 支持: Debian/Ubuntu、CentOS/RHEL/Fedora、Arch、Alpine、macOS、Git Bash
#
# 说明: 本脚本刻意不使用 `set -e`。它的职责就是暴露问题，
#       任何单项检查失败都必须继续往下跑，而不是中途退出。

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1

FIX_MODE=0
for arg in "$@"; do
    case "$arg" in
        --fix)  FIX_MODE=1 ;;
        --help|-h)
            sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "未知参数: $arg（可用: --fix / --help）" >&2
            exit 2
            ;;
    esac
done

# ── 输出样式 ──
# 只用 ASCII 标记，避免在 GBK 控制台（Windows Git Bash）出现乱码
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C_OK=$'\033[32m'; C_BAD=$'\033[31m'; C_WARN=$'\033[33m'
    C_DIM=$'\033[2m'; C_OFF=$'\033[0m'
else
    C_OK=''; C_BAD=''; C_WARN=''; C_DIM=''; C_OFF=''
fi

ok()   { printf '  %s[ OK ]%s %s\n' "$C_OK"   "$C_OFF" "$1"; }
bad()  { printf '  %s[FAIL]%s %s\n' "$C_BAD"  "$C_OFF" "$1"; }
warn() { printf '  %s[WARN]%s %s\n' "$C_WARN" "$C_OFF" "$1"; }
note() { printf '  %s[ -- ]%s %s\n' "$C_DIM"  "$C_OFF" "$1"; }
head_() { printf '\n%s\n' "$1"; }

FAILED=0
FIXES=""
add_fix() {
    FAILED=1
    case "$FIXES" in
        *"$1"*) ;;
        *) FIXES="${FIXES}${1}
" ;;
    esac
}

# ── 平台与包管理器 ──
UNAME_S="$(uname -s 2>/dev/null || echo unknown)"
case "$UNAME_S" in
    Linux)                PLATFORM=linux ;;
    Darwin)               PLATFORM=macos ;;
    MINGW*|MSYS*|CYGWIN*) PLATFORM=gitbash ;;
    *)                    PLATFORM=unknown ;;
esac

if [ "$(id -u 2>/dev/null || echo 1)" = "0" ]; then SUDO=""; else SUDO="sudo "; fi

PM=""
if   command -v apt-get >/dev/null 2>&1; then PM=apt
elif command -v dnf     >/dev/null 2>&1; then PM=dnf
elif command -v yum     >/dev/null 2>&1; then PM=yum
elif command -v pacman  >/dev/null 2>&1; then PM=pacman
elif command -v apk     >/dev/null 2>&1; then PM=apk
elif command -v brew    >/dev/null 2>&1; then PM=brew
fi

printf '%s\n' "=================================================="
printf '%s\n' "  ZJNU 体育场馆预约 - 环境自检"
printf '%s\n' "=================================================="
note "系统: $UNAME_S   包管理器: ${PM:-未识别}   身份: $( [ -z "$SUDO" ] && echo root || echo 普通用户 )"

# ── 1. Python 3 ──
head_ "[1/7] Python 3"

# 逐个候选解释器实测，而不是只看 `command -v`。
# Windows 上 python3 常是 Microsoft Store 的占位存根：命令存在但不产生任何输出。
# 若只判断命令是否存在，会把存根误当成可用的解释器。
PY=""
PY_VER=""
for c in python3 python; do
    command -v "$c" >/dev/null 2>&1 || continue
    v="$("$c" -c 'import sys;print("%d.%d.%d"%sys.version_info[:3])' 2>/dev/null)"
    case "$v" in
        [0-9]*.[0-9]*.[0-9]*) PY="$c"; PY_VER="$v"; break ;;
        *) continue ;;
    esac
done

if [ -z "$PY" ]; then
    bad "未找到 python3"
    case "$PM" in
        apt)    add_fix "${SUDO}apt update && ${SUDO}apt install -y python3 python3-pip python3-venv" ;;
        dnf)    add_fix "${SUDO}dnf install -y python3 python3-pip" ;;
        yum)    add_fix "${SUDO}yum install -y python3 python3-pip" ;;
        pacman) add_fix "${SUDO}pacman -S --noconfirm python" ;;
        apk)    add_fix "${SUDO}apk add python3 py3-pip" ;;
        brew)   add_fix "brew install python3" ;;
        *)      add_fix "请先安装 Python 3.8 或更高版本" ;;
    esac
else
    PYPATH="$(command -v "$PY")"
    if "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' 2>/dev/null; then
        ok "Python $PY_VER  ($PYPATH)"
    else
        bad "Python 版本过低: $PY_VER（需要 3.8+）"
        add_fix "请升级到 Python 3.8 或更高版本"
    fi
fi

# 供第 2 步拼包名用（如 python3.12-venv）。未识别到 Python 时留空，
# 避免拼出 "python-venv" 这种不存在的包名。
PYMAJMIN=""
if [ -n "$PY" ]; then
    PYMAJMIN="$("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)"
fi

# ── 2. venv / ensurepip ──
# 这一项对应报错 "The virtual environment was not created successfully
# because ensurepip is not available" —— Debian/Ubuntu 把 venv 拆成了独立包
head_ "[2/7] venv 与 ensurepip（创建虚拟环境的能力）"

VENV_FIX=""
if [ -n "$PYMAJMIN" ]; then
    APT_VENV="${SUDO}apt install -y python${PYMAJMIN}-venv"
else
    APT_VENV="${SUDO}apt install -y python3-venv"
fi
case "$PM" in
    apt)    VENV_FIX="${SUDO}apt update && (${APT_VENV} || ${SUDO}apt install -y python3-venv)" ;;
    dnf)    VENV_FIX="${SUDO}dnf install -y python3-pip" ;;
    yum)    VENV_FIX="${SUDO}yum install -y python3-pip" ;;
    pacman) VENV_FIX="${SUDO}pacman -S --noconfirm python" ;;
    apk)    VENV_FIX="${SUDO}apk add python3 py3-pip" ;;
    brew)   VENV_FIX="brew install python3" ;;
    *)      VENV_FIX="请安装 python3-venv 对应的系统包" ;;
esac

if [ -n "$PY" ]; then
    if "$PY" -c 'import venv' >/dev/null 2>&1; then
        ok "venv 模块可用"
    else
        bad "venv 模块缺失 —— 无法创建虚拟环境"
        add_fix "$VENV_FIX"
    fi

    if "$PY" -c 'import ensurepip' >/dev/null 2>&1; then
        ok "ensurepip 可用"
    else
        bad "ensurepip 缺失 —— 这正是 \"ensurepip is not available\" 报错的原因"
        add_fix "$VENV_FIX"
    fi
else
    note "无 Python，无法检测 venv / ensurepip（先完成第 1 步）"
fi

# ── 3. 虚拟环境与依赖 ──
head_ "[3/7] 项目虚拟环境与依赖"

VENV=""
for d in venv .venv; do
    if [ -f "$d/bin/activate" ]; then VENV="$d"; break; fi
    if [ -f "$d/Scripts/activate" ]; then VENV="$d"; break; fi
done

if [ -z "$VENV" ]; then
    warn "尚未创建虚拟环境（venv/ 或 .venv/ 都不存在）"
    note "创建命令: $PY -m venv venv"
    if [ -n "$PY" ]; then
        if "$PY" -c 'import venv, ensurepip' >/dev/null 2>&1; then
            note "前置条件已满足，可以直接创建"
        else
            add_fix "$VENV_FIX"
        fi
    fi
else
    VPY="$VENV/bin/python"
    [ -x "$VPY" ] || VPY="$VENV/Scripts/python.exe"

    if [ -x "$VPY" ]; then
        ok "虚拟环境存在: $VENV/"
        if "$VPY" -m pip --version >/dev/null 2>&1; then
            ok "pip 可用: $("$VPY" -m pip --version 2>/dev/null | cut -d' ' -f1-2)"
        else
            bad "虚拟环境里的 pip 不可用（环境创建不完整）"
            note "修复: rm -rf $VENV && $PY -m venv $VENV"
            add_fix "rm -rf $VENV && $PY -m venv $VENV"
        fi

        MISSING="$("$VPY" - <<'PYEOF' 2>/dev/null
import importlib.util as u
mods = [("requests","requests"),("execjs","PyExecJS"),("bs4","beautifulsoup4"),("lxml","lxml")]
print(" ".join(pkg for mod,pkg in mods if u.find_spec(mod) is None))
PYEOF
)"
        if [ -z "$MISSING" ]; then
            ok "Python 依赖已装齐 (requests / PyExecJS / beautifulsoup4 / lxml)"
        else
            bad "缺少依赖: $MISSING"
            add_fix "$VPY -m pip install -r badminton-booking/requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple"
        fi
    else
        bad "虚拟环境目录存在但 Python 解释器缺失: $VENV/"
        add_fix "rm -rf $VENV && $PY -m venv $VENV"
    fi
fi

# ── 4. Node.js ──
head_ "[4/7] Node.js（PyExecJS 依赖，缺了会直接崩）"

if command -v node >/dev/null 2>&1; then
    ok "Node.js $(node --version 2>/dev/null)  ($(command -v node))"
else
    bad "未找到 node —— 脚本导入 auth.py 时会抛 RuntimeUnavailableError"
    case "$PM" in
        apt)    add_fix "${SUDO}apt install -y nodejs" ;;
        dnf)    add_fix "${SUDO}dnf install -y nodejs" ;;
        yum)    add_fix "${SUDO}yum install -y nodejs" ;;
        pacman) add_fix "${SUDO}pacman -S --noconfirm nodejs" ;;
        apk)    add_fix "${SUDO}apk add nodejs" ;;
        brew)   add_fix "brew install node" ;;
        *)      add_fix "请安装 Node.js: https://nodejs.org/" ;;
    esac
fi

# ── 5. 时区 ──
head_ "[5/7] 系统时区（错了不会报错，但会抢错时间）"

if [ "$PLATFORM" = "linux" ]; then
    TZOFF="$(date +%z 2>/dev/null)"
    TZNAME="$(date +%Z 2>/dev/null)"
    if [ "$TZOFF" = "+0800" ]; then
        ok "时区为北京时间 ($TZNAME $TZOFF)"
    else
        bad "当前时区 $TZNAME $TZOFF，不是 +0800"
        note "脚本用本机时钟卡 07:00，时区错会导致在错误的时间触发"
        if command -v timedatectl >/dev/null 2>&1; then
            add_fix "${SUDO}timedatectl set-timezone Asia/Shanghai"
        else
            add_fix "echo 'Asia/Shanghai' | ${SUDO}tee /etc/timezone && ${SUDO}dpkg-reconfigure -f noninteractive tzdata"
        fi
    fi
elif [ "$PLATFORM" = "macos" ]; then
    TZOFF="$(date +%z 2>/dev/null)"
    if [ "$TZOFF" = "+0800" ]; then ok "时区为北京时间 (+0800)"; else warn "当前时区偏移 $TZOFF，建议设为 Asia/Shanghai"; fi
else
    note "Git Bash / 非 Linux 平台，跳过时区检查"
fi

# ── 6. 网络连通性 ──
head_ "[6/7] 网络连通性"

if [ -n "$PY" ]; then
    net_check() {
        "$PY" -c '
import sys, urllib.request, urllib.error
try:
    urllib.request.urlopen(sys.argv[1], timeout=8)
    print("ok")
except urllib.error.HTTPError:
    print("ok")          # 4xx/5xx 也说明网络是通的
except Exception:
    print("fail")
' "$1" 2>/dev/null
    }

    if [ "$(net_check https://tycg.zjnu.edu.cn)" = "ok" ]; then
        ok "场地预约系统可达 (tycg.zjnu.edu.cn)"
    else
        bad "无法访问 tycg.zjnu.edu.cn"
        note "校内系统，通常需要校园网或学校 VPN"
    fi

    if [ "$(net_check http://authserver.zjnu.edu.cn)" = "ok" ]; then
        ok "统一认证可达 (authserver.zjnu.edu.cn)"
    else
        bad "无法访问 authserver.zjnu.edu.cn"
        note "校外需连学校 VPN 才能登录"
    fi
else
    note "无 Python，跳过网络检查"
fi

# ── 7. 配置文件 ──
head_ "[7/7] 配置文件"

if [ -f badminton-booking/.env ]; then
    if grep -q '^ZJNU_USERNAME=' badminton-booking/.env 2>/dev/null; then
        ok "badminton-booking/.env 已配置"
        CAMPUS="$(grep '^ZJNU_CAMPUS=' badminton-booking/.env 2>/dev/null | cut -d= -f2)"
        SPORT="$(grep '^ZJNU_SPORT=' badminton-booking/.env 2>/dev/null | cut -d= -f2)"
        note "校区: ${CAMPUS:-未设置}   运动: ${SPORT:-未设置}"
        if grep -q '^SENDKEY=' badminton-booking/.env 2>/dev/null; then
            ok "已配置 Server酱推送"
        else
            note "未配置 SENDKEY（不推送微信，不影响抢场）"
        fi
    else
        bad "badminton-booking/.env 存在但缺少 ZJNU_USERNAME"
        add_fix "./run.sh --setup"
    fi
else
    warn "尚未配置账号（badminton-booking/.env 不存在）"
    add_fix "./run.sh --setup"
fi

if [ ! -f badminton-booking/main.py ]; then
    bad "找不到 badminton-booking/main.py —— 请在项目根目录运行本脚本"
fi

# ── 汇总 ──
printf '\n%s\n' "=================================================="
if [ "$FAILED" -eq 0 ]; then
    printf '  %s全部通过%s\n' "$C_OK" "$C_OFF"
    printf '%s\n' "=================================================="
    printf '\n下一步:\n'
    printf '  ./run.sh --scan      # 确认能拉到场地数据\n'
    exit 0
fi

printf '  %s发现问题，需要修复%s\n' "$C_BAD" "$C_OFF"
printf '%s\n' "=================================================="
printf '\n建议按顺序执行以下命令:\n\n'
printf '%s' "$FIXES" | while IFS= read -r line; do
    [ -n "$line" ] && printf '  %s\n' "$line"
done

if [ "$FIX_MODE" -eq 1 ]; then
    printf '\n是否现在自动执行以上命令? [y/N] '
    read -r ans
    case "$ans" in
        y|Y)
            printf '\n'
            printf '%s' "$FIXES" | while IFS= read -r line; do
                [ -z "$line" ] && continue
                printf '%s>>> %s%s\n' "$C_DIM" "$line" "$C_OFF"
                sh -c "$line" || printf '%s    命令失败，请手动处理%s\n' "$C_WARN" "$C_OFF"
            done
            printf '\n执行完毕。请重新运行 ./check_env.sh 确认。\n'
            ;;
        *) printf '已取消。\n' ;;
    esac
else
    printf '\n提示: 运行 ./check_env.sh --fix 可自动执行以上命令\n'
fi

exit 1
