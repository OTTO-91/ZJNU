# 浙师大体育场地自动预约

> 📖 **完整文档请查看** [项目主页](../README.md)

## 快速开始

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

## 文件说明

| 文件 | 用途 |
|------|------|
| `main.py` | CLI 入口（--scan / --loop / --setup） |
| `config.py` | 配置管理（.env、场地注册、设置向导） |
| `auth.py` | CAS 登录 + Session 持久化 |
| `booker.py` | 抢场引擎（scan / book / loop） |
| `notify.py` | Server酱推送 |
| `ez.js` | AES 密码加密 |

## 部署

参考 [项目主页 - 服务器部署](../README.md#服务器部署)
