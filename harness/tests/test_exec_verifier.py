# mypy: ignore-errors
# flake8: noqa
"""Tests for harness.exec_verifier module."""

from __future__ import annotations

from pathlib import Path

from harness.exec_verifier import VerifyResult, verify_import

FIXTURES = Path(__file__).parent / "fixtures"


def test_verify_import_success() -> None:
    """A normal Python file should import successfully."""
    result = verify_import(str(FIXTURES / "clean_code.py"))
    if result.passed is not True:
        raise AssertionError(f"Expected pass but got: {result.error_message}")


def test_verify_import_failure() -> None:
    """ModuleNotFoundError on a syntactically-valid file is treated as warn-pass.

    Rationale: v0.1.1 changed verify_import to soft-pass ImportError /
    ModuleNotFoundError when compile() succeeded. This avoids false-failing
    code that imports package-internal modules where the subprocess can't
    resolve sys.path. A real syntax error still hard-fails (see test_verify_import_syntax_error).
    """
    result = verify_import(str(FIXTURES / "import_error.py"))
    if result.passed is not True:
        raise AssertionError(
            f"Expected warn-pass but got passed={result.passed}, error={result.error_message}"
        )
    if result.error_type not in ("ModuleNotFoundError", "ImportError"):
        raise AssertionError(
            f"Expected error_type ModuleNotFoundError or ImportError, got {result.error_type!r}"
        )
    if result.error_message is None:
        raise AssertionError("Expected error_message to be set")
    if "(warn, compile OK)" not in result.error_message:
        raise AssertionError(
            f"Expected '(warn, compile OK)' in error_message, got: {result.error_message!r}"
        )


def test_verify_import_syntax_error() -> None:
    """A file with a real SyntaxError must hard-fail (not warn-pass).

    Uses an in-test tempfile so we don't ship a permanently-broken fixture
    that would conflict with hooks scanning tests/fixtures/.
    """
    import shutil
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="test_verify_syntax_")
    try:
        bad = Path(tmpdir) / "bad.py"
        bad.write_text("def broken(\n    return 'missing paren'\n", encoding="utf-8")
        result = verify_import(str(bad))
        if result.passed is not False:
            raise AssertionError(
                f"Real SyntaxError must hard-fail, got passed={result.passed}"
            )
        if result.error_type != "SyntaxError":
            raise AssertionError(
                f"Expected error_type 'SyntaxError', got {result.error_type!r}"
            )
        if result.error_message is None:
            raise AssertionError("Expected error_message to be set for SyntaxError")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_verify_result_fields() -> None:
    """VerifyResult should have passed, error_type, and error_message fields."""
    r = VerifyResult(passed=True)
    if r.passed is not True:
        raise AssertionError("Expected passed=True")
    if r.error_type is not None:
        raise AssertionError(f"Expected error_type=None, got {r.error_type!r}")
    if r.error_message is not None:
        raise AssertionError(f"Expected error_message=None, got {r.error_message!r}")

    r2 = VerifyResult(
        passed=False,
        error_type="SyntaxError",
        error_message="invalid syntax",
    )
    if r2.passed is not False:
        raise AssertionError("Expected passed=False")
    if r2.error_type != "SyntaxError":
        raise AssertionError(f"Expected error_type='SyntaxError', got {r2.error_type!r}")
    if r2.error_message != "invalid syntax":
        raise AssertionError(
            f"Expected error_message='invalid syntax', got {r2.error_message!r}"
        )
