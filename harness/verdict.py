"""
Verdict Layer — translates internal scores into PM-facing PASS/FAIL/BLOCKED decisions.

The scoring engine (reward.py) is the diagnostic layer.
The verdict is what non-technical users see: a clear gate decision + action items.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from harness.reward import DimensionResult, RewardConfig
from harness.runner import HarnessReport


@dataclass
class Verdict:
    """User-facing gate decision."""

    status: str  # "PASS" | "FAIL" | "BLOCKED"
    reason: str  # Human-readable explanation
    total_score: float  # Internal score (for debug/details)
    blocking_dimension: str | None  # Which dimension caused BLOCKED
    action_items: list[str] = field(default_factory=list)  # Prioritized fix list


# Display names for dimensions
_DIM_DISPLAY = {
    "functional": "Functional",
    "spec_compliance": "Spec Compliance",
    "type_safety": "Type Safety",
    "security": "Security",
    "complexity": "Complexity",
    "architecture": "Architecture",
    "secrets": "Secret Safety",
    "code_quality": "Code Quality",
}


def _extract_action_items(dimensions: list[DimensionResult], config: RewardConfig) -> list[str]:
    """Extract actionable fix items from failed dimensions, sorted by severity."""
    items: list[str] = []

    # BLOCKED items first (hard gate failures)
    for dim in dimensions:
        if dim.name in config.hard_gates and dim.status == "evaluated":
            if dim.score < config.hard_gates[dim.name]:
                display = _DIM_DISPLAY.get(dim.name, dim.name)
                # Extract first meaningful line from details
                first_detail = dim.details.split("\n")[0] if dim.details else ""
                items.append(f"[BLOCKED] {display}: {first_detail}")

    # FAIL items next (score < 50 or not passed)
    for dim in dimensions:
        if dim.status == "evaluated" and dim.passed is False:
            # Skip if already added as BLOCKED
            if any(f"[BLOCKED] {_DIM_DISPLAY.get(dim.name, dim.name)}" in item for item in items):
                continue
            display = _DIM_DISPLAY.get(dim.name, dim.name)
            first_detail = dim.details.split("\n")[0] if dim.details else ""
            items.append(f"[FAIL] {display} ({dim.score}/100): {first_detail}")

    # WARN items last (score 50-79, passed but weak)
    for dim in dimensions:
        if dim.status == "evaluated" and dim.passed is True and dim.score < 80:
            display = _DIM_DISPLAY.get(dim.name, dim.name)
            items.append(f"[WARN] {display} ({dim.score}/100): could be improved")

    return items


def compute_verdict(report: HarnessReport, config: RewardConfig | None = None) -> Verdict:
    """Compute a PM-facing verdict from a HarnessReport.

    Args:
        report: The harness check result.
        config: Reward configuration. Uses default if not provided.

    Returns:
        Verdict with status, reason, and prioritized action items.
    """
    if config is None:
        config = RewardConfig()

    action_items = _extract_action_items(report.dimensions, config)

    # BLOCKED: a hard gate was triggered
    if report.blocked_by:
        display = _DIM_DISPLAY.get(report.blocked_by, report.blocked_by)
        return Verdict(
            status="BLOCKED",
            reason=f"{display} hard gate triggered",
            total_score=report.total_score,
            blocking_dimension=report.blocked_by,
            action_items=action_items,
        )

    # FAIL: total score below threshold
    if not report.passed:
        return Verdict(
            status="FAIL",
            reason=f"Total score {report.total_score} < {config.pass_threshold} threshold",
            total_score=report.total_score,
            blocking_dimension=None,
            action_items=action_items,
        )

    # PASS
    return Verdict(
        status="PASS",
        reason="All checks passed",
        total_score=report.total_score,
        blocking_dimension=None,
        action_items=action_items,  # May still have WARN items
    )
