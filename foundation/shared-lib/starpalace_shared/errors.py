"""统一错误处理 — 所有异常返回标准JSON，不泄露HTML 500"""

import logging
import traceback
from typing import Any

logger = logging.getLogger("starpalace.errors")


class AppError(Exception):
    """应用层异常，带HTTP状态码和用户可见消息。

    用法:
        raise AppError(404, "用户不存在")
        raise AppError(403, "无权操作", detail="需要管理员权限")
    """

    def __init__(self, status_code: int = 500, message: str = "服务器内部错误", detail: str = ""):
        self.status_code = status_code
        self.message = message
        self.detail = detail
        super().__init__(message)


def register_error_handlers(app) -> None:
    """注册全局异常处理器到FastAPI app。

    - AppError → 返回标准JSON + 对应status_code
    - 所有其他Exception → 返回500标准JSON + logger.error记录堆栈
    - 标准格式: {"error": true, "message": "...", "detail": "..."}
    """
    # 延迟导入，避免未安装fastapi时import失败
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        logger.warning("AppError %d: %s (detail=%s)", exc.status_code, exc.message, exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "message": exc.message,
                "detail": exc.detail or "",
            },
        )

    @app.exception_handler(Exception)
    async def handle_generic_error(request: Request, exc: Exception):
        logger.error(
            "未处理异常: %s\n%s",
            str(exc),
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": "服务器内部错误",
                "detail": "",
            },
        )
