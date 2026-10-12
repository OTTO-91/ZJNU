# 浙师大体育场地自动预约 🏸

浙江师范大学（ZJNU）体育场地自动预约脚本。支持多校区、多运动项目，
**每天早上 7:00 准时抢场**。

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](badminton-booking/LICENSE)
[![Python 3.7+](https://img.shields.io/badge/Python-3.7%2B-blue)](https://python.org)

---

## 目录

**基础**

- [快速开始](#快速开始) —— 只想跑起来，看这一节就够
- [功能特性](#功能特性)
- [支持的场地](#支持的场地)
- [命令说明](#命令说明)
- [抢场原理](#抢场原理) · [触发精度](#触发精度) · [时段优先级](#时段优先级) · [账号上限](#账号预约上限)
- [配置项](#配置项)

**部署**

- [系统版本对照表](#系统版本对照表) —— **先查你的系统能不能用**
- [部署到 Linux 服务器](#部署到-linux-服务器)
  - [第 1 步：获取代码](#第-1-步获取代码)
  - [第 2 步：环境自检](#第-2-步环境自检)
  - [第 3 步：安装依赖](#第-3-步安装依赖)
  - [第 4 步：设置时区](#第-4-步设置时区) ⚠️
  - [第 5 步：创建虚拟环境](#第-5-步创建虚拟环境)
  - [第 6 步：配置账号](#第-6-步配置账号)
  - [第 7 步：试运行](#第-7-步试运行)
  - [第 8 步：配置定时任务](#第-8-步配置定时任务)
- [部署到 Windows](#部署到-windows)

**排错与参考**

- [常见问题](#常见问题) · [安装与环境](#安装与环境) · [运行与抢场](#运行与抢场) · [其他](#其他)
- [项目结构](#项目结构)
- [许可](#许可)

---

## 快速开始

> 适用于 **Linux 服务器**（Ubuntu / Debian 等）。Windows 见[部署到 Windows](#部署到-windows)。

```bash
git clone https://github.com/OTTO-91/ZJNU.git && cd ZJNU

./check_env.sh --fix     # 环境自检，缺什么自动装什么
./run.sh --setup         # 输入学号、密码、选校区
./run.sh --scan          # 能列出空场就成功了
```

最后配置定时任务：

```bash
crontab -e
```

```
55 6 * * * cd /root/ZJNU && ./run.sh --loop
```

> ⚠️ 是 **`55 6`** 不是 `0 7`。脚本需要 2~3 秒启动并预取数据，
> 07:00 才开始启动就晚了。详见[触发精度](#触发精度)。

[↑ 回到目录](#目录)

---

## 功能特性

| 特性 | 说明 |
|------|------|
| 🎯 **一次配置，永久运行** | 首次输入学号密码，之后全自动 |
| 🏫 **多校区** | 金华校区 / 萧山校区 |
| 🏃 **多运动** | 羽毛球 / 乒乓球 / 排球 |
| 🔐 **自动登录** | CAS 统一认证 + Token 自动提取与校验 |
| ⏱️ **精准抢场** | 6:55 预取数据，7:00:00 准时开抢 |
| 🔁 **自动兜底** | 首选时段被抢则自动降级重试 |
| 📱 **微信通知** | Server酱 推送预约结果 |
| 🔄 **会话保持** | Cookie + Token 持久化，重启无需重新登录 |

[↑ 回到目录](#目录)

---

## 支持的场地

| 校区 | 运动 | 场馆 | 场地 ID |
|------|------|------|---------|
| 金华 | 羽毛球 | 北田羽毛球馆 | 87 |
| 金华 | 羽毛球 | 综合馆羽毛球馆 | 84 |
| 金华 | 乒乓球 | 风雨操场乒乓球馆 | 86 |
| 金华 | 排球 | 风雨操场排球馆 | 85 |
| 萧山 | 羽毛球 | 萧山校区热身馆 | 92 |

> 萧山校区目前仅开放羽毛球。

[↑ 回到目录](#目录)

---

## 命令说明

| 命令 | 用途 |
|------|------|
| `./check_env.sh` | **环境自检**，逐项检查并给出修复命令 |
| `./check_env.sh --fix` | 自检并自动执行修复 |
| `./run.sh` | 立即预约明天场地 |
| `./run.sh --scan` | 查看明天空闲场地（只读，不下单） |
| `./run.sh --loop` | 等 7:00 准时抢场（定时任务用） |
| `./run.sh --setup` | 重新配置账号 / 校区 / 运动 |

三点注意：

- `run.sh` 和 `check_env.sh` 是 **bash 脚本**，仅适用于 Linux / macOS / Git Bash。
  Windows 原生环境请直接调用 `python main.py <参数>`。
- 所有模式操作的都是**明天**的场地。
- `--setup` 会先删除已有的 `.env`、`cookies.json`、`token.json`，再走配置向导。

[↑ 回到目录](#目录)

---

## 抢场原理

```
06:55  脚本启动（--loop 模式）
  ├─ 恢复上次 Session（cookie + token），并调接口校验 token 是否有效
  ├─ 预取所有场地和时间段数据（实测约 2~3 秒）
  ├─ 预构建所有可预约订单
  └─ sleep 到 06:59:58.5

06:59:58.5  纯 CPU 空转轮询
  └─ 不发网络请求，避免网络波动

07:00:00.000  触发下单
  ├─ 先用预取数据里的最优时段发第一枪（省掉一次往返）
  └─ 若失败 → 重新拉取实时数据，每 10 秒一轮，60 秒超时为止

完成 → 写入 booking.log + Server酱微信推送
```

### 触发精度

- 触发精度约 **1 毫秒**。实测 `datetime.now()` 的粒度在 0.3~1.5 ms 之间。
- 真正决定成败的是**网络往返时间**（几十到几百毫秒）。脚本只能保证
  "不因为自己的原因晚发"，无法保证"比所有人都早到"。
- 所以**启动时刻必须早于 06:59**。晚于 07:00 启动时脚本不会等待，
  会在预取（2~3 秒）完成后立即发请求，等于白白晚了几秒。

### 时段优先级

默认**由晚到早**尝试（20:00 优先于 19:00），同一时段内随机打乱并优先靠前的场馆。
这是刻意设计——晚间黄金时段最抢手。需调整见 `booker.py` 的 `_shuffle_within_time()`。

### 账号预约上限

服务器限制每个账号同时最多 **3 个**未使用的场地。命中时脚本立即停止并推送
"账号预约数已达上限"，不做无谓重试。

[↑ 回到目录](#目录)

---

## 配置项

配置保存在 `badminton-booking/.env`（`--setup` 自动生成）：

| 键 | 必填 | 说明 |
|----|------|------|
| `ZJNU_USERNAME` | ✅ | 学号 |
| `ZJNU_PASSWORD` | ✅ | 密码（明文存本地，请勿提交到仓库） |
| `ZJNU_CAMPUS` | ✅ | `jinhua` 或 `xiaoshan` |
| `ZJNU_SPORT` | ✅ | `badminton` / `pingpong` / `volleyball` |
| `SENDKEY` | ⬜ | Server酱 SendKey，留空则不推送 |

> `SENDKEY` 有回退机制：本地 `.env` 没有时会去读项目根目录的 `.env`。
> 其余键**只**从 `badminton-booking/.env` 读取。

[↑ 回到目录](#目录)

---

## 系统版本对照表

**不同系统差别很大，先在这里找到你的系统。**

| 系统 | 版本 | 自带 Python | 能用吗 |
|------|------|-------------|--------|
| **Ubuntu** | 24.04 / 22.04 / 20.04 | 3.12 / 3.10 / 3.8 | ✅ 直接用 |
| | 18.04 | 3.6 | ❌ 版本过低 |
| **Debian** | 13 / 12 / 11 | 3.13 / 3.11 / 3.9 | ✅ 直接用 |
| | 10 | 3.7 | ⚠️ 刚好够，但已 EOL |
| **CentOS** | 7 / 8 | 3.6 | ❌ 系统已 EOL |
| **Rocky / AlmaLinux** | 9 / 10 | 3.9 / 3.12 | ✅ 直接用 |
| | 8 | 3.6 | ❌ 需启用 python39 模块 |
| **Fedora** | 40+ | 3.13 | ✅ 直接用 |
| **Arch / Manjaro** | 滚动 | 最新 | ✅ 直接用 |
| **Alpine** | 3.19+ | 3.11+ | ✅ 需额外装 `bash` |
| **macOS** | — | 视安装方式 | ✅ 直接用 |

> **关键约束**：`requirements.txt` 里的 `requests>=2.28` 要求 **Python ≥ 3.7**，
> 低于此版本 **pip 会直接拒绝安装**，不是脚本能绕过的。
>
> 受影响的系统：**CentOS 7/8、Ubuntu 18.04、Debian 10、Rocky 8**。

不确定自己是什么系统？直接跑 `./check_env.sh`，它会替你判断。

[↑ 回到目录](#目录)

---

## 部署到 Linux 服务器

> 假设你刚拿到一台全新服务器，除了 SSH 什么都没有。
> 按顺序照做即可，遇到报错先跑 `./check_env.sh`。

### 第 1 步：获取代码

```bash
cd /root
git clone https://github.com/OTTO-91/ZJNU.git
cd ZJNU
```

没装 git 就 `apt install -y git`，或从 GitHub 下载 zip 解压。

> **`git clone` 会自动带上执行权限，无需 `chmod`。**
> 但在 Windows 上解压后上传到服务器会丢失执行权限，
> 报 `Permission denied`。修复见[常见问题](#permission-denied)。

### 第 2 步：环境自检

```bash
./check_env.sh
```

它会检查 8 项，并对每一项给出**可直接复制的修复命令**：

| # | 检查项 | 缺失后果 |
|---|--------|----------|
| 1 | Python **3.7+** | 无法运行 |
| 2 | `venv` / `ensurepip` | 建不了虚拟环境 |
| 3 | 虚拟环境 + 四个依赖 | 无法运行 |
| 4 | Node.js | **导入 `auth.py` 时直接崩** |
| 5 | 系统时区为 +0800 | **不报错，但抢错时间** |
| 6 | 能否连上校内系统 | 校外需连学校 VPN |
| 7 | `run.sh` 执行权限 | `Permission denied` |
| 8 | `.env` 账号配置 | 引导你跑 `--setup` |

输出长这样：

```
系统: Ubuntu 24.04.1 LTS   包管理器: apt   身份: root
该版本自带 Python 3.12（本项目要求 >= 3.7）

[1/8] Python 3
  [ OK ] Python 3.12.10  (/usr/bin/python3)
[2/8] venv 与 ensurepip
  [FAIL] ensurepip 缺失 —— 这正是 "ensurepip is not available" 报错的原因
...
建议按顺序执行以下命令:

  sudo apt update && (sudo apt install -y python3.12-venv || sudo apt install -y python3-venv)
  sudo apt install -y nodejs
  sudo timedatectl set-timezone Asia/Shanghai
```

想让它**自动执行**这些命令：

```bash
./check_env.sh --fix
```

执行前会把命令列出来征求确认，不会偷偷改你的系统。

### 第 3 步：安装依赖

按你的系统选一行：

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y python3 python3-pip python3-venv nodejs git

# Rocky / AlmaLinux / RHEL 9+、Fedora
sudo dnf install -y python3 python3-pip nodejs git

# Arch / Manjaro
sudo pacman -S --noconfirm python nodejs git

# Alpine
sudo apk add python3 py3-pip nodejs git bash
```

**三个容易踩的点：**

**① Debian/Ubuntu 的 `python3-venv` 是独立包**

装 Python 时**不会**自动带上，缺了就会报 `ensurepip is not available`。
如果 `python3-venv` 提示找不到，把版本号带上：

```bash
sudo apt install -y python3.12-venv     # Ubuntu 24.04
sudo apt install -y python3.10-venv     # Ubuntu 22.04
sudo apt install -y python3.11-venv     # Debian 12
```

版本号用这条查：`python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])'`

**② CentOS 7/8 不能用**

自带 Python 3.6，装不上依赖。而且 CentOS 7 已于 2024-06-30 EOL、
CentOS 8 于 2021-12-31 EOL，官方源已下线，`yum install` 会报
`Could not resolve host: mirrorlist.centos.org`。

建议重装为 **Rocky Linux 9** 或 **AlmaLinux 9**（同源，自带 Python 3.9，开箱即用）。

若必须留在 CentOS 7，用 SCL 装新版 Python：

```bash
sudo yum install -y centos-release-scl rh-python38
scl enable rh-python38 bash
python3 --version        # 应为 3.8.x
```

> ⚠️ SCL 装的 Python **只在 `scl enable` 会话里生效**。
> crontab 必须显式带上，否则定时任务仍用旧的 3.6：
>
> ```
> 55 6 * * * cd /root/ZJNU && scl enable rh-python38 -- ./run.sh --loop
> ```

**③ Rocky / AlmaLinux 8 要启用模块**

```bash
sudo dnf module enable -y python39
sudo dnf install -y python39 python39-pip nodejs git
```

> 注意此时命令是 `python3.9` 而非 `python3`，建虚拟环境要用
> `python3.9 -m venv venv`。

**④ Alpine 必须装 `bash`**

Alpine 默认只有 `sh`，而 `run.sh` 需要 `bash`。

### 第 4 步：设置时区

**⚠️ 这一步最容易被忽略，而且错了不会报任何错。**

脚本用本机时钟卡 07:00，云服务器默认通常是 UTC：

```bash
timedatectl                       # 先看当前时区
sudo timedatectl set-timezone Asia/Shanghai
date                              # 应显示 CST +0800 的北京时间
```

时区是 UTC 的话，脚本会在 **UTC 07:00 = 北京时间 15:00** 触发，
crontab 同理，**永远抢不到但永远不报错**。

### 第 5 步：创建虚拟环境

```bash
python3 -m venv venv
venv/bin/pip install -r badminton-booking/requirements.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> **如果报 `ensurepip is not available`**：说明第 3 步的 `python3-venv` 没装上。
> 补装后**必须删掉残缺的 venv 重建**，否则 pip 仍是坏的：
>
> ```bash
> sudo apt install -y python3.12-venv    # 版本号按你的 python3 来
> rm -rf venv
> python3 -m venv venv
> venv/bin/pip --version                 # 能打印版本号即成功
> ```

> **如果报 `No matching distribution found for requests>=2.28`**：
> Python 版本低于 3.7，见[系统版本对照表](#系统版本对照表)。

### 第 6 步：配置账号

```bash
./run.sh --setup
```

按提示输入学号、密码、选校区和运动项目。

### 第 7 步：试运行

```bash
./run.sh --scan
```

**必须看到真实的场地列表才算通过**：

```
  明日 (2026-10-13) 场地空闲情况
  综合馆羽毛球馆:
   08:00: #1, 2, 3, 4, 5, 6
   09:00: #1, 2, 3, 4, 5, 6
   共 25 个可预约时段
```

| 现象 | 说明 |
|------|------|
| 报登录失败 | 检查学号密码，或确认是否需要校园网 / VPN |
| 全是"无可用场地" | 网络通了但确实没空位，属正常 |
| 控制台中文乱码 | **不影响运行**，`booking.log` 是 UTF-8 正常日志 |

### 第 8 步：配置定时任务

**方式一：crontab（推荐）**

```bash
crontab -e        # 首次会让你选编辑器，选 nano 最省事
```

加入这一行：

```
55 6 * * * cd /root/ZJNU && ./run.sh --loop
```

保存退出（nano 按 `Ctrl+O` 回车，再 `Ctrl+X`）。确认写入成功：

```bash
crontab -l
```

> ⚠️ **不要写成 `0 7 * * *`**。那样 07:00:00 才开始启动 Python、导入依赖、
> 登录并预取数据，等真正发请求时已经过去 2~3 秒，热门场地早没了。

**方式二：systemd timer**

```bash
sudo cp badminton-booking/badminton-booking.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now badminton-booking.timer
```

> `badminton-booking.timer` 的 `OnCalendar` 必须早于 07:00（现为 `06:55:00`）。
> `badminton-booking.service` 里的路径写死为 `/root/ZJNU`，**换目录必须改**。
>
> 检查状态：`systemctl list-timers | grep badminton`

**配完后先手动跑一次**，别等第二天早上才发现没跑：

```bash
cd /root/ZJNU && ./run.sh --loop
tail -f badminton-booking/booking.log      # 另开一个窗口看日志
```

第二天早上确认结果：

```bash
cat badminton-booking/last_booking.json    # 成功的话会有记录
tail -50 badminton-booking/booking.log     # 完整过程
```

[↑ 回到目录](#目录)

---

## 部署到 Windows

### 环境准备

需要 Python 3 和 Node.js。推荐用虚拟环境：

```powershell
# 在项目根目录
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r badminton-booking\requirements.txt
```

### 首次配置

```powershell
cd badminton-booking
..\.venv\Scripts\python.exe main.py --setup
```

### 创建定时任务

以**管理员身份**打开 PowerShell（注意用绝对路径，定时任务不继承 PATH）：

```powershell
schtasks /create /tn "ZJNU抢场" /tr "C:\ZJNU\.venv\Scripts\python.exe C:\ZJNU\badminton-booking\main.py --loop" /sc daily /st 06:54 /f
```

任务已存在时改用 `/change`（**同样需要管理员权限**，否则报 `Access is denied`）：

```powershell
schtasks /change /tn "ZJNU抢场" /tr "..."
schtasks /change /tn "ZJNU抢场" /enable
```

> `/st` 用 06:54 或 06:55 都行，只要早于 06:59。脚本会自己等到 07:00。

### 自动唤醒（可选）

1. 控制面板 → 电源选项 → 高级电源设置 → 睡眠 → **允许唤醒计时器** → 启用
2. `Win + R` → `taskschd.msc` → "ZJNU抢场" → 属性 → 条件 → 勾选「唤醒计算机运行此任务」

防止鼠标误唤醒：

```powershell
powercfg /devicequery wake_armed
powercfg /devicedisablewake "HID Keyboard Device"
powercfg /devicedisablewake "HID-compliant mouse"
```

### 控制台中文与 emoji

Windows 控制台默认 GBK（cp936），emoji 无法输出。脚本已把 stdout/stderr 的
错误处理改为 `replace`，遇到不支持的字符降级成 `?` 而不是崩溃。

**`booking.log` 是 UTF-8 的权威日志**，控制台乱码不代表运行出错。

[↑ 回到目录](#目录)

---

## 常见问题

### 安装与环境

#### `ensurepip is not available`

Debian/Ubuntu 把 `venv` 拆成了独立包。装完**必须重建**虚拟环境：

```bash
sudo apt install -y python3.12-venv
rm -rf venv && python3 -m venv venv
```

#### `RuntimeUnavailableError` 或登录直接崩

缺 Node.js。PyExecJS 需要它执行 `ez.js` 做密码加密：

```bash
sudo apt install -y nodejs
```

#### `No matching distribution found for requests>=2.28`

Python 版本低于 3.7。`requests>=2.28` 的元数据里写死了 `requires_python >= 3.7`，
**pip 会直接拒绝安装**，不是网络问题。

```bash
python3 --version
```

若是 3.6（CentOS 7/8、Ubuntu 18.04 常见），见[系统版本对照表](#系统版本对照表)。

#### Permission denied

```
-bash: ./run.sh: Permission denied
```

Linux 靠文件的「执行位」决定能否直接运行。以下情况会丢失它：

| 场景 | 会丢吗 |
|------|--------|
| `git clone` | ❌ 不会 |
| GitHub 下载 ZIP 后在 **Linux** 上 `unzip` | ❌ 不会 |
| 在 **Windows** 上解压，再上传到服务器 | ✅ **会丢** |
| 用 FTP / 宝塔面板 / 某些网盘上传 | ✅ 常见会丢 |
| 服务器把目录挂载为 `noexec` | ✅ 会丢 |

修复：

```bash
chmod +x run.sh check_env.sh
```

临时绕过（不需要执行权限也能跑）：

```bash
bash run.sh --scan
bash check_env.sh
```

> `./run.sh` 要求文件可执行，`bash run.sh` 只要求可读。
> 但 **crontab 里建议用 `./run.sh`**，并用 `chmod +x` 修好权限。

#### `Could not resolve host: mirrorlist.centos.org`

CentOS 7/8 已 EOL，官方源已下线。这不是本项目的错误，任何 `yum install` 都会失败。

建议重装为 Rocky Linux 9 / AlmaLinux 9。若必须留在 CentOS 7，
需把 yum 源指向 `vault.centos.org`：

```bash
sudo sed -i 's/^mirrorlist=/#mirrorlist=/; s|^#baseurl=http://mirror.centos.org|baseurl=http://vault.centos.org|' /etc/yum.repos.d/CentOS-*.repo
sudo yum makecache
```

> vault 是归档源，**不再有安全更新**。仅作过渡，不建议长期使用。

### 运行与抢场

#### 登录失败

1. 检查学号密码是否正确
2. 运行 `./run.sh --setup` 重新配置
3. 查看 `badminton-booking/booking.log` 确认具体错误

#### 抢不到，但手动跑 `--scan` 正常

按可能性排序：

1. **时区不对** —— 跑 `date` 确认是 `+0800`
2. **启动太晚** —— crontab 必须是 `55 6`，不能是 `0 7`
3. **账号已有 3 个未使用预约** —— 服务器限制，先取消
4. 场地确实太热门

#### 定时任务没执行

**Linux：**

```bash
systemctl status cron          # 或 crond，确认定时服务在跑
crontab -l                     # 确认任务已写入
grep CRON /var/log/syslog      # 看 cron 有没有触发（CentOS: /var/log/cron）
tail -50 /root/ZJNU/badminton-booking/booking.log
```

**Windows：**

```powershell
schtasks /query /tn "ZJNU抢场" /v /fo LIST
```

检查任务是否被禁用、`/st` 时间是否正确、路径是否指向正确的 Python。

常见原因：路径写错、cron 服务没启动、时区不对（见[第 4 步](#第-4-步设置时区)）。

#### Cookie / Token 过期

自动处理。启动时会调接口**实际验证** token 是否有效，失效则自动重新登录。

#### 服务器重启后要重新配置吗

不用。`.env`、`cookies.json`、`token.json` 都持久化在磁盘上，
crontab 也会在重启后自动生效。

### 其他

#### 换账号 / 换运动

```bash
./run.sh --setup
```

#### 能同时抢多个场地吗

可以复制整个目录，配不同的 `badminton-booking/.env`，各自独立运行。
注意同一账号最多同时持有 3 个未使用的场地。

#### 能指定只抢某个时段吗

当前版本不支持。脚本按"由晚到早"的顺序自动尝试所有可用时段。
需要固定时段请改 `booker.py` 的 `_shuffle_within_time()`。

#### CAS 系统升级了怎么办

密码加密在 `ez.js`。如果 CAS 改版导致登录页结构变化，需要更新 `auth.py` 里的
表单字段解析（`execution`、`pwdEncryptSalt`）。欢迎提 Issue 或 PR。

[↑ 回到目录](#目录)

---

## 项目结构

```
ZJNU/
├── run.sh                        # 快捷启动脚本（bash）
├── check_env.sh                  # 环境自检（--fix 可自动修复）
├── README.md
├── zjnu.py                       # 原始单文件脚本（历史存档，不参与运行）
│
└── badminton-booking/
    ├── main.py                   # CLI 入口
    ├── config.py                 # 配置管理（.env、场地注册表、设置向导）
    ├── auth.py                   # CAS 登录 + Session 持久化 + Token 校验
    ├── booker.py                 # 抢场引擎（scan / book / loop）
    ├── notify.py                 # Server酱推送
    ├── ez.js                     # CryptoJS AES 密码加密
    ├── requirements.txt          # Python 依赖
    ├── LICENSE                   # Apache License 2.0
    ├── .env.example              # 配置模板
    ├── crontab.txt               # crontab 参考
    ├── badminton-booking.service # systemd 服务
    ├── badminton-booking.timer   # systemd 定时器
    │
    └── ── 运行时生成，已 gitignore ──
        ├── .env                  # 实际配置（含密码）
        ├── cookies.json / token.json
        ├── last_booking.json     # 最近一次成功预约
        └── booking.log           # 运行日志（UTF-8）
```

[↑ 回到目录](#目录)

---

## 许可

Apache License 2.0，详见 [badminton-booking/LICENSE](badminton-booking/LICENSE)。

致谢：[CryptoJS](https://github.com/brix/crypto-js) · [Server酱](https://sct.ftqq.com/)
