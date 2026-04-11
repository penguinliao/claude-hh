"""FastAPI应用 — 安全默认配置"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="My Project", docs_url="/docs" if __import__("os").environ.get("DEBUG") else None)

# CORS — 必须指定具体origins，禁止*
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    # 添加你的前端域名
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


# 全局异常处理 — 所有错误返回JSON，不返回HTML 500
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"未处理异常: {exc}", exc_info=True)
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"error": True, "message": "服务器内部错误", "detail": str(exc) if __import__("os").environ.get("DEBUG") else "请稍后重试"},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}
