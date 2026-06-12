# 浙师大体育场地自动预约 🏸

浙江师范大学（ZJNU）体育场地自动预约脚本，支持多校区、多运动项目。
**每天早上 7:00 准时抢场，微秒级卡秒，一个请求搞定。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue)](https://python.org)

## 目录

- [功能特性](#功能特性)
- [支持的场地](#支持的场地)
- [快速开始](#快速开始)
- [命令说明](#命令说明)
- [抢场原理](#抢场原理)
- [服务器部署](#服务器部署)
- [消息推送](#消息推送)
- [项目结构](#项目结构)
- [常见问题](#常见问题)

---

## 功能特性

- 🎯 **一次配置，永久运行** —— 首次输入学号密码，之后全自动
- 🏫 **多校区** —— 金华校区 / 萧山校区
- 🏃 **多运动** —— 羽毛球 / 乒乓球 / 排球
- 🔐 **自动登录** —— CAS 统一认证 + Token 自动提取
- ⏱️ **精准抢场** —— 6:55 预构建所有订单，7:00:00.000 准时开抢
- 📱 **微信通知** —— Server酱 推送预约结果到微信
- 🔄 **会话保持** —— Cookie + Token 持久化，重启无需重新登录

## 支持的场地

| 校区 | 运动 | 场馆 |
|------|------|------|
| 金华 | 羽毛球 | 北田羽毛球馆、综合馆羽毛球馆 |
| 金华 | 乒乓球 | 风雨操场乒乓球馆 |
| 金华 | 排球 | 风雨操场排球馆 |
| 萧山 | 羽毛球 | 萧山校区热身馆（羽毛球） |

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/OTTO-91/ZJNU.git
cd ZJNU-tycg-order
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
| `./run.sh --scan` | 查看明天空闲场地 |
| `./run.sh --loop` | 等 7:00 准时抢场（cron 用） |
| `./run.sh --setup` | 重新配置账号/校区/运动 |

---

## 抢场原理

```
06:55  脚本启动（--loop 模式）
  ├─ 恢复上次 Session（cookie + token）
  ├─ 预取所有场地和时间段数据
  ├─ 预构建所有可预约订单（JSON payload）
  └─ sleep 到 06:59:58

06:59:58  纯 CPU 空转（微秒级精度）
  └─ 不发送网络请求，避免网络波动

07:00:00.000  精确触发，依次发送下单请求
  ├─ 优先发首选时段，满则自动 fall 到次选
  └─ 每个请求间隔 0.3 秒，避免限流

完成 → 结果写入日志 + Server酱微信推送
```

---

## 服务器部署

### 方式一：crontab（推荐）

```bash
crontab -e
```

添加：
```
0 7 * * * cd /root/ZJNU-tycg-order && ./run.sh --loop
```

### 方式二：systemd timer

```bash
sudo cp badminton-booking/badminton-booking.service /etc/systemd/system/
sudo cp badminton-booking/badminton-booking.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now badminton-booking.timer
```

---

## 消息推送

通过 [Server酱](https://sct.ftqq.com/) 推送到微信。

配置方式：运行 `./run.sh --setup`，在提示时输入你的 SendKey。不需要则直接回车跳过。

---

## 项目结构

```
ZJNU-tycg-order/
├── run.sh                        # 快捷启动脚本
├── README.md                     # 项目主页
├── zjnu.py                       # 原始参考脚本
│
└── badminton-booking/
    ├── main.py                   # CLI 入口（--scan / --loop / --setup）
    ├── config.py                 # 配置管理（.env、场地注册、设置向导）
    ├── auth.py                   # CAS 登录 + Session 持久化
    ├── booker.py                 # 抢场引擎（scan / book / loop）
    ├── notify.py                 # Server酱推送
    ├── ez.js                     # CryptoJS AES 密码加密
    ├── requirements.txt          # Python 依赖
    │
    ├── .env.example              # 配置模板
    ├── crontab.txt               # crontab 参考
    ├── badminton-booking.service # systemd 服务文件
    └── badminton-booking.timer   # systemd 定时器
```

---

## 常见问题

### 登录失败？

1. 检查学号密码是否正确
2. 运行 `./run.sh --setup` 重新配置
3. 查看日志确认具体错误

### 预约失败？

- 先跑 `./run.sh --scan` 确认有空场
- 如果 scan 正常但抢不到 → 场地太热门，脚本没问题

### 换账号/换运动？

```bash
./run.sh --setup
```

### Cookie/Token 过期？

自动处理。启动时检测过期会自动重新登录。

### 能同时抢多个场地吗？

可以复制整个目录，配不同的 `.env`，各自独立运行。

### CAS 系统升级了怎么办？

密码加密在 `ez.js`。如果 CAS 改版，需要更新 `auth.py`。欢迎提 Issue 或 PR。

---

## 许可

MIT License

## 致谢

- [CryptoJS](https://github.com/brix/crypto-js) - AES 加密
- [Server酱](https://sct.ftqq.com/) - 微信推送
