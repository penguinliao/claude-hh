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


def test_to_markdown_contains_dimensions():
    """Markdown output should contain all dimension display names."""
    report = _make_sample_report()
    md = to_markdown(report)
    assert "Functional" in md
    assert "Spec Compliance" in md
    assert "Type Safety" in md
    assert "Security" in md
    assert "Complexity" in md
    assert "Architecture" in md
    assert "Secret Safety" in md
    assert "Code Quality" in md


def test_to_markdown_shows_skipped():
    """Markdown should show skipped dimensions as 'SKIP'."""
    report = _make_report_with_skipped()
    md = to_markdown(report)
    assert "SKIP" in md
    assert "skipped" in md.lower()


def test_to_markdown_shows_completeness():
    """Markdown should show completeness when not complete."""
    report = _make_report_with_skipped()
    md = to_markdown(report)
    assert "incomplete" in md.lower()


def test_to_json_is_valid():
    """JSON output should be valid JSON and contain expected keys."""
    report = _make_sample_report()
    raw = to_json(report)
    data = json.loads(raw)  # Should not raise
    assert "total_score" in data
    assert "passed" in data
    assert "dimensions" in data
    assert "completeness" in data
    assert len(data["dimensions"]) == 8


def test_to_json_includes_status():
    """JSON output should include status field for each dimension."""
    report = _make_report_with_skipped()
    raw = to_json(report)
    data = json.loads(raw)
    statuses = [d["status"] for d in data["dimensions"]]
    assert "skipped" in statuses
    assert "evaluated" in statuses


def test_to_terminal_contains_bars():
    """Terminal output should contain progress bar characters."""
    report = _make_sample_report()
    term = to_terminal(report)
    # Progress bar uses block chars: \u2588 (filled) and \u2591 (empty)
    assert "\u2588" in term or "\u2591" in term, "Expected progress bar characters in terminal output"


def test_to_terminal_skipped_dimensions():
    """Terminal output should show skipped dimensions differently."""
    report = _make_report_with_skipped()
    term = to_terminal(report)
    assert "skipped" in term


def test_to_terminal_completeness():
    """Terminal output should show completeness when incomplete."""
    report = _make_report_with_skipped()
    term = to_terminal(report)
    assert "incomplete" in term.lower()
