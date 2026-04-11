"""
Harness Runner -- the single entry point for all checks.

Three modes:
  quick:    ruff + bandit (<5s, after each edit)
  standard: + mypy + execution verification + complexity (<30s, before commit)
  full:     + spec validation + all dimensions (1-2min, before deploy)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from harness.reward import (
    DimensionResult,
    RewardConfig,
    compute_completeness,
    compute_weighted_total,
    score_architecture,
    score_code_quality,
    score_complexity,
    score_functional,
    score_secrets,
    score_security,
    score_spec_compliance,
    score_type_safety,
)


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------

@dataclass
class HarnessReport:
    """Result of a harness check run."""

    mode: str
    dimensions: list[DimensionResult]
    total_score: float
    passed: bool
    blocked_by: str | None = None
    completeness: str = "complete"  # complete / incomplete / minimal
    skipped_dimensions: list[str] = field(default_factory=list)
    duration_ms: int = 0
    iteration: int = 0  # Which fix-loop iteration produced this report (0 = first run)


# ---------------------------------------------------------------------------
# Mode -> dimension mapping
# ---------------------------------------------------------------------------

_MODE_DIMENSIONS: dict[str, list[str]] = {
    "quick": ["code_quality", "security"],
    "standard": ["code_quality", "security", "type_safety", "functional", "complexity"],
    "full": [
        "code_quality", "security", "type_safety", "functional",
        "complexity", "spec_compliance", "architecture", "secrets",
    ],
}


def _run_dimension(
    name: str,
    files: list[str],
    spec_path: str | None = None,
    test_cmd: str | None = None,
) -> DimensionResult:
    """Run a single dimension by name."""
    runners = {
        "code_quality": lambda: score_code_quality(files),
        "security": lambda: score_security(files),
        "type_safety": lambda: score_type_safety(files),
        "functional": lambda: score_functional(files, test_cmd=test_cmd),
        "complexity": lambda: score_complexity(files),
        "spec_compliance": lambda: score_spec_compliance(files, spec_path=spec_path),
        "architecture": lambda: score_architecture(files),
        "secrets": lambda: score_secrets(files),
    }
    fn = runners.get(name)
    if fn is None:
        return DimensionResult(
            name=name, score=0, passed=None, status="skipped",
            details=f"Unknown dimension: {name}",
        )
    try:
        return fn()
    except Exception as e:
        return DimensionResult(
            name=name, score=0, passed=False, status="blocked",
            details=f"Dimension crashed: {e}",
        )


# ---------------------------------------------------------------------------
# Core check function
# ---------------------------------------------------------------------------

def check(
    files: list[str],
    mode: str = "standard",
    spec_path: str | None = None,
    test_cmd: str | None = None,
) -> HarnessReport:
    """Run checks in the specified mode and return a report.

    Args:
        files: List of file paths to check.
        mode: One of "quick", "standard", "full".
        spec_path: Path to spec.md (only used in full mode).
        test_cmd: Shell command to run tests (only used in standard/full).

    Returns:
        HarnessReport with all dimension results and aggregated score.
    """
    start = time.monotonic()

    if isinstance(files, str):
        raise TypeError("files must be a list[str], not str. Got: " + repr(files)[:100])
    if files is None:
        raise TypeError("files must be a list[str], not None")

    if mode not in _MODE_DIMENSIONS:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of: {', '.join(_MODE_DIMENSIONS.keys())}")
    dim_names = _MODE_DIMENSIONS[mode]
    config = RewardConfig()

    dimensions: list[DimensionResult] = []
    blocked_by: str | None = None

    for dim_name in dim_names:
        result = _run_dimension(dim_name, files, spec_path=spec_path, test_cmd=test_cmd)
        dimensions.append(result)

        # Short-circuit: blocked dimension stops execution
        if result.status == "blocked":
            blocked_by = result.name
            break

        # Hard gate check: all gates defined in RewardConfig.hard_gates
        if dim_name in config.hard_gates and result.status == "evaluated":
            if result.score < config.hard_gates[dim_name]:
                blocked_by = result.name
                break

    # Use shared helpers (same logic as compute_reward, no duplication)
    skipped_dimensions = [d.name for d in dimensions if d.status == "skipped"]
    total_score = compute_weighted_total(dimensions, config)
    completeness = compute_completeness(dimensions)
    passed = blocked_by is None and total_score >= config.pass_threshold

    duration_ms = int((time.monotonic() - start) * 1000)

    report = HarnessReport(
        mode=mode,
        dimensions=dimensions,
        total_score=total_score,
        passed=passed,
        blocked_by=blocked_by,
        completeness=completeness,
        skipped_dimensions=skipped_dimensions,
        duration_ms=duration_ms,
    )

    # Optional telemetry (never blocks, never fails)
    try:
        from harness.telemetry import log_check, CheckEvent
        dim_scores = {d.name: d.score for d in dimensions if d.status == "evaluated"}
        log_check(CheckEvent(
            hook_type="runner",
            mode=mode,
            total_score=total_score,
            passed=passed,
            blocked_by=blocked_by,
            dimensions=dim_scores,
            duration_ms=duration_ms,
        ))
    except Exception:
        pass

    return report


# ---------------------------------------------------------------------------
# Convenience shortcuts
# ---------------------------------------------------------------------------

def check_quick(files: list[str]) -> HarnessReport:
    """Quick mode: ruff + security only."""
    return check(files, mode="quick")


def check_standard(files: list[str], test_cmd: str | None = None) -> HarnessReport:
    """Standard mode: + mypy + functional + complexity."""
    return check(files, mode="standard", test_cmd=test_cmd)


def check_full(
    files: list[str],
    spec_path: str | None = None,
    test_cmd: str | None = None,
) -> HarnessReport:
    """Full mode: all dimensions."""
    return check(files, mode="full", spec_path=spec_path, test_cmd=test_cmd)
