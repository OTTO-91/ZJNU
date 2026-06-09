# 浙师大体育场地自动预约 🏸

浙江师范大学（ZJNU）体育场地自动预约脚本，支持多校区、多运动项目。
**每天早上 7:00 准时抢场，微秒级卡秒，一个请求搞定，无需手动操作。**

## 目录

- [功能特性](#功能特性)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [命令说明](#命令说明)
- [抢场原理](#抢场原理)
- [服务器部署](#服务器部署)
- [消息推送](#消息推送)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 功能特性

- 🎯 **一次配置，永久运行** —— 首次输入学号密码 + 选择校区运动，之后全自动
- 🏫 **多校区** —— 金华校区 / 萧山校区
- 🏃 **多运动** —— 羽毛球 / 乒乓球 / 排球
- 🔐 **自动登录** —— CAS 统一认证 + Token 自动提取
- ⏱️ **精准抢场** —— 6:55 预构建所有订单，7:00:00.000 只发一次下单请求
- 📱 **微信通知** —— 通过 Server酱 推送预约结果到微信
- 🔄 **会话保持** —— Cookie + Token 三重持久化，重启无需重新登录

## 支持的场地

| 校区 | 运动 | 场馆 |
|------|------|------|
| 金华 | 羽毛球 | 北田羽毛球馆、综合馆羽毛球馆 |
| 金华 | 乒乓球 | 风雨操场乒乓球馆 |
| 金华 | 排球 | 风雨操场排球馆 |
| 萧山 | 羽毛球 | 浙师大萧山校区热身馆（羽毛球） |

---

## 环境要求

### 必须安装

| 软件 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.8+ | 推荐 3.10+ |
| Node.js | 14+ | execjs 需要，用于 AES 密码加密 |
| pip | 20+ | Python 包管理 |

### 检查安装

```bash
python --version   # 应该 >= 3.8
node --version     # 应该 >= 14
pip --version
```

### 如果没装 Node.js

**Ubuntu / Debian：**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

**CentOS / Rocky Linux：**
```bash
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
sudo yum install -y nodejs
```

**Windows：** 去 [nodejs.org](https://nodejs.org) 下载 LTS 版本安装。

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/OTTO-91/ZJNU-tycg-order.git
cd ZJNU-tycg-order/badminton-booking  # 或直接 cd badminton-booking
```

如果 GitHub 连不上，可以用镜像：
```bash
git clone https://ghproxy.net/https://github.com/OTTO-91/ZJNU-tycg-order.git
```

### 2. 安装 Python 依赖

> 国内服务器务必使用清华/阿里镜像，否则极慢。

```bash
# 清华镜像（推荐）
cd badminton-booking && pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 或者阿里镜像
cd badminton-booking && pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com
```

### 3. 首次运行（配置账号）

```bash
python badminton-booking/main.py
```

按提示依次输入：
1. **学号** —— 例如 `202400000000`
2. **密码** —— 校园统一身份认证密码
3. **校区** —— `1` 金华 或 `2` 萧山
4. **运动项目** —— `1` 羽毛球 / `2` 乒乓球 / `3` 排球（萧山只有羽毛球）

配置自动保存到 `.env` 文件，之后运行不再询问。

### 4. 试运行（查看空场，不预约）

```bash
python badminton-booking/main.py --scan
```

确认能正常返回场地信息后再部署定时任务。

---

## 命令说明

| 命令 | 用途 | 适用场景 |
|------|------|---------|
| `python badminton-booking/main.py` | 立即预约明天场地 | 手动测试 |
| `python badminton-booking/main.py --scan` | 查看明天空闲场地 | 检查场地情况 |
| `python badminton-booking/main.py --loop` | 等到 7:00 准时抢场 | cron / 定时任务 |
| `python badminton-booking/main.py --setup` | 重新配置账号/校区/运动 | 换号或换场地 |

**重要：** `--loop` 模式会阻塞等待到早上 7:00，只适合 cron 调用。手动测试用不带参数的方式（立即预约）。

---

## 抢场原理

```
06:55  cron 触发脚本（--loop 模式）
  ├─ 恢复上次的 Session（cookie + token），无需重新登录
  ├─ 访问场馆页面，预取所有场地和时间段
  ├─ 预构建所有可预约时段的订单数据（JSON payload）
  └─ sleep 到 06:59:58，留 2 秒余量

06:59:58  纯 CPU 空转（微秒级精度），等待精确到毫秒
  └─ 不发送任何网络请求，避免因网络波动错过时机

07:00:00.000  精确触发，依次发送 CreateOrder 请求
  ├─ 优先发首选时段
  ├─ 首选满则自动 fall 到次选、三选……
  └─ 每个请求间隔 0.3 秒，避免触发限流

完成  结果写入 booking.log，通过 Server酱 推送到微信
```

> **为什么 7:00 之前不发请求？** 系统在 7:00 才开放预约，提前发会全部失败。我们只提前准备好数据，准时秒发。

---

## 服务器部署

### 方案一：crontab（最简单）

适用于任何 Linux 服务器，包括云服务器、树莓派、软路由等。

```bash
# 编辑 crontab
crontab -e
```

添加一行（注意替换路径）：

```
55 6 * * * cd /你的路径/ZJNU-tycg-order/badminton-booking && /usr/bin/python3 main.py --loop >> booking.log 2>&1
```

> ⚠️ 务必使用**绝对路径**。`which python3` 查看 Python 路径。

**验证 crontab 已生效：**
```bash
crontab -l
```

### 方案二：systemd timer（推荐，更可靠）

适合不想依赖 cron 的场景，systemd 有更好的日志和错误处理。

**1. 创建 service 文件：**

```bash
sudo nano /etc/systemd/system/badminton-booking.service
```

```
[Unit]
Description=ZJNU Badminton Court Auto-Booking
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/你的路径/ZJNU-tycg-order/badminton-booking
ExecStart=/usr/bin/python3 main.py --loop
StandardOutput=append:/你的路径/ZJNU-tycg-order/badminton-booking/booking.log
StandardError=append:/你的路径/ZJNU-tycg-order/badminton-booking/booking.log
User=root

[Install]
WantedBy=multi-user.target
```

**2. 创建 timer 文件：**

```bash
sudo nano /etc/systemd/system/badminton-booking.timer
```

```
[Unit]
Description=Daily ZJNU Court Booking at 06:55

[Timer]
OnCalendar=daily
Persistent=true
WakeSystem=false

[Install]
WantedBy=timers.target
```

> `OnCalendar=daily` 默认凌晨 00:00 触发，项目内部会自己 sleep 到 7:00。

**3. 启用并启动：**

```bash
sudo systemctl daemon-reload
sudo systemctl enable badminton-booking.timer
sudo systemctl start badminton-booking.timer
```

**4. 查看状态：**

```bash
systemctl status badminton-booking.timer   # 定时器状态
systemctl list-timers                      # 所有定时器
journalctl -u badminton-booking -f         # 实时日志
```

### 验证部署

部署后建议手动跑一次确认正常：
```bash
cd /你的路径/ZJNU-tycg-order/badminton-booking
python3 main.py --scan
```

---

## 消息推送

通过 [Server酱](https://sct.ftqq.com/) 将预约结果推送到微信。

### 方式一：首次配置时输入（推荐）

运行 `python badminton-booking/main.py --setup`，在选择完校区和运动后，会提示：

```
--- 可选配置：微信推送通知 ---
如果配置 Server酱，预约结果会自动推送到微信。
获取 SendKey: https://sct.ftqq.com/ (微信扫码登录)
不需要则直接回车跳过
SendKey: 
```

填入你的 SendKey 即可。不填直接回车跳过，预约成功/失败**不会**推送通知，但也不会报错。

### 方式二：手动写入 .env

```bash
echo "SENDKEY=你的SendKey" >> .env
```

或编辑 `.env` 添加一行：
```
SENDKEY=SCT123456xxxxxxxxxxxxxxxx
```

### 验证推送

```bash
python -c "from notify import sc_send; sc_send(\"你的SendKey\", \"测试\", \"如果你收到这条消息，推送配置成功\")"
```

### 推送内容示例

成功时：
```
标题：预约成功 🎉
内容：
场地: 北田羽毛球馆
时间: 18:00-19:00
场号: #3
日期: 2026-06-10
```

---

## 项目结构

```
ZJNU-tycg-order/
├── README.md                    # 你正在看的
├── zjnu.py                      # 旧版独立脚本（仍可用）
└── badminton-booking/           # 新版项目

├── main.py              # CLI 入口（--scan / --loop / --setup）
├── config.py            # 配置管理（.env 读取、场地注册、设置向导）
├── auth.py              # 认证模块（CAS SSO 登录 + Session 持久化）
├── booker.py            # 核心引擎（scan / book / loop 三种模式）
├── notify.py            # 消息推送（Server酱）
├── ez.js                # CryptoJS AES 加密（登录密码加密）
├── requirements.txt     # Python 依赖清单
│
├── .env                 # 账号配置（首次运行自动生成，不要提交 Git）
├── .env.example         # 配置文件模板
├── .gitignore           # Git 忽略规则
│
├── cookies.json         # Cookie 持久化（自动生成）
├── token.json           # Token 持久化（自动生成）
├── booking.log          # 运行日志
└── last_booking.json    # 最近一次预约记录
```

### 登录态管理

项目采用**三重持久化**保证会话稳定，避免每次都要重新登录：

| 机制 | 文件 | 说明 |
|------|------|------|
| Cookie | `cookies.json` | 每次请求后自动保存，JSON 明文可读 |
| Token | `token.json` | 含保存时间戳，验证过期自动刷新 |
| Session | 自动恢复 | 启动时加载 cookie/token，失败则自动重登录 |

重启脚本自动恢复，过期自动重登。完全无需人工干预。

---

## 常见问题

### Q1：提示 `execjs` 找不到 Node.js？

安装 Node.js 即可。如果已安装但仍然报错，检查环境变量：
```bash
which node     # Linux
where node     # Windows
```

### Q2：pip 安装报错或太慢？

换国内镜像：
```bash
cd badminton-booking && pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

永久生效：
```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q3：登录失败？

1. 检查学号密码是否正确（能否在浏览器正常登录）
2. 检查 CAS 页面是否改版（运行 `python badminton-booking/main.py --setup` 重新配置）
3. 查看日志：`cat booking.log | tail -30`

### Q4：预约失败？

- 查看日志确认失败原因：`cat booking.log | tail -20`
- 确认 `python badminton-booking/main.py --scan` 能看到空场
- 如果 `--scan` 正常但抢不到，说明脚本没问题，只是场地太热门秒没

### Q5：换运动项目？

```bash
python badminton-booking/main.py --setup
```

### Q6：换账号（帮同学抢）？

```bash
python badminton-booking/main.py --setup
```

### Q7：Cookie / Token 过期了怎么办？

自动处理，无需手动操作。脚本启动时会检测，过期自动重新登录。

### Q8：能不能同时抢多个场地？

可以。需要改两个地方：
1. `config.py` 的 `COURT_REGISTRY` 中添加多组场馆
2. 或者跑多个实例（复制整个目录，配不同的 `.env`）

### Q9：Windows 能用吗？

能。安装 Python 和 Node.js 后直接 `python badminton-booking/main.py`。但**定时任务建议用 Linux 服务器**，Windows 的定时任务不如 cron 稳定。

### Q10：学校 CAS 系统升级了怎么办？

密码加密逻辑在 `ez.js` 中。如果 CAS 改版（更改了加密方式、添加了验证码等），需要更新 `auth.py` 中的 `login()` 方法。欢迎提 Issue 或 PR。

---

## 许可

MIT License

## 致谢

- [CryptoJS](https://github.com/brix/crypto-js) - AES 加密库
- [Server酱](https://sct.ftqq.com/) - 微信推送服务


