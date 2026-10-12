# 浙师大体育场地自动预约

> 📖 **完整文档请查看** [项目主页](../README.md)

## 快速开始

### Linux / macOS

```bash
# 安装依赖
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 首次配置
python main.py --setup

# 查看空场
python main.py --scan
```

或使用项目根目录的快捷脚本：

```bash
cd .. && ./run.sh --scan
```

### Windows

```powershell
# 在项目根目录创建虚拟环境
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r badminton-booking\requirements.txt

# 首次配置
..\.venv\Scripts\python.exe main.py --setup

# 查看空场
..\.venv\Scripts\python.exe main.py --scan
```

> `run.sh` 是 bash 脚本，Windows 原生环境不适用，请直接用上面的 Python 命令。
> 详细部署步骤见 [项目主页 - Windows 部署](../README.md#windows-部署)。

## 命令

| 命令 | 用途 |
|------|------|
| `python main.py` | 立即预约明天场地 |
| `python main.py --scan` | 查看明天空闲场地（只读） |
| `python main.py --loop` | 等 7:00 准时抢场（定时任务用） |
| `python main.py --setup` | 重新配置账号/校区/运动 |

> `--loop` 模式必须在 **06:59 之前**启动，否则预取数据会占用掉关键的头几秒。

## 文件说明

| 文件 | 用途 |
|------|------|
| `main.py` | CLI 入口（--scan / --loop / --setup） |
| `config.py` | 配置管理（.env、场地注册表、设置向导） |
| `auth.py` | CAS 登录 + Session 持久化 + Token 校验 |
| `booker.py` | 抢场引擎（scan / book / loop） |
| `notify.py` | Server酱推送 |
| `ez.js` | AES 密码加密 |

运行时生成（已 gitignore）：`.env`、`cookies.json`、`token.json`、
`last_booking.json`、`booking.log`。

## 部署

- [服务器部署（crontab / systemd）](../README.md#服务器部署)
- [Windows 部署（计划任务）](../README.md#windows-部署)

## 许可

Apache License 2.0，详见 [LICENSE](LICENSE)。
