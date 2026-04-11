"""安全异步任务 — 包装create_task，异常自动记日志"""

import asyncio
import logging
import traceback
from typing import Coroutine

logger = logging.getLogger("starpalace.tasks")


def safe_task(coro: Coroutine, name: str = "") -> asyncio.Task:
    """创建安全的异步任务，异常自动记录到日志。

    用法:
        safe_task(send_notification(user_id), name="发送通知")

    后台任务异常时logger.error可见，不会静默吞掉。
    """
    task = asyncio.create_task(coro, name=name or None)

    def _on_done(t: asyncio.Task):
        if t.cancelled():
            logger.info("任务已取消: %s", name or t.get_name())
            return
        exc = t.exception()
        if exc:
            logger.error(
                "后台任务异常 [%s]: %s\n%s",
                name or t.get_name(),
                str(exc),
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            )

    task.add_done_callback(_on_done)
    return task
