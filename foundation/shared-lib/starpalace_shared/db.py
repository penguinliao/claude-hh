"""安全数据库连接池 — SQLite with WAL + auto commit/rollback/close"""

import sqlite3
from contextlib import contextmanager


@contextmanager
def db_conn(db_path: str = "data.db"):
    """SQLite连接的context manager，自动commit/rollback/close。

    用法:
        with db_conn("my.db") as conn:
            conn.execute("INSERT INTO t VALUES (?)", (1,))
        # 正常退出自动commit+close
        # 异常时自动rollback+close，不泄漏连接
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # 开启WAL模式，提升并发读写性能
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
