"""安全默认值 — CORS配置/SQL转义/路径净化/HTML转义"""

import html as _html
import os
import re


def get_cors_config(allowed_origins: list[str]) -> dict:
    """生成CORS配置字典，禁止通配符*。

    Args:
        allowed_origins: 允许的源列表，如 ["https://example.com"]
    Returns:
        dict，可直接传给 CORSMiddleware(**config)
    Raises:
        ValueError: 传入"*"时抛出
    """
    if "*" in allowed_origins:
        raise ValueError(
            "CORS不允许使用通配符'*'，请明确指定允许的域名列表。"
            "例如: ['https://your-domain.com']"
        )
    return {
        "allow_origins": allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        "allow_headers": ["*"],
    }


def escape_like(s: str) -> str:
    """转义SQL LIKE子句中的特殊字符 % 和 _。

    用法:
        safe = escape_like(user_input)
        cursor.execute("SELECT * FROM t WHERE name LIKE ? ESCAPE '\\\\'", (f"%{safe}%",))
    """
    s = s.replace("\\", "\\\\")  # 先转义反斜杠本身
    s = s.replace("%", "\\%")
    s = s.replace("_", "\\_")
    return s


def sanitize_path(path: str) -> str:
    """净化文件路径，移除路径穿越攻击。

    - 移除 .. 组件
    - 移除开头的 / （变为相对路径）
    - 移除空组件（连续的/）
    - 规范化路径

    Returns:
        安全的相对路径字符串
    """
    # 分割路径组件
    parts = path.replace("\\", "/").split("/")
    # 过滤危险组件
    safe_parts = [
        p for p in parts
        if p and p != ".." and p != "."
    ]
    # 如果过滤后为空，返回空字符串
    if not safe_parts:
        return ""
    return os.path.join(*safe_parts)


def escape_html(text: str) -> str:
    """HTML转义，防止XSS注入。

    转义 &, <, >, ", ' 五个字符。
    """
    return _html.escape(text, quote=True)
