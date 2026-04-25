# mypy: ignore-errors
# flake8: noqa
"""Tests for harness.reporter module."""

from __future__ import annotations

import json

from harness.reporter import to_json, to_markdown, to_terminal
from harness.reward import DimensionResult, RewardReport


def _make_sample_report() -> RewardReport:
    """Create a sample RewardReport for testing."""
    dims = [
        DimensionResult(name="functional", score=90, passed=True, details="All good"),
        DimensionResult(name="spec_compliance", score=70, passed=True, details="Mostly covered"),
        DimensionResult(name="type_safety", score=60, passed=True, details="Some issues"),
        DimensionResult(name="security", score=80, passed=True, details="Clean"),
        DimensionResult(name="complexity", score=85, passed=True, details="Low complexity"),
        DimensionResult(name="architecture", score=85, passed=True, details="No violations"),
        DimensionResult(name="secrets", score=100, passed=True, details="No secrets"),
        DimensionResult(name="code_quality", score=75, passed=True, details="Minor issues"),
    ]
    total = (
        90 * 0.33 + 70 * 0.18 + 60 * 0.14 + 80 * 0.12
        + 85 * 0.08 + 85 * 0.05 + 100 * 0.05 + 75 * 0.05
    )
    return RewardReport(
        dimensions=dims,
        total_score=round(total, 1),
        passed=True,
        completeness="complete",
    )


def _make_report_with_skipped() -> RewardReport:
    """Create a report with some skipped dimensions."""
    dims = [
        DimensionResult(name="functional", score=90, passed=True, details="All good"),
        DimensionResult(name="spec_compliance", score=70, passed=True, details="Mostly covered"),
        DimensionResult(
            name="type_safety", score=0, passed=None, status="skipped",
            details="mypy not installed",
        ),
        DimensionResult(name="security", score=80, passed=True, details="Clean"),
        DimensionResult(
            name="complexity", score=0, passed=None, status="skipped",
            details="radon not installed",
        ),
        DimensionResult(name="architecture", score=85, passed=True, details="No violations"),
        DimensionResult(name="secrets", score=100, passed=True, details="No secrets"),
        DimensionResult(name="code_quality", score=75, passed=True, details="Minor issues"),
    ]
    return RewardReport(
        dimensions=dims,
        total_score=80.0,
        passed=True,
        completeness="incomplete",
    )


def test_to_markdown_contains_dimensions() -> None:
    """Markdown output should contain all dimension display names."""
    report = _make_sample_report()
    md = to_markdown(report)
    for name in ("Functional", "Spec Compliance", "Type Safety", "Security",
                 "Complexity", "Architecture", "Secret Safety", "Code Quality"):
        if name not in md:
            raise AssertionError(f"Expected '{name}' in markdown output")


def test_to_markdown_shows_skipped() -> None:
    """Markdown should show skipped dimensions as 'SKIP'."""
    report = _make_report_with_skipped()
    md = to_markdown(report)
    if "SKIP" not in md:
        raise AssertionError("Expected 'SKIP' in markdown output")
    if "skipped" not in md.lower():
        raise AssertionError("Expected 'skipped' in markdown output (case-insensitive)")


def test_to_markdown_shows_completeness() -> None:
    """Markdown should show completeness when not complete."""
    report = _make_report_with_skipped()
    md = to_markdown(report)
    if "incomplete" not in md.lower():
        raise AssertionError("Expected 'incomplete' in markdown output")


def test_to_json_is_valid() -> None:
    """JSON output should be valid JSON and contain expected keys."""
    report = _make_sample_report()
    raw = to_json(report)
    data = json.loads(raw)  # Should not raise
    for key in ("total_score", "passed", "dimensions", "completeness"):
        if key not in data:
            raise AssertionError(f"Expected key '{key}' in JSON output")
    if len(data["dimensions"]) != 8:
        raise AssertionError(f"Expected 8 dimensions, got {len(data['dimensions'])}")


def test_to_json_includes_status() -> None:
    """JSON output should include status field for each dimension."""
    report = _make_report_with_skipped()
    raw = to_json(report)
    data = json.loads(raw)
    statuses = [d["status"] for d in data["dimensions"]]
    if "skipped" not in statuses:
        raise AssertionError(f"Expected 'skipped' in statuses, got {statuses}")
    if "evaluated" not in statuses:
        raise AssertionError(f"Expected 'evaluated' in statuses, got {statuses}")


def test_to_terminal_contains_bars() -> None:
    """Terminal output should contain PASS/FAIL banner + numeric scores.

    (Function name kept for AC compatibility; v0.2+ replaced progress bars
    with verdict banner + numeric scores.)
    """
    import re
    report = _make_sample_report()
    term = to_terminal(report)
    if "PASS" not in term:
        raise AssertionError(f"Expected PASS banner in terminal output:\n{term!r}")
    if not re.search(r"\d+/100", term):
        raise AssertionError(
            f"Expected at least one 'X/100' score in terminal output:\n{term!r}"
        )
    if "Functional" not in term and "Security" not in term:
        raise AssertionError(
            f"Expected dimension display name in terminal output:\n{term!r}"
        )


def test_to_terminal_skipped_dimensions() -> None:
    """Terminal output should show skipped dimensions differently."""
    report = _make_report_with_skipped()
    term = to_terminal(report)
    if "skipped" not in term:
        raise AssertionError("Expected 'skipped' in terminal output")


def test_to_terminal_completeness() -> None:
    """Terminal output should show completeness when incomplete."""
    report = _make_report_with_skipped()
    term = to_terminal(report)
    if "incomplete" not in term.lower():
        raise AssertionError("Expected 'incomplete' in terminal output")
