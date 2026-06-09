# 浙师大体育场地自动预约

> 📖 **完整文档请查看** [项目根目录 README](../README.md)

## 快速开始

```bash
# 安装依赖（国内用清华镜像）
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 首次配置
python main.py

# 查看空场
python main.py --scan
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `main.py` | CLI 入口 |
| `config.py` | 配置管理 |
| `auth.py` | CAS 登录 + Session 持久化 |
| `booker.py` | 抢场引擎 |
| `notify.py` | Server酱推送 |
| `ez.js` | AES 加密 |

详细文档 → [../README.md](../README.md)
