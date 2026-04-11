"""Tests for harness.exec_verifier module."""

from __future__ import annotations

from pathlib import Path

from harness.exec_verifier import VerifyResult, verify_import

FIXTURES = Path(__file__).parent / "fixtures"


def test_verify_import_success():
    """A normal Python file should import successfully."""
    result = verify_import(str(FIXTURES / "clean_code.py"))
    assert result.passed is True, f"Expected pass but got: {result.error_message}"


def test_verify_import_failure():
    """A file with import of nonexistent module should fail."""
    result = verify_import(str(FIXTURES / "import_error.py"))
    assert result.passed is False
    assert result.error_type is not None
    assert result.error_message is not None


def test_verify_result_fields():
    """VerifyResult should have passed, error_type, and error_message fields."""
    r = VerifyResult(passed=True)
    assert r.passed is True
    assert r.error_type is None
    assert r.error_message is None

    r2 = VerifyResult(
        passed=False,
        error_type="SyntaxError",
        error_message="invalid syntax",
    )
    assert r2.passed is False
    assert r2.error_type == "SyntaxError"
    assert r2.error_message == "invalid syntax"
