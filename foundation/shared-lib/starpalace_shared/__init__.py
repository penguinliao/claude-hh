"""starpalace-shared: 星宫跨项目共享库"""

from starpalace_shared.db import db_conn
from starpalace_shared.auth import get_jwt_secret, create_token, verify_token
from starpalace_shared.security import get_cors_config, escape_like, sanitize_path, escape_html
from starpalace_shared.errors import AppError, register_error_handlers
from starpalace_shared.tasks import safe_task
from starpalace_shared.models import StrictBaseModel, OptionalStr
from starpalace_shared.logging_config import setup_logging

__version__ = "0.1.0"

__all__ = [
    "db_conn",
    "get_jwt_secret", "create_token", "verify_token",
    "get_cors_config", "escape_like", "sanitize_path", "escape_html",
    "AppError", "register_error_handlers",
    "safe_task",
    "StrictBaseModel", "OptionalStr",
    "setup_logging",
]
