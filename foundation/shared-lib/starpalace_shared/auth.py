"""统一认证 — JWT签发/验证 + FastAPI依赖注入"""

import os
import time
from typing import Any

import jwt


def get_jwt_secret() -> str:
    """从环境变量JWT_SECRET读取密钥，未配置则raise RuntimeError。"""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET环境变量未配置。请设置: export JWT_SECRET='your-secret-key'"
        )
    return secret


def create_token(user_id: str, secret: str, expires_hours: int = 24) -> str:
    """签发JWT token。

    Args:
        user_id: 用户ID
        secret: 签名密钥
        expires_hours: 过期时间（小时），默认24
    Returns:
        JWT token字符串
    """
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + expires_hours * 3600,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def verify_token(token: str, secret: str) -> dict[str, Any]:
    """验证JWT token，返回payload。

    Raises:
        jwt.ExpiredSignatureError: token已过期
        jwt.InvalidTokenError: token无效
    """
    return jwt.decode(token, secret, algorithms=["HS256"])


def get_current_user():
    """FastAPI Depends依赖注入，从请求Header中提取并验证用户。

    用法:
        @app.get("/me")
        async def me(user=Depends(get_current_user)):
            return user
    """
    # 延迟导入，避免未安装fastapi时import失败
    from fastapi import Depends, HTTPException, Header

    async def _extract_user(authorization: str = Header(...)) -> dict:
        if not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization header格式错误，需要Bearer token")
        token = authorization[7:]
        secret = get_jwt_secret()
        try:
            payload = verify_token(token, secret)
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token已过期")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Token无效")
        return payload

    return Depends(_extract_user)
