"""Tests for harness.runner module."""

from __future__ import annotations

from pathlib import Path

from harness.runner import HarnessReport, check, check_full, check_quick, check_standard

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# HarnessReport structure
# ---------------------------------------------------------------------------

def test_harness_report_has_required_fields():
    """HarnessReport should have mode, dimensions, total_score, etc."""
    report = check(files=[str(FIXTURES / "clean_code.py")], mode="quick")
    assert isinstance(report, HarnessReport)
    assert hasattr(report, "mode")
    assert hasattr(report, "dimensions")
    assert hasattr(report, "total_score")
    assert hasattr(report, "passed")
    assert hasattr(report, "blocked_by")
    assert hasattr(report, "completeness")
    assert hasattr(report, "skipped_dimensions")
    assert hasattr(report, "duration_ms")


# ---------------------------------------------------------------------------
# Three modes
# ---------------------------------------------------------------------------

def test_check_quick_mode():
    """Quick mode should only run code_quality and security."""
    report = check_quick(files=[str(FIXTURES / "clean_code.py")])
    assert report.mode == "quick"
    dim_names = [d.name for d in report.dimensions]
    assert "code_quality" in dim_names
    assert "security" in dim_names
    # Should NOT include full-mode-only dimensions
    assert "spec_compliance" not in dim_names
    assert "architecture" not in dim_names


def test_check_standard_mode():
    """Standard mode should include quick + type_safety + functional + complexity."""
    report = check_standard(files=[str(FIXTURES / "clean_code.py")])
    assert report.mode == "standard"
    dim_names = [d.name for d in report.dimensions]
    assert "code_quality" in dim_names
    assert "security" in dim_names
    assert "type_safety" in dim_names
    assert "functional" in dim_names
    assert "complexity" in dim_names


def test_check_full_mode():
    """Full mode should include all 8 dimensions."""
    report = check_full(files=[str(FIXTURES / "clean_code.py")])
    assert report.mode == "full"
    dim_names = [d.name for d in report.dimensions]
    assert "code_quality" in dim_names
    assert "security" in dim_names
    assert "type_safety" in dim_names
    assert "functional" in dim_names
    assert "complexity" in dim_names
    assert "spec_compliance" in dim_names
    assert "architecture" in dim_names
    assert "secrets" in dim_names


# ---------------------------------------------------------------------------
# Score and pass logic
# ---------------------------------------------------------------------------

def test_check_returns_valid_score():
    """Total score should be between 0 and 100."""
    report = check(files=[str(FIXTURES / "clean_code.py")], mode="quick")
    assert 0 <= report.total_score <= 100


def test_check_duration_is_positive():
    """Duration should be non-negative."""
    report = check(files=[str(FIXTURES / "clean_code.py")], mode="quick")
    assert report.duration_ms >= 0


def test_check_completeness_field():
    """Completeness should be one of the valid values."""
    report = check(files=[str(FIXTURES / "clean_code.py")], mode="quick")
    assert report.completeness in ("complete", "incomplete", "minimal")


def test_check_skipped_dimensions_list():
    """Skipped dimensions should be a list of strings."""
    report = check(files=[str(FIXTURES / "clean_code.py")], mode="quick")
    assert isinstance(report.skipped_dimensions, list)
    for name in report.skipped_dimensions:
        assert isinstance(name, str)


def test_check_blocks_on_secrets():
    """Full mode with secret leak should block."""
    report = check_full(files=[str(FIXTURES / "secret_leak.py")])
    assert report.blocked_by == "secrets"
    assert report.passed is False


# ---------------------------------------------------------------------------
# Short-circuit logic
# ---------------------------------------------------------------------------

def test_check_empty_files():
    """Empty file list should still return a valid report."""
    report = check(files=[], mode="quick")
    assert isinstance(report, HarnessReport)
    assert report.total_score >= 0
