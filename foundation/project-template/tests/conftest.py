"""测试fixtures — 统一的测试基础设施"""

import os
import pytest

# 测试环境标记
os.environ.setdefault("JWT_SECRET", "test-secret-for-testing-only")
os.environ.setdefault("DEBUG", "true")


@pytest.fixture
def test_db(tmp_path):
    """提供临时测试数据库"""
    db_path = tmp_path / "test.db"
    os.environ["DB_PATH"] = str(db_path)
    yield db_path


@pytest.fixture
def test_user_id():
    """测试用户ID（dev_前缀，不影响真实数据）"""
    return "dev_test_user_001"
