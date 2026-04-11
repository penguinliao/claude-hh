"""Tests for harness.reward module."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from harness.reward import (
    DimensionResult,
    RewardConfig,
    RewardReport,
    compute_reward,
    score_code_quality,
    score_complexity,
    score_secrets,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# RewardConfig
# ---------------------------------------------------------------------------

def test_reward_config_defaults():
    """Default weights should sum to 1.0 (i.e. 100%)."""
    cfg = RewardConfig()
    total = sum(cfg.weights.values())
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


def test_reward_config_has_complexity():
    """Config should include complexity weight."""
    cfg = RewardConfig()
    assert "complexity" in cfg.weights
    assert cfg.weights["complexity"] == 0.08


# ---------------------------------------------------------------------------
# DimensionResult
# ---------------------------------------------------------------------------

def test_dimension_result_creation():
    """DimensionResult should store name, score, passed, details, and status."""
    dim = DimensionResult(name="test_dim", score=85, passed=True, details="all good")
    assert dim.name == "test_dim"
    assert dim.score == 85
    assert dim.passed is True
    assert dim.details == "all good"
    assert dim.status == "evaluated"


def test_dimension_result_skipped():
    """DimensionResult with skipped status should have passed=None."""
    dim = DimensionResult(
        name="test_dim", score=0, passed=None, status="skipped",
        details="tool not installed",
    )
    assert dim.status == "skipped"
    assert dim.passed is None
    assert dim.score == 0


def test_dimension_result_blocked():
    """DimensionResult with blocked status."""
    dim = DimensionResult(
        name="test_dim", score=0, passed=False, status="blocked",
        details="crashed",
    )
    assert dim.status == "blocked"


# ---------------------------------------------------------------------------
# score_code_quality
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not shutil.which("ruff"),
    reason="ruff not installed",
)
def test_score_code_quality_on_clean_file():
    """A clean, well-formatted Python file should score > 80."""
    result = score_code_quality([str(FIXTURES / "clean_code.py")])
    assert result.score > 80, f"Expected >80 but got {result.score}: {result.details}"


def test_score_code_quality_no_ruff_fallback():
    """When ruff is not available, score_code_quality returns skipped status."""
    result = score_code_quality([str(FIXTURES / "clean_code.py")])
    if not shutil.which("ruff"):
        assert result.status == "skipped"
        assert result.passed is None
        assert result.score == 0
    else:
        # ruff is available, should get a real score
        assert result.status == "evaluated"
        assert result.score >= 50


@pytest.mark.skipif(
    not shutil.which("ruff"),
    reason="ruff not installed",
)
def test_score_code_quality_on_bad_file():
    """A file with many style/safety issues should score < 50."""
    result = score_code_quality([str(FIXTURES / "bad_code.py")])
    assert result.score < 50, f"Expected <50 but got {result.score}: {result.details}"


# ---------------------------------------------------------------------------
# score_complexity
# ---------------------------------------------------------------------------

def test_score_complexity_no_files():
    """No Python files should return score 100."""
    result = score_complexity([])
    assert result.score == 100
    assert result.passed is True


def test_score_complexity_skipped_without_radon():
    """Without radon installed, should return skipped."""
    if not shutil.which("radon"):
        result = score_complexity([str(FIXTURES / "clean_code.py")])
        assert result.status == "skipped"
        assert result.passed is None
    else:
        result = score_complexity([str(FIXTURES / "clean_code.py")])
        assert result.status == "evaluated"
        assert result.score >= 0


@pytest.mark.skipif(
    not shutil.which("radon"),
    reason="radon not installed",
)
def test_score_complexity_on_clean_file():
    """A clean file should have low complexity and high score."""
    result = score_complexity([str(FIXTURES / "clean_code.py")])
    assert result.score >= 50, f"Expected >=50 but got {result.score}: {result.details}"


# ---------------------------------------------------------------------------
# score_secrets
# ---------------------------------------------------------------------------

def test_score_secrets_no_leak():
    """A file with no secrets should score 100."""
    result = score_secrets([str(FIXTURES / "clean_code.py")])
    assert result.score == 100
    assert result.passed is True


def test_score_secrets_with_leak():
    """A file with hardcoded API keys should score 0 and be blocked."""
    result = score_secrets([str(FIXTURES / "secret_leak.py")])
    assert result.score == 0, f"Expected 0 but got {result.score}: {result.details}"
    assert result.passed is False


# ---------------------------------------------------------------------------
# compute_reward
# ---------------------------------------------------------------------------

def test_compute_reward_returns_report():
    """compute_reward should return a RewardReport with total_score and passed."""
    report = compute_reward(files=[str(FIXTURES / "clean_code.py")])
    assert isinstance(report, RewardReport)
    assert isinstance(report.total_score, float)
    assert isinstance(report.passed, bool)
    assert len(report.dimensions) == 8  # Now 8 dimensions


def test_compute_reward_blocks_on_secrets():
    """When secrets are found, the report should be blocked."""
    report = compute_reward(files=[str(FIXTURES / "secret_leak.py")])
    assert report.blocked_by == "secrets"
    assert report.passed is False


def test_compute_reward_has_completeness():
    """RewardReport should have a completeness field."""
    report = compute_reward(files=[str(FIXTURES / "clean_code.py")])
    assert hasattr(report, "completeness")
    assert report.completeness in ("complete", "incomplete", "minimal")


def test_compute_reward_skipped_renormalization():
    """When dimensions are skipped, total is re-normalized from evaluated ones only."""
    report = compute_reward(files=[str(FIXTURES / "clean_code.py")])
    # Total score should still be in valid range even with skipped dimensions
    assert 0 <= report.total_score <= 100
