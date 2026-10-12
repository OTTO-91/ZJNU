# 浙师大体育场地自动预约 🏸

浙江师范大学（ZJNU）体育场地自动预约脚本，支持多校区、多运动项目。
**每天早上 7:00 准时抢场，毫秒级触发，一次命中。**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](badminton-booking/LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)

## 目录

- [功能特性](#功能特性)
- [支持的场地](#支持的场地)
- [运行环境](#运行环境)
- [快速开始](#快速开始)
- [命令说明](#命令说明)
- [抢场原理](#抢场原理)
- [配置项](#配置项)
- [服务器部署](#服务器部署)
- [Windows 部署](#windows-部署)
- [消息推送](#消息推送)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 功能特性

- 🎯 **一次配置，永久运行** —— 首次输入学号密码，之后全自动
- 🏫 **多校区** —— 金华校区 / 萧山校区
- 🏃 **多运动** —— 羽毛球 / 乒乓球 / 排球
- 🔐 **自动登录** —— CAS 统一认证 + Token 自动提取与校验
- ⏱️ **精准抢场** —— 6:55 预取数据，7:00:00.000 准时开抢
- 🔁 **自动兜底** —— 首选时段被抢则自动降级重试，无需人工干预
- 📱 **微信通知** —— Server酱 推送预约结果到微信
- 🔄 **会话保持** —— Cookie + Token 持久化，重启无需重新登录

## 支持的场地

| 校区 | 运动 | 场馆 | 场地 ID |
|------|------|------|---------|
| 金华 | 羽毛球 | 北田羽毛球馆 | 87 |
| 金华 | 羽毛球 | 综合馆羽毛球馆 | 84 |
| 金华 | 乒乓球 | 风雨操场乒乓球馆 | 86 |
| 金华 | 排球 | 风雨操场排球馆 | 85 |
| 萧山 | 羽毛球 | 萧山校区热身馆（羽毛球） | 92 |

> 萧山校区目前仅开放羽毛球。

---

## 运行环境

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | 已在 3.12 上验证 |
| Node.js | 任意 LTS | **必需**。PyExecJS 需要 Node 执行 `ez.js` 完成密码 AES 加密 |
| 系统时间 | 需准确 | 脚本按本机时钟卡点，请确保已开启系统时间同步 |

Python 依赖（`badminton-booking/requirements.txt`）：

```
requests>=2.28
PyExecJS>=1.5
beautifulsoup4>=4.11
lxml>=4.9
```

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/OTTO-91/ZJNU.git
cd ZJNU
```

### 2. 安装依赖

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装（国内用清华镜像）
cd badminton-booking
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
cd ..
```

> Windows 用户请看 [Windows 部署](#windows-部署)，venv 目录结构与激活命令不同。

### 3. 首次配置

```bash
./run.sh --setup
```

按提示输入学号、密码、选择校区和运动项目。配置自动保存，之后无需重复。

### 4. 试运行（查看空场）

```bash
./run.sh --scan
```

确认能正常返回场地信息后，就可以部署定时任务了。

---

## 命令说明

| 命令 | 用途 |
|------|------|
| `./run.sh` | 立即预约明天场地 |
| `./run.sh --scan` | 查看明天空闲场地（只读，不下单） |
| `./run.sh --loop` | 等 7:00 准时抢场（定时任务用） |
| `./run.sh --setup` | 重新配置账号/校区/运动 |

> `run.sh` 是 bash 脚本，仅适用于 Linux / macOS / Git Bash。
> Windows 原生环境请直接调用 `python main.py <参数>`，见 [Windows 部署](#windows-部署)。
>
> 所有模式操作的都是**明天**的场地（`DAY_OFFSET = 1`）。

`--setup` 会先删除已有的 `.env`、`cookies.json`、`token.json`，然后重新走配置向导。

---

## 抢场原理

```
06:55  脚本启动（--loop 模式）
  ├─ 恢复上次 Session（cookie + token），并调用接口校验 token 是否仍有效
  ├─ 预取所有场地和时间段数据（实测约 2~3 秒）
  ├─ 预构建所有可预约订单（JSON payload）
  └─ sleep 到 06:59:58.5

06:59:58.5  纯 CPU 空转轮询
  └─ 不发网络请求，避免网络波动；也不受 sleep 调度延迟影响

07:00:00.000  触发下单
  ├─ 先用预取数据里的最优时段发第一枪（不重新拉数据，省掉一次往返）
  └─ 若失败 → 重新拉取实时数据，每 10 秒一轮，60 秒超时为止

完成 → 结果写入 booking.log + Server酱微信推送
```

### 关于"精准"的实话

- 触发精度约 **1 毫秒**，不是微秒级。Windows 上 `datetime.now()` 的实际粒度实测在
  0.3~1.5 ms 之间，空转轮询只能保证在这个量级上命中 `07:00:00.000`。
- 真正决定成败的是**网络往返时间**，通常在几十到几百毫秒。脚本能保证的是
  "不因为自己的原因晚发"，无法保证"比所有人都早到"。
- 因此**启动时刻必须早于 06:59**。启动晚于 07:00 时脚本不会等待，会在预取
  （约 2~3 秒）完成后立即发请求，等于白白晚了几秒。

### 时段优先级

默认**由晚到早**尝试（20:00 优先于 19:00），同一时段内随机打乱并优先尝试靠前的场馆。
这是刻意的设计：晚间黄金时段最抢手。如需调整，见 `booker.py` 的 `_shuffle_within_time()`。

### 账号预约上限

服务器限制每个账号同时最多 3 个未使用的场地。命中该限制时脚本会立即停止并推送
"账号预约数已达上限"，不会继续无谓重试。

---

## 配置项

配置保存在 `badminton-booking/.env`（首次运行 `--setup` 自动生成）：

| 键 | 必填 | 说明 |
|----|------|------|
| `ZJNU_USERNAME` | ✅ | 学号 |
| `ZJNU_PASSWORD` | ✅ | 密码（明文存本地，请勿提交到仓库） |
| `ZJNU_CAMPUS` | ✅ | `jinhua` 或 `xiaoshan` |
| `ZJNU_SPORT` | ✅ | `badminton` / `pingpong` / `volleyball` |
| `SENDKEY` | ⬜ | Server酱 SendKey，留空则不推送 |

`SENDKEY` 支持回退：若 `badminton-booking/.env` 中没有，会去读项目根目录的 `.env`。
其余键**只**从 `badminton-booking/.env` 读取。

---

## 服务器部署

### 方式一：crontab（推荐）

```bash
crontab -e
```

添加：

```
55 6 * * * cd /root/ZJNU && ./run.sh --loop
```

> ⚠️ **不要写成 `0 7 * * *`**。那样会在 07:00:00 才开始启动 Python、导入依赖、
> 登录并预取数据，等真正发请求时已经过去 2~3 秒，热门场地早没了。

### 方式二：systemd timer

```bash
sudo cp badminton-booking/badminton-booking.service /etc/systemd/system/
sudo cp badminton-booking/badminton-booking.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now badminton-booking.timer
```

> 注意 `badminton-booking.timer` 里的 `OnCalendar` 必须早于 07:00（当前为 `06:55:00`）。
> 同时 `badminton-booking.service` 的 `WorkingDirectory` 和 `ExecStart` 里的路径
> 是 `/root/ZJNU`，部署到其他目录需要一并修改。

---

## Windows 部署

### 环境准备

确保已安装 Python 3 和 Node.js（PyExecJS 需要 Node 运行 `ez.js`）。

推荐用虚拟环境（避免污染系统 Python，且 3.12 下依赖较新）：

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

以**管理员身份**打开 PowerShell，执行（注意用虚拟环境的绝对路径，定时任务不继承 PATH）：

```powershell
schtasks /create /tn "ZJNU抢场" /tr "C:\ZJNU\.venv\Scripts\python.exe C:\ZJNU\badminton-booking\main.py --loop" /sc daily /st 06:54 /f
```

任务已存在时改用 `/change`（**同样需要管理员权限**，否则报 `Access is denied`）：

```powershell
schtasks /change /tn "ZJNU抢场" /tr "C:\ZJNU\.venv\Scripts\python.exe C:\ZJNU\badminton-booking\main.py --loop"
schtasks /change /tn "ZJNU抢场" /enable
```

> `/st` 用 06:54 或 06:55 都可以，只要早于 06:59。脚本会自己等到 07:00。

### 自动唤醒

1. 控制面板 → 电源选项 → 高级电源设置 → 睡眠 → **允许唤醒计时器** → 启用
2. `Win + R` → `taskschd.msc` → "ZJNU抢场" → 属性 → 条件 → 勾选「唤醒计算机运行此任务」

### 防止鼠标误唤醒

```powershell
powercfg /devicequery wake_armed
powercfg /devicedisablewake "HID Keyboard Device"
powercfg /devicedisablewake "HID-compliant mouse"
```

### 自动睡眠（可选）

```powershell
schtasks /create /tn "ZJNU睡眠" /tr "rundll32.exe powrprof.dll,SetSuspendState 0,1,0" /sc daily /st 00:30 /f
```

### 控制台中文与 emoji

Windows 控制台默认是 GBK（cp936）编码，emoji 无法输出。脚本已在启动时把
stdout/stderr 的错误处理改为 `replace`，遇到不支持的字符会降级成 `?` 而不是崩溃。

**`booking.log` 是 UTF-8 的权威日志**，控制台显示乱码不代表运行出错。

---

## 消息推送

通过 [Server酱](https://sct.ftqq.com/) 推送到微信。

配置方式：运行 `./run.sh --setup`，在提示时输入你的 SendKey。不需要则直接回车跳过。

推送时机：

| 场景 | 标题 |
|------|------|
| 预约成功 | 预约成功 🎉 |
| 60 秒内未抢到 | 预约失败 |
| 账号已达 3 场上限 | 账号预约数已达上限 |
| 登录失败 | 登录失效 / Token 失效 |

---

## 项目结构

```
ZJNU/
├── run.sh                        # 快捷启动脚本（bash）
├── README.md                     # 项目主页
├── zjnu.py                       # 原始单文件参考脚本（历史存档，不参与运行）
├── .gitattributes                # 换行符规范化（保证 run.sh 在 Linux 下为 LF）
├── .gitignore
├── .env                          # 可选：仅用于存放 SENDKEY
│
└── badminton-booking/
    ├── main.py                   # CLI 入口（--scan / --loop / --setup）
    ├── config.py                 # 配置管理（.env、场地注册表、设置向导）
    ├── auth.py                   # CAS 登录 + Session 持久化 + Token 校验
    ├── booker.py                 # 抢场引擎（scan / book / loop）
    ├── notify.py                 # Server酱推送
    ├── ez.js                     # CryptoJS AES 密码加密
    ├── requirements.txt          # Python 依赖
    ├── LICENSE                   # Apache License 2.0
    ├── README.md                 # 子目录简版说明
    │
    ├── .env.example              # 配置模板
    ├── crontab.txt               # crontab 参考
    ├── badminton-booking.service # systemd 服务文件
    ├── badminton-booking.timer   # systemd 定时器
    │
    └── ── 以下为运行时生成，已被 .gitignore 忽略 ──
        ├── .env                  # 实际配置（含密码）
        ├── cookies.json          # 会话 Cookie
        ├── token.json            # API Token
        ├── last_booking.json     # 最近一次成功预约记录
        ├── booking.log           # 运行日志（UTF-8）
        └── run_loop.bat          # 本机专用的 loop 启动批处理
```

---

## 常见问题

### 登录失败？

1. 检查学号密码是否正确
2. 运行 `./run.sh --setup` 重新配置
3. 查看 `badminton-booking/booking.log` 确认具体错误

### 预约失败？

- 先跑 `./run.sh --scan` 确认有空场
- 如果 scan 正常但抢不到 → 场地太热门，脚本没问题
- 确认定时任务**在 06:59 之前**启动（见 [抢场原理](#关于精准的实话)）

### 定时任务没反应？

Windows 下先检查任务是否被禁用、路径是否指向正确的 Python：

```powershell
schtasks /query /tn "ZJNU抢场" /v /fo LIST
```

`/st` 时间和 `--loop` 参数都要对。

### 换账号/换运动？

```bash
./run.sh --setup
```

### Cookie/Token 过期？

自动处理。启动时会调用接口**实际验证** token 是否有效，失效则自动重新登录。

### 能同时抢多个场地吗？

可以复制整个目录，配不同的 `badminton-booking/.env`，各自独立运行。
注意同一账号最多同时持有 3 个未使用的场地。

### 能指定只抢某个时段吗？

当前版本不支持。脚本按"由晚到早"的顺序自动尝试所有可用时段。
需要固定时段请改 `booker.py` 的 `_shuffle_within_time()`。

### CAS 系统升级了怎么办？

密码加密在 `ez.js`。如果 CAS 改版导致登录页结构变化，需要更新 `auth.py` 里的
表单字段解析（`execution`、`pwdEncryptSalt`）。欢迎提 Issue 或 PR。

---

## 许可

Apache License 2.0，详见 [badminton-booking/LICENSE](badminton-booking/LICENSE)。

## 致谢

- [CryptoJS](https://github.com/brix/crypto-js) - AES 加密
- [Server酱](https://sct.ftqq.com/) - 微信推送
