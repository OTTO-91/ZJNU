# 浙师大体育场地自动预约

一个在浙江师范大学（ZJNU）自动预约体育场地的命令行工具：支持多校区多运动项目，
每天早上 7:00 准时提交预约，抢不到时自动降级重试。

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](badminton-booking/LICENSE)
[![Python 3.7+](https://img.shields.io/badge/Python-3.7%2B-blue.svg)](https://www.python.org/downloads/)
[![Runtime dependencies: 4](https://img.shields.io/badge/runtime%20dependencies-4-blue.svg)](badminton-booking/requirements.txt)

**按你的处境选入口：**

| 我想…… | 去哪 |
|---|---|
| 先搞清楚这是什么 | [这是什么](#这是什么) |
| 赶紧跑起来 | [快速上手](#快速上手) |
| 部署到服务器 / 定时抢场 | [安装](#安装) → [定时任务](#定时任务) |
| 查某个参数 / 退出码 | [命令与参数](#命令与参数) · [退出码](#退出码与错误行为) |
| 报错了 | [常见问题](#常见问题) |
| 想改代码 | [贡献](#贡献) · [项目结构](#项目结构) |

## 目录

- [这是什么](#这是什么)
- [功能特性](#功能特性)
- [支持的场地](#支持的场地)
- [运行环境](#运行环境)
- [安装](#安装)
  - [Linux 服务器](#linux-服务器)
  - [Windows](#windows)
  - [发行版对照表](#发行版对照表)
- [快速上手](#快速上手)
- [命令与参数](#命令与参数)
- [退出码与错误行为](#退出码与错误行为)
- [配置项](#配置项)
- [抢场原理](#抢场原理)
- [定时任务](#定时任务)
- [常见问题](#常见问题)
- [日志与隐私](#日志与隐私)
- [项目结构](#项目结构)
- [贡献](#贡献)
- [许可](#许可)

---

## 这是什么

浙师大的体育场地（羽毛球、乒乓球、排球）每天早上 7:00 开放次日预约，热门时段
（尤其是晚间 20:00）在几十秒内就会被抢光。手动守着网页刷新既累又不一定抢得到。

这个工具把整个过程自动化：提前取好数据，在 07:00:00 那一刻提交请求，抢不到就
自动换下一个时段重试，结果推送到微信。

**适合谁**：有 ZJNU 学号、想固定约到某个时段的在校师生。
**不适合谁**：需要预约校外场地、或需要同时管理多个账号的场景——本项目只处理
单个账号的自动预约，没有图形界面。

[↑ 回到目录](#目录)

---

## 功能特性

- **毫秒级卡点** —— 提前预取数据并在 `07:00:00` 触发，实测触发误差约 1 毫秒，
  不是"大概七点"。
- **抢不到会自动降级** —— 首选时段被抢则按由晚到早的顺序尝试其余时段，
  60 秒内持续重试，不需要人盯着。
- **登录状态持久化** —— Cookie 与 Token 存本地，重启无需重新登录；Token 失效
  时会调接口实际验证并自动重新登录。
- **多校区多项目** —— 金华校区（羽毛球 / 乒乓球 / 排球）、萧山校区（羽毛球）。
- **结果推送微信** —— 可选接入 Server酱，成功、失败、账号超限都会推送。
- **零配置改动即可换目标** —— 换账号 / 换校区 / 换项目都走 `--setup`，
  不需要手改代码。

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

> 萧山校区目前仅开放羽毛球。场地 ID 定义在 `badminton-booking/config.py`
> 的 `COURT_REGISTRY`，学校新增场馆时在那里补充即可。

[↑ 回到目录](#目录)

---

## 运行环境

| 依赖 | 要求 | 说明 |
|------|------|------|
| Python | **3.7+** | 由 `requests>=2.28` 的 `requires_python` 决定 |
| Node.js | 任意 LTS | **必需**，见下方说明 |
| 系统时区 | +0800 | 时区不对**不报错**，但会在错误的时间抢场 |
| 网络 | 能访问校内系统 | 校外需连学校 VPN |

**为什么需要 Node.js**：登录时密码要用 AES 加密（`ez.js` 里的 CryptoJS），
Python 通过 PyExecJS 调用 Node 来执行它。**缺 Node 会在导入 `auth.py` 时直接
崩溃**，报 `RuntimeUnavailableError`，连 `--setup` 都进不去。

Python 依赖共 4 个（`badminton-booking/requirements.txt`）：

```text
requests>=2.28
PyExecJS>=1.5
beautifulsoup4>=4.11
lxml>=4.9
```

[↑ 回到目录](#目录)

---

## 安装

> 不确定环境是否齐全？装完代码后直接跑 `./check_env.sh`，它会逐项检查并给出
> 可直接复制的修复命令。

### Linux 服务器

```bash
# 1. 取代码
git clone https://github.com/OTTO-91/ZJNU.git
cd ZJNU

# 2. 装系统依赖（Ubuntu / Debian）
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nodejs git

# 3. 建虚拟环境并装 Python 依赖
python3 -m venv venv
venv/bin/pip install -r badminton-booking/requirements.txt \
  -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 验证
./check_env.sh
```

第 4 步全绿即可继续。也可以手动确认关键三项：

```bash
python3 --version     # 应为 3.7 或更高
node --version        # 有输出即可
date                  # 应显示 +0800
```

> **`git clone` 会保留执行权限，不需要 `chmod`。**
> 但在 Windows 上解压后上传到服务器会丢失执行权限，报 `Permission denied`，
> 修复见[常见问题](#permission-denied)。

### Windows

需要 Python 3 与 Node.js。推荐用虚拟环境，避免污染系统 Python：

```powershell
# 在项目根目录
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r badminton-booking\requirements.txt
```

配置账号：

```powershell
cd badminton-booking
..\.venv\Scripts\python.exe main.py --setup
```

> `run.sh` 与 `check_env.sh` 是 bash 脚本，Windows 原生环境不适用，
> 直接用上面的 `python main.py <参数>` 形式。若已装 Git Bash，也可以在
> Git Bash 里按 Linux 的方式操作。

### 发行版对照表

**不同发行版自带的 Python 版本差别很大，先在这里找到你的系统。**

| 系统 | 版本 | 自带 Python | 能否直接用 |
|------|------|-------------|-----------|
| Ubuntu | 24.04 / 22.04 / 20.04 | 3.12 / 3.10 / 3.8 | ✅ 直接用 |
| Ubuntu | 18.04 | 3.6 | ❌ 版本过低 |
| Debian | 13 / 12 / 11 | 3.13 / 3.11 / 3.9 | ✅ 直接用 |
| Debian | 10 | 3.7 | ⚠️ 刚好够，但系统已 EOL |
| CentOS | 7 / 8 | 3.6 | ❌ 系统已 EOL |
| Rocky / AlmaLinux | 9 / 10 | 3.9 / 3.12 | ✅ 直接用 |
| Rocky / AlmaLinux | 8 | 3.6 | ❌ 需启用 python39 模块 |
| Fedora | 40+ | 3.13 | ✅ 直接用 |
| Arch / Manjaro | 滚动 | 最新 | ✅ 直接用 |
| Alpine | 3.19+ | 3.11+ | ✅ 需额外装 `bash` |

各系统的安装命令：

| 系统 | 命令 |
|------|------|
| Ubuntu / Debian | `sudo apt install -y python3 python3-pip python3-venv nodejs git` |
| Rocky / Alma / RHEL 9+ | `sudo dnf install -y python3 python3-pip nodejs git` |
| Fedora | `sudo dnf install -y python3 python3-pip nodejs git` |
| Arch / Manjaro | `sudo pacman -S --noconfirm python nodejs git` |
| Alpine | `sudo apk add python3 py3-pip nodejs git bash` |

**三个容易踩的坑：**

**① Debian / Ubuntu 的 `python3-venv` 是独立包**

装 Python 时**不会**自动带上，缺了会报 `ensurepip is not available`。
如果 `python3-venv` 提示找不到，把版本号带上：

```bash
sudo apt install -y python3.12-venv     # Ubuntu 24.04
sudo apt install -y python3.10-venv     # Ubuntu 22.04
sudo apt install -y python3.11-venv     # Debian 12
```

版本号用这条查：`python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])'`

**② CentOS 7 / 8 需要额外步骤**

自带 Python 3.6，装不上依赖；且 CentOS 7 已于 2024-06-30 EOL、
CentOS 8 于 2021-12-31 EOL，官方源已下线，`yum install` 会报
`Could not resolve host: mirrorlist.centos.org`。

建议重装为 **Rocky Linux 9** 或 **AlmaLinux 9**（与 CentOS 同源，自带 Python 3.9）。
若必须留在 CentOS 7，用 SCL 装新版 Python：

```bash
sudo yum install -y centos-release-scl rh-python38
scl enable rh-python38 bash
python3 --version        # 应为 3.8.x
```

> ⚠️ SCL 装的 Python **只在 `scl enable` 会话里生效**，crontab 必须显式带上，
> 否则定时任务仍会用旧的 3.6，见[定时任务](#定时任务)。

**③ Rocky / AlmaLinux 8 要启用模块**

```bash
sudo dnf module enable -y python39
sudo dnf install -y python39 python39-pip nodejs git
```

> 此时命令是 `python3.9` 而非 `python3`，建虚拟环境要用 `python3.9 -m venv venv`。

[↑ 回到目录](#目录)

---

## 快速上手

配置账号（首次运行会交互式询问学号、密码、校区、运动项目）：

```bash
./run.sh --setup
```

确认能正常登录并拉到场地数据：

```bash
./run.sh --scan
```

**预期输出**（这是明天真实的可预约时段，你的结果会随日期变化）：

```text
==================================================
  明日 (2026-10-13) 场地空闲情况
==================================================

  北田羽毛球馆:
   (无可用场地)
  综合馆羽毛球馆:
   08:00: #1, 2, 3, 4, 5, 6
   09:00: #1, 2, 3, 4, 5, 6
   10:00: #2, 4, 5
   11:00: #1, 2, 4, 5, 6
   14:00: #1, 2, 4, 5, 6
   共 25 个可预约时段
```

看到这样的列表就说明登录、取数、解析全部正常。之后配上[定时任务](#定时任务)
即可每天自动抢场。

[↑ 回到目录](#目录)

---

## 命令与参数

```text
python main.py [--scan | --loop | --setup]
```

日常使用建议通过 `./run.sh` 调用，它会自动激活虚拟环境：

| 命令 | 用途 |
|------|------|
| `./run.sh` | 立即预约明天场地（**会真的下单**） |
| `./run.sh --scan` | 查看明天空闲场地，只读不下单 |
| `./run.sh --loop` | 等到 07:00 再抢，定时任务用 |
| `./run.sh --setup` | 重新配置账号 / 校区 / 运动 |
| `./check_env.sh` | 环境自检，逐项检查并给出修复命令 |
| `./check_env.sh --fix` | 自检并自动执行修复 |

参数表：

| 参数 | 说明 |
|------|------|
| `--scan` | 只查询并打印空闲场地，不发起任何下单请求 |
| `--loop` | 先预取数据，等到 `07:00:00` 再提交；启动需早于 06:59 |
| `--setup` | 重新走配置向导。**会先删除已有的 `.env`、`cookies.json`、`token.json`** |
| `-h`, `--help` | 显示帮助 |
| 无参数 | 等同于立即预约明天场地 |

三点注意：

- **所有模式操作的都是"明天"的场地**（`booker.py` 里 `DAY_OFFSET = 1`）。
- **不支持从 stdin 读取**。输入文件固定为 `badminton-booking/.env`，参数只用于
  选择模式，因此不能用于管道（如 `echo ... | ./run.sh -`）。
- **无参数模式会真的下单**，只想看空场请用 `--scan`。

[↑ 回到目录](#目录)

---

## 退出码与错误行为

脚本化调用（cron、CI、监控）时这是最重要的契约：

| 退出码 | 含义 |
|--------|------|
| `0` | 正常结束。**包括"没抢到场地"的情况** |
| `1` | `--setup` 被中断（Ctrl+C 或非交互环境读到 EOF），或登录失败 |
| `2` | 参数用法错误（如传了未知参数） |

> ⚠️ **"抢不到"返回 0，不是非零。** 预约失败只会写日志并推送微信，
> 不会让进程以失败状态退出。所以 cron 的 `MAILTO` 不会因为没抢到而发邮件——
> 想感知失败请依赖微信推送或检查 `booking.log`。

错误输出示例：

```text
$ ./run.sh --bogus
usage: main.py [-h] [--scan] [--loop] [--setup]
main.py: error: unrecognized arguments: --bogus
```

登录失败时错误信息会写入 `booking.log`，同时（若配置了 SENDKEY）推送微信。

[↑ 回到目录](#目录)

---

## 配置项

配置保存在 `badminton-booking/.env`，由 `--setup` 自动生成：

| 键 | 必填 | 说明 |
|----|------|------|
| `ZJNU_USERNAME` | ✅ | 学号 |
| `ZJNU_PASSWORD` | ✅ | 密码（**明文存本地**，该文件已 gitignore） |
| `ZJNU_CAMPUS` | ✅ | `jinhua` 或 `xiaoshan` |
| `ZJNU_SPORT` | ✅ | `badminton` / `pingpong` / `volleyball` |
| `SENDKEY` | ⬜ | Server酱 SendKey，留空则不推送 |

> `SENDKEY` 有回退机制：`badminton-booking/.env` 里没有时，会去读项目根目录的
> `.env`。其余键**只**从 `badminton-booking/.env` 读取。

**数据流向**：密码仅用于向 `authserver.zjnu.edu.cn` 登录，登录后请求
`tycg.zjnu.edu.cn` 完成预约；两者都是校内系统。除可选的 Server酱推送
（`sctapi.ftqq.com`）外，没有任何数据发往第三方。日志会记录**学号**但不会
记录密码，见[日志与隐私](#日志与隐私)。

[↑ 回到目录](#目录)

---

## 抢场原理

```text
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

- 触发误差约 **1 毫秒**。实测 `datetime.now()` 的粒度在 0.3~1.5 ms 之间。
- 真正决定成败的是**网络往返时间**（几十到几百毫秒）。本工具只能保证
  "不因为自己的原因晚发"，无法保证"比所有人都早到"。
- 所以**启动时刻必须早于 06:59**。晚于 07:00 启动时不会等待，会在预取
  （2~3 秒）完成后立即发请求，等于白白晚了几秒。

### 时段优先级

默认**由晚到早**尝试（20:00 优先于 19:00），同一时段内随机打乱并优先靠前的场馆。
这是刻意设计——晚间黄金时段最抢手。需调整见 `booker.py` 的
`_shuffle_within_time()`。

### 账号预约上限

服务器限制每个账号同时最多 **3 个**未使用的场地。命中时立即停止并推送
"账号预约数已达上限"，不做无谓重试。

[↑ 回到目录](#目录)

---

## 定时任务

脚本需要**在 06:59 之前启动**，它自己会等到 07:00。因此定时任务设在 06:54~06:55。

### Linux：crontab

```bash
crontab -e        # 首次会让你选编辑器，选 nano 最省事
```

加入这一行：

```text
55 6 * * * cd /root/ZJNU && ./run.sh --loop
```

保存退出（nano 按 `Ctrl+O` 回车，再 `Ctrl+X`），确认写入成功：

```bash
crontab -l
```

> ⚠️ **不要写成 `0 7 * * *`**。那样 07:00:00 才开始启动 Python、导入依赖、
> 登录并预取数据，等真正发请求时已经过去 2~3 秒，热门场地早没了。

**CentOS 7 用 SCL 装的 Python 必须显式启用**，否则定时任务仍用旧的 3.6：

```text
55 6 * * * cd /root/ZJNU && scl enable rh-python38 -- ./run.sh --loop
```

### Linux：systemd timer

```bash
sudo cp badminton-booking/badminton-booking.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now badminton-booking.timer
```

> `badminton-booking.timer` 的 `OnCalendar` 已设为 `06:55:00`，必须早于 07:00。
> `badminton-booking.service` 里的路径写死为 `/root/ZJNU`，**换目录必须改**。
>
> 检查状态：`systemctl list-timers | grep badminton`

### Windows：计划任务

以**管理员身份**打开 PowerShell（注意用绝对路径，计划任务不继承 PATH）：

```powershell
schtasks /create /tn "ZJNU抢场" /tr "C:\ZJNU\.venv\Scripts\python.exe C:\ZJNU\badminton-booking\main.py --loop" /sc daily /st 06:54 /f
```

任务已存在时改用 `/change`（**同样需要管理员权限**，否则报 `Access is denied`）：

```powershell
schtasks /change /tn "ZJNU抢场" /tr "..."
schtasks /change /tn "ZJNU抢场" /enable
```

需要唤醒睡眠中的电脑时：控制面板 → 电源选项 → 高级电源设置 → 睡眠 →
**允许唤醒计时器** → 启用；然后在 `taskschd.msc` 里勾选「唤醒计算机运行此任务」。

### 验证定时任务真的会跑

**不要等到第二天早上才发现没跑。** 先手动触发一次：

```bash
cd /root/ZJNU && ./run.sh --loop
```

它会预取数据、等到 07:00、然后下单。想立刻看到过程而不等到 07:00：

```bash
tail -f badminton-booking/booking.log
```

第二天早上确认结果：

```bash
cat badminton-booking/last_booking.json    # 成功的话会有记录
tail -50 badminton-booking/booking.log     # 完整过程
```

[↑ 回到目录](#目录)

---

## 常见问题

### 安装与环境

#### ensurepip is not available

Debian / Ubuntu 把 `venv` 拆成了独立包。装完**必须删掉残缺的虚拟环境重建**，
否则 pip 仍是坏的：

```bash
sudo apt install -y python3.12-venv    # 版本号按你的 python3 来
rm -rf venv
python3 -m venv venv
venv/bin/pip --version                 # 能打印版本号即成功
```

#### RuntimeUnavailableError 或登录直接崩

缺 Node.js。PyExecJS 需要它执行 `ez.js` 做密码加密：

```bash
sudo apt install -y nodejs
```

#### No matching distribution found for requests>=2.28

Python 版本低于 3.7。`requests>=2.28` 的元数据里写死了 `requires_python >= 3.7`，
**pip 会直接拒绝安装**，不是网络问题。

```bash
python3 --version
```

若是 3.6（CentOS 7/8、Ubuntu 18.04 常见），见[发行版对照表](#发行版对照表)。

#### Permission denied

```text
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

#### Could not resolve host: mirrorlist.centos.org

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

#### 抢不到，但手动跑 --scan 正常

按可能性排序：

1. **时区不对** —— 跑 `date` 确认是 `+0800`
2. **启动太晚** —— crontab 必须是 `55 6`，不能是 `0 7`
3. **账号已有 3 个未使用预约** —— 服务器限制，先取消
4. 场地确实太热门

#### 定时任务没执行

Linux：

```bash
systemctl status cron          # 或 crond，确认定时服务在跑
crontab -l                     # 确认任务已写入
grep CRON /var/log/syslog      # 看 cron 有没有触发（CentOS: /var/log/cron）
tail -50 /root/ZJNU/badminton-booking/booking.log
```

Windows：

```powershell
schtasks /query /tn "ZJNU抢场" /v /fo LIST
```

常见原因：路径写错、cron 服务没启动、时区不对、CentOS 7 忘了 `scl enable`。

#### Cookie / Token 过期

自动处理。启动时会调接口**实际验证** token 是否有效，失效则自动重新登录。

#### 服务器重启后要重新配置吗

不用。`.env`、`cookies.json`、`token.json` 都持久化在磁盘上，
crontab 也会在重启后自动生效。

#### 控制台中文显示乱码

Windows 控制台默认 GBK（cp936），部分字符无法输出。脚本已把 stdout / stderr 的
错误处理改为 `replace`，遇到不支持的字符降级成 `?` 而不是崩溃。

**`booking.log` 是 UTF-8 的权威日志**，控制台乱码不代表运行出错。

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
表单字段解析（`execution`、`pwdEncryptSalt`）。

[↑ 回到目录](#目录)

---

## 日志与隐私

- `booking.log` 会记录**学号**（形如 `Logging in as 2024xxxxxx`）、场地、时段和
  接口返回码，**不会记录密码**。
- 密码以**明文**存放在 `badminton-booking/.env`，该文件已在 `.gitignore` 中，
  不会进入版本库。请勿手动提交它。
- `cookies.json` 与 `token.json` 含登录凭据，同样已 gitignore。
- 数据流向：密码仅用于向 `authserver.zjnu.edu.cn` 登录，登录后请求
  `tycg.zjnu.edu.cn` 完成预约，两者都是校内系统。除可选的 Server酱推送
  （`sctapi.ftqq.com`）外，没有任何数据发往第三方。

[↑ 回到目录](#目录)

---

## 项目结构

```text
ZJNU/
├── run.sh                        # 快捷启动脚本（bash）
├── check_env.sh                  # 环境自检，--fix 可自动修复
├── README.md
├── zjnu.py                       # 早期单文件版本，历史存档，不参与运行
│
└── badminton-booking/
    ├── main.py                   # CLI 入口，参数解析与流程编排
    ├── config.py                 # 配置读写、场地注册表、设置向导
    ├── auth.py                   # CAS 登录、Session 持久化、Token 校验
    ├── booker.py                 # 抢场核心：scan / book / loop
    ├── notify.py                 # Server酱推送
    ├── ez.js                     # CryptoJS AES 密码加密
    ├── requirements.txt          # Python 依赖（4 个）
    ├── LICENSE                   # Apache License 2.0
    ├── .env.example              # 配置模板
    ├── crontab.txt               # crontab 参考
    ├── badminton-booking.service # systemd 服务
    ├── badminton-booking.timer   # systemd 定时器
    │
    └── 以下为运行时生成，已被 .gitignore 忽略
        ├── .env                  # 账号配置，含明文密码
        ├── cookies.json          # 会话 Cookie
        ├── token.json            # API Token
        ├── last_booking.json     # 最近一次成功预约
        └── booking.log           # 运行日志（UTF-8）
```

**项目没有测试套件，也没有 CI。** 验证方式是跑 `./check_env.sh` 与
`./run.sh --scan`——后者会真实登录并拉取数据，是最有效的端到端检查。

[↑ 回到目录](#目录)

---

## 贡献

欢迎 bug 报告、文档修正和代码改进。这个项目没有 `CONTRIBUTING.md`，
直接开 issue 或提 PR 即可。

**开发环境**：

```bash
git clone https://github.com/OTTO-91/ZJNU.git
cd ZJNU
python3 -m venv venv
venv/bin/pip install -r badminton-booking/requirements.txt
```

改完代码用这两条验证，不需要额外的测试框架：

```bash
./check_env.sh          # 环境是否仍然正常
./run.sh --scan         # 端到端：登录 + 取数 + 解析
```

**提 issue 时请附上**：`./run.sh --scan` 的输出、`booking.log` 里对应的报错段落、
以及你的系统版本与 Python 版本。**请先抹掉学号、密码、SENDKEY 等个人信息。**

**这个项目不做什么**（避免无效 issue）：

- 不做图形界面
- 不支持多账号管理
- 不支持指定单一目标时段（当前按由晚到早自动降级）
- 不绕过学校的预约规则与账号限额

[↑ 回到目录](#目录)

---

## 许可

本项目基于 [Apache License 2.0](badminton-booking/LICENSE) 发布。

登录环节的密码加密使用了 [CryptoJS](https://github.com/brix/crypto-js)，
微信推送使用 [Server酱](https://sct.ftqq.com/)。
