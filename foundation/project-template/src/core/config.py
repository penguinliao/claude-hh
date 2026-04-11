"""项目配置 — 环境变量读取，无默认敏感值"""

import os


def get_required_env(key: str) -> str:
    """获取必需的环境变量，未设置则报错"""
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(
            f"环境变量 {key} 未设置！请在 .env 或系统环境中配置。"
        )
    return value


# JWT密钥 — 必须配置，无默认值
JWT_SECRET = get_required_env("JWT_SECRET") if os.environ.get("JWT_SECRET") else None

# 数据库路径
DB_PATH = os.environ.get("DB_PATH", "data.db")

# 服务端口
PORT = int(os.environ.get("PORT", "8000"))

# 调试模式（生产环境必须为False）
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
