"""starpalace-shared 关键功能测试"""

import asyncio
import logging
import os
import sqlite3
import tempfile
import unittest

from starpalace_shared.db import db_conn
from starpalace_shared.security import get_cors_config, sanitize_path, escape_like, escape_html
from starpalace_shared.tasks import safe_task
from starpalace_shared.models import StrictBaseModel
from starpalace_shared.logging_config import setup_logging


class TestDbConn(unittest.TestCase):
    """数据库连接池测试"""

    def test_db_conn_auto_rollback(self):
        """异常时自动rollback，已插入的数据不会持久化。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # 先建表
            with db_conn(db_path) as conn:
                conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")

            # 插入后抛异常 → 应该rollback
            with self.assertRaises(ValueError):
                with db_conn(db_path) as conn:
                    conn.execute("INSERT INTO t (val) VALUES (?)", ("should_rollback",))
                    raise ValueError("模拟异常")

            # 验证数据未持久化
            with db_conn(db_path) as conn:
                row = conn.execute("SELECT COUNT(*) FROM t").fetchone()
                self.assertEqual(row[0], 0)
        finally:
            os.unlink(db_path)

    def test_db_conn_auto_commit(self):
        """正常退出时自动commit。"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            with db_conn(db_path) as conn:
                conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
                conn.execute("INSERT INTO t (val) VALUES (?)", ("committed",))

            with db_conn(db_path) as conn:
                row = conn.execute("SELECT val FROM t").fetchone()
                self.assertEqual(row[0], "committed")
        finally:
            os.unlink(db_path)


class TestAuth(unittest.TestCase):
    """认证模块测试"""

    def test_jwt_secret_missing_raises(self):
        """JWT_SECRET未配置时调用get_jwt_secret应raise RuntimeError。"""
        # 确保环境变量不存在
        old = os.environ.pop("JWT_SECRET", None)
        try:
            from starpalace_shared.auth import get_jwt_secret
            with self.assertRaises(RuntimeError) as ctx:
                get_jwt_secret()
            self.assertIn("JWT_SECRET", str(ctx.exception))
        finally:
            if old is not None:
                os.environ["JWT_SECRET"] = old

    def test_jwt_roundtrip(self):
        """签发的token能正确验证。"""
        from starpalace_shared.auth import create_token, verify_token
        secret = "test-secret-key-12345"
        token = create_token("user_123", secret, expires_hours=1)
        payload = verify_token(token, secret)
        self.assertEqual(payload["sub"], "user_123")


class TestSecurity(unittest.TestCase):
    """安全模块测试"""

    def test_cors_wildcard_rejected(self):
        """CORS传入*时应raise ValueError。"""
        with self.assertRaises(ValueError) as ctx:
            get_cors_config(["*"])
        self.assertIn("通配符", str(ctx.exception))

    def test_cors_valid(self):
        """正常域名列表应返回配置字典。"""
        config = get_cors_config(["https://example.com"])
        self.assertEqual(config["allow_origins"], ["https://example.com"])
        self.assertTrue(config["allow_credentials"])

    def test_sanitize_path(self):
        """路径穿越攻击应被净化。"""
        result = sanitize_path("../../etc/passwd")
        self.assertNotIn("..", result)
        self.assertEqual(result, os.path.join("etc", "passwd"))

    def test_sanitize_path_complex(self):
        """复杂路径穿越。"""
        result = sanitize_path("/foo/../bar/../../etc/shadow")
        self.assertNotIn("..", result)
        # 应保留安全部分
        self.assertIn("etc", result)

    def test_escape_like(self):
        """SQL LIKE特殊字符应被转义。"""
        self.assertEqual(escape_like("100%"), "100\\%")
        self.assertEqual(escape_like("a_b"), "a\\_b")

    def test_escape_html(self):
        """HTML特殊字符应被转义。"""
        result = escape_html('<script>alert("xss")</script>')
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)


class TestTasks(unittest.TestCase):
    """异步任务测试"""

    def test_safe_task_logs_exception(self):
        """后台任务异常时logger.error可见。"""

        async def _run():
            async def failing_task():
                raise RuntimeError("模拟后台任务崩溃")

            with self.assertLogs("starpalace.tasks", level="ERROR") as cm:
                task = safe_task(failing_task(), name="测试任务")
                # 等待任务完成
                await asyncio.sleep(0.1)

            # 检查日志包含异常信息
            log_output = "\n".join(cm.output)
            self.assertIn("模拟后台任务崩溃", log_output)
            self.assertIn("测试任务", log_output)

        asyncio.run(_run())


class TestModels(unittest.TestCase):
    """Pydantic模型测试"""

    def test_strict_model_rejects_none(self):
        """StrictBaseModel的子类中 str字段传None应ValidationError。"""
        from pydantic import ValidationError

        class User(StrictBaseModel):
            name: str

        with self.assertRaises(ValidationError):
            User(name=None)

    def test_strict_model_rejects_type_coercion(self):
        """StrictBaseModel不允许隐式类型转换。"""
        from pydantic import ValidationError

        class Item(StrictBaseModel):
            count: int

        # 字符串"5"不应被隐式转为int
        with self.assertRaises(ValidationError):
            Item(count="5")


class TestLogging(unittest.TestCase):
    """日志配置测试"""

    def test_setup_logging(self):
        """setup_logging返回配置好的logger。"""
        logger = setup_logging("test_app", level="DEBUG")
        self.assertEqual(logger.name, "test_app")
        self.assertEqual(logger.level, logging.DEBUG)
        self.assertTrue(len(logger.handlers) > 0)


if __name__ == "__main__":
    unittest.main()
