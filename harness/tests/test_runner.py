# mypy: ignore-errors
# flake8: noqa
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
    if not isinstance(report, HarnessReport):
        raise AssertionError(f"Expected HarnessReport, got {type(report).__name__}")
    if not hasattr(report, "mode"):
        raise AssertionError("Expected HarnessReport to have 'mode' attribute")
    if not hasattr(report, "dimensions"):
        raise AssertionError("Expected HarnessReport to have 'dimensions' attribute")
    if not hasattr(report, "total_score"):
        raise AssertionError("Expected HarnessReport to have 'total_score' attribute")
    if not hasattr(report, "passed"):
        raise AssertionError("Expected HarnessReport to have 'passed' attribute")
    if not hasattr(report, "blocked_by"):
        raise AssertionError("Expected HarnessReport to have 'blocked_by' attribute")
    if not hasattr(report, "completeness"):
        raise AssertionError("Expected HarnessReport to have 'completeness' attribute")
    if not hasattr(report, "skipped_dimensions"):
        raise AssertionError("Expected HarnessReport to have 'skipped_dimensions' attribute")
    if not hasattr(report, "duration_ms"):
        raise AssertionError("Expected HarnessReport to have 'duration_ms' attribute")


# ---------------------------------------------------------------------------
# Three modes
# ---------------------------------------------------------------------------

def test_check_quick_mode():
    """Quick mode should only run code_quality and security."""
    report = check_quick(files=[str(FIXTURES / "clean_code.py")])
    if not (report.mode == "quick"):
        raise AssertionError(f"Expected mode='quick', got {report.mode!r}")
    dim_names = [d.name for d in report.dimensions]
    if "code_quality" not in dim_names:
        raise AssertionError(f"Expected 'code_quality' in dim_names, got {dim_names!r}")
    if "security" not in dim_names:
        raise AssertionError(f"Expected 'security' in dim_names, got {dim_names!r}")
    # Should NOT include full-mode-only dimensions
    if "spec_compliance" in dim_names:
        raise AssertionError(f"Expected 'spec_compliance' NOT in dim_names, got {dim_names!r}")
    if "architecture" in dim_names:
        raise AssertionError(f"Expected 'architecture' NOT in dim_names, got {dim_names!r}")


def test_check_standard_mode():
    """Standard mode should include quick + type_safety + functional + complexity."""
    report = check_standard(files=[str(FIXTURES / "clean_code.py")])
    if not (report.mode == "standard"):
        raise AssertionError(f"Expected mode='standard', got {report.mode!r}")
    dim_names = [d.name for d in report.dimensions]
    if "code_quality" not in dim_names:
        raise AssertionError(f"Expected 'code_quality' in dim_names, got {dim_names!r}")
    if "security" not in dim_names:
        raise AssertionError(f"Expected 'security' in dim_names, got {dim_names!r}")
    if "type_safety" not in dim_names:
        raise AssertionError(f"Expected 'type_safety' in dim_names, got {dim_names!r}")
    if "functional" not in dim_names:
        raise AssertionError(f"Expected 'functional' in dim_names, got {dim_names!r}")
    if "complexity" not in dim_names:
        raise AssertionError(f"Expected 'complexity' in dim_names, got {dim_names!r}")


def test_check_full_mode():
    """Full mode should include all 8 dimensions."""
    report = check_full(files=[str(FIXTURES / "clean_code.py")])
    if not (report.mode == "full"):
        raise AssertionError(f"Expected mode='full', got {report.mode!r}")
    dim_names = [d.name for d in report.dimensions]
    if "code_quality" not in dim_names:
        raise AssertionError(f"Expected 'code_quality' in dim_names, got {dim_names!r}")
    if "security" not in dim_names:
        raise AssertionError(f"Expected 'security' in dim_names, got {dim_names!r}")
    if "type_safety" not in dim_names:
        raise AssertionError(f"Expected 'type_safety' in dim_names, got {dim_names!r}")
    if "functional" not in dim_names:
        raise AssertionError(f"Expected 'functional' in dim_names, got {dim_names!r}")
    if "complexity" not in dim_names:
        raise AssertionError(f"Expected 'complexity' in dim_names, got {dim_names!r}")
    if "spec_compliance" not in dim_names:
        raise AssertionError(f"Expected 'spec_compliance' in dim_names, got {dim_names!r}")
    if "architecture" not in dim_names:
        raise AssertionError(f"Expected 'architecture' in dim_names, got {dim_names!r}")
    if "secrets" not in dim_names:
        raise AssertionError(f"Expected 'secrets' in dim_names, got {dim_names!r}")


# ---------------------------------------------------------------------------
# Score and pass logic
# ---------------------------------------------------------------------------

def test_check_returns_valid_score():
    """Total score should be between 0 and 100."""
    report = check(files=[str(FIXTURES / "clean_code.py")], mode="quick")
    if not (0 <= report.total_score <= 100):
        raise AssertionError(f"Expected total_score in [0, 100], got {report.total_score}")


def test_check_duration_is_positive():
    """Duration should be non-negative."""
    report = check(files=[str(FIXTURES / "clean_code.py")], mode="quick")
    if not (report.duration_ms >= 0):
        raise AssertionError(f"Expected duration_ms>=0, got {report.duration_ms}")


def test_check_completeness_field():
    """Completeness should be one of the valid values."""
    report = check(files=[str(FIXTURES / "clean_code.py")], mode="quick")
    if report.completeness not in ("complete", "incomplete", "minimal"):
        raise AssertionError(
            f"Expected completeness in {{complete, incomplete, minimal}}, got {report.completeness!r}"
        )


def test_check_skipped_dimensions_list():
    """Skipped dimensions should be a list of strings."""
    report = check(files=[str(FIXTURES / "clean_code.py")], mode="quick")
    if not isinstance(report.skipped_dimensions, list):
        raise AssertionError(
            f"Expected skipped_dimensions to be a list, got {type(report.skipped_dimensions).__name__}"
        )
    for name in report.skipped_dimensions:
        if not isinstance(name, str):
            raise AssertionError(f"Expected all skipped_dimensions to be str, got {type(name).__name__}: {name!r}")


def test_check_blocks_on_secrets():
    """Full mode with secret leak should block.

    Accepts blocked_by in {'secrets', 'security'} — see test_compute_reward_blocks_on_secrets
    for rationale (dimension merge).
    """
    report = check_full(files=[str(FIXTURES / "secret_leak.py")])
    if report.blocked_by not in ("secrets", "security"):
        raise AssertionError(
            f"Expected blocked_by in {{secrets, security}}, got {report.blocked_by!r}"
        )
    if not (report.passed is False):
        raise AssertionError(f"Expected passed=False, got {report.passed!r}")


# ---------------------------------------------------------------------------
# Short-circuit logic
# ---------------------------------------------------------------------------

def test_check_empty_files():
    """Empty file list should still return a valid report."""
    report = check(files=[], mode="quick")
    if not isinstance(report, HarnessReport):
        raise AssertionError(f"Expected HarnessReport, got {type(report).__name__}")
    if not (report.total_score >= 0):
        raise AssertionError(f"Expected total_score>=0, got {report.total_score}")
