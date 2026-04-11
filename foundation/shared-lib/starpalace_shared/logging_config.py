"""统一日志配置 — 标准格式 + 不依赖print"""

import logging
import sys


def setup_logging(name: str, level: str = "INFO") -> logging.Logger:
    """配置并返回一个标准格式的logger。

    Args:
        name: logger名称，通常用项目名如 "xiaokun", "dapeng"
        level: 日志级别，默认INFO
    Returns:
        配置好的Logger实例
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加handler
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
