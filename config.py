"""
配置文件
- GitHub Actions: 从 Secrets 环境变量读取
- 本地开发: 创建 config.local.py 填入真实 Key（此文件不要提交）
"""

import os
import sys

# ============================================================
# DeepSeek API
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ============================================================
# 飞书自定义机器人 Webhook
# ============================================================
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK_URL", "")

# ============================================================
# 推送时间设置（24小时制）
# ============================================================
PREVIEW_HOUR = 22
MORNING_HOUR = 7

# ============================================================
# Web 服务
# ============================================================
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "http://localhost:5000")
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# ============================================================
# 数据库
# ============================================================
_DB_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(_DB_DIR, exist_ok=True)
DATABASE_URL = f"sqlite:///{os.path.join(_DB_DIR, 'study.db')}"

# ============================================================
# 本地覆盖（如果存在 config.local.py 则用它覆盖上面的值）
# ============================================================
try:
    _local_dir = os.path.dirname(os.path.abspath(__file__))
    if _local_dir not in sys.path:
        sys.path.insert(0, _local_dir)
    import importlib.util
    _spec = importlib.util.spec_from_file_location("_config_local", os.path.join(_local_dir, "config.local.py"))
    if _spec and _spec.loader:
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        for _key in dir(_mod):
            if _key.isupper():
                globals()[_key] = getattr(_mod, _key)
except Exception:
    pass
