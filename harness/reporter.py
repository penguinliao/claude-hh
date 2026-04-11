"""
Report Generator

Generates human-readable and machine-readable reward reports
in Markdown, JSON, and colored terminal output formats.

Supports both RewardReport (from reward.py) and HarnessReport (from runner.py).
"""

from __future__ import annotations

import json
from dataclasses import asdict

from harness.reward import DimensionResult, RewardConfig, RewardReport
from harness.runner import HarnessReport
from harness.verdict import Verdict, compute_verdict


# ---------------------------------------------------------------------------
# Dimension display config
# ---------------------------------------------------------------------------

_DISPLAY_NAMES: dict[str, str] = {
    "functional": "Functional",
    "spec_compliance": "Spec Compliance",
    "type_safety": "Type Safety",
    "security": "Security",
    "complexity": "Complexity",
    "architecture": "Architecture",
    "secrets": "Secret Safety",
    "code_quality": "Code Quality",
}


def _get_weight_display() -> dict[str, str]:
    """Dynamically generate weight labels from RewardConfig."""
    cfg = RewardConfig()
    return {k: f"{int(v * 100)}%" for k, v in cfg.weights.items()}


def _progress_bar(score: int, width: int = 10) -> str:
    """Generate a text progress bar."""
    filled = round(score / 100 * width)
    empty = width - filled
    return "\u2588" * filled + "\u2591" * empty


def _status_icon(dim: DimensionResult) -> str:
    """Return status icon based on score and status."""
    if dim.status == "skipped":
        return "\u23ed"   # skip icon
    if dim.status == "blocked":
        return "\u26d4"  # no entry
    if dim.passed is None:
        return "\u23ed"
    if dim.score >= 80:
        return "\u2705"  # green check
    elif dim.score >= 50:
        return "\u26a0\ufe0f"   # warning
    else:
        return "\u274c"  # red X


def _display_name(dim: DimensionResult) -> str:
    """Get human-readable name for a dimension."""
    return _DISPLAY_NAMES.get(dim.name, dim.name.replace("_", " ").title())


def _weight_label(dim: DimensionResult) -> str:
    """Get weight label for a dimension."""
    weights = _get_weight_display()
    return weights.get(dim.name, "?%")


# ---------------------------------------------------------------------------
# ANSI terminal colors
# ---------------------------------------------------------------------------

class _C:
    """ANSI color codes."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    BG_YELLOW = "\033[43m"


def _score_color(score: int) -> str:
    """Return ANSI color based on score."""
    if score >= 80:
        return _C.GREEN
    elif score >= 50:
        return _C.YELLOW
    return _C.RED


# ---------------------------------------------------------------------------
# Helpers: extract dimensions + completeness from either report type
# ---------------------------------------------------------------------------

def _extract_report_info(report: RewardReport | HarnessReport) -> tuple[
    list[DimensionResult], float, bool, str | None, str
]:
    """Extract (dimensions, total_score, passed, blocked_by, completeness)."""
    if isinstance(report, HarnessReport):
        return (
            report.dimensions,
            report.total_score,
            report.passed,
            report.blocked_by,
            report.completeness,
        )
    return (
        report.dimensions,
        report.total_score,
        report.passed,
        report.blocked_by,
        getattr(report, "completeness", "complete"),
    )


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def to_markdown(report: RewardReport | HarnessReport) -> str:
    """Generate a Markdown report with table.

    Args:
        report: The reward/harness report to format.

    Returns:
        Markdown string.
    """
    dimensions, total_score, passed, blocked_by, completeness = _extract_report_info(report)

    lines: list[str] = []
    lines.append("# Harness Reward Report")
    lines.append("")

    # Status banner
    if blocked_by:
        lines.append(f"> **BLOCKED** by `{blocked_by}` -- hard gate failed")
    elif passed:
        lines.append(f"> **PASS** -- Total score: **{total_score}/100**")
    else:
        lines.append(f"> **FAIL** -- Total score: **{total_score}/100**")

    if completeness != "complete":
        lines.append(f"> Completeness: **{completeness}** (some dimensions skipped)")
    lines.append("")

    # Dimension table
    lines.append("| Dimension | Score | Status | Weight |")
    lines.append("|-----------|-------|--------|--------|")

    for dim in dimensions:
        icon = _status_icon(dim)
        name = _display_name(dim)
        weight = _weight_label(dim)

        if dim.status == "skipped":
            lines.append(f"| *{name}* | *skipped* | {icon} SKIP | {weight} |")
        elif dim.status == "blocked":
            lines.append(f"| {name} | {dim.score}/100 | {icon} BLOCKED | {weight} |")
        else:
            status = "PASS" if dim.passed else "FAIL"
            lines.append(f"| {name} | {dim.score}/100 | {icon} {status} | {weight} |")

    lines.append("")
    lines.append(f"**Total: {total_score}/100**")
    lines.append("")

    # Details section
    lines.append("## Details")
    lines.append("")
    for dim in dimensions:
        name = _display_name(dim)
        if dim.status == "skipped":
            lines.append(f"### {name} (skipped)")
        else:
            lines.append(f"### {name} ({dim.score}/100)")
        lines.append("")
        lines.append("```")
        lines.append(dim.details)
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def to_json(report: RewardReport | HarnessReport) -> str:
    """Generate JSON report.

    Args:
        report: The reward/harness report to format.

    Returns:
        JSON string.
    """
    dimensions, total_score, passed, blocked_by, completeness = _extract_report_info(report)

    # Compute verdict for HarnessReport
    verdict_data = None
    if isinstance(report, HarnessReport):
        v = compute_verdict(report)
        verdict_data = {
            "status": v.status,
            "reason": v.reason,
            "action_items": v.action_items,
        }

    data: dict = {
        "total_score": total_score,
        "passed": passed,
        "blocked_by": blocked_by,
        "completeness": completeness,
    }
    if verdict_data:
        data["verdict"] = verdict_data
    if isinstance(report, HarnessReport):
        data["mode"] = report.mode
        data["duration_ms"] = report.duration_ms
        data["iteration"] = report.iteration
    data["dimensions"] = [
        {
            "name": dim.name,
            "display_name": _display_name(dim),
            "score": dim.score,
            "passed": dim.passed,
            "status": dim.status,
            "weight": _weight_label(dim),
            "details": dim.details,
        }
        for dim in dimensions
    ]
    return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------

def to_terminal(report: RewardReport | HarnessReport) -> str:
    """Generate colored terminal output with verdict banner + dimension details.

    The verdict (PASS/FAIL/BLOCKED) is the first thing visible.
    Scores are kept as diagnostic detail on each dimension line.

    Args:
        report: The reward/harness report to format.

    Returns:
        ANSI-colored string for terminal display.
    """
    dimensions, total_score, passed, blocked_by, completeness = _extract_report_info(report)
    sep_line = "\u2501" * 48
    separator = f"{_C.DIM}{sep_line}{_C.RESET}"

    # Compute verdict for action items
    verdict: Verdict | None = None
    if isinstance(report, HarnessReport):
        verdict = compute_verdict(report)

    lines: list[str] = []
    lines.append("")

    # ---- Verdict banner (the most important thing) ----
    if blocked_by:
        display = _DISPLAY_NAMES.get(blocked_by, blocked_by)
        lines.append(f"  {_C.BG_RED}{_C.WHITE}{_C.BOLD}  BLOCKED \u2014 {display}  {_C.RESET}")
    elif passed:
        lines.append(f"  {_C.BG_GREEN}{_C.WHITE}{_C.BOLD}  PASS  {_C.RESET}")
    else:
        lines.append(f"  {_C.BG_RED}{_C.WHITE}{_C.BOLD}  FAIL \u2014 {total_score}/{RewardConfig().pass_threshold}  {_C.RESET}")

    lines.append("")

    # ---- Dimension lines ----
    max_name_len = max(len(_display_name(dim)) for dim in dimensions) if dimensions else 15

    for dim in dimensions:
        name = _display_name(dim).ljust(max_name_len)
        weight = _weight_label(dim)

        if dim.status == "skipped":
            lines.append(
                f"  {_C.GRAY}\u23ed {name}  skipped  ({weight}){_C.RESET}"
            )
        elif dim.status == "blocked":
            lines.append(
                f"  {_C.RED}\u2298 {name}  BLOCKED        ({weight}){_C.RESET}"
            )
        elif dim.passed is False:
            color = _score_color(dim.score)
            lines.append(
                f"  {_C.RED}\u2717 {name}{_C.RESET}  "
                f"{color}{dim.score:>3}/100{_C.RESET}  FAIL  "
                f"{_C.DIM}({weight}){_C.RESET}"
            )
        else:
            color = _score_color(dim.score)
            lines.append(
                f"  {_C.GREEN}\u2713 {name}{_C.RESET}  "
                f"{color}{dim.score:>3}/100{_C.RESET}  PASS  "
                f"{_C.DIM}({weight}){_C.RESET}"
            )

    lines.append(separator)

    # ---- Action items (from verdict) ----
    if verdict and verdict.action_items:
        blocked_or_fail = [a for a in verdict.action_items if "[BLOCKED]" in a or "[FAIL]" in a]
        if blocked_or_fail:
            lines.append("")
            lines.append(f"  {_C.BOLD}Fix these to pass:{_C.RESET}")
            for i, item in enumerate(blocked_or_fail, 1):
                lines.append(f"  {_C.RED}{i}. {item}{_C.RESET}")

    # ---- Footer: meta info ----
    lines.append("")
    meta_parts = []
    if isinstance(report, HarnessReport):
        meta_parts.append(f"mode: {report.mode}")
        if report.duration_ms > 0:
            meta_parts.append(f"{report.duration_ms}ms")
        if report.iteration > 0:
            meta_parts.append(f"iteration: {report.iteration}")
    if completeness != "complete":
        meta_parts.append(f"completeness: {completeness}")
    if meta_parts:
        lines.append(f"  {_C.DIM}{' | '.join(meta_parts)}{_C.RESET}")

    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience printer
# ---------------------------------------------------------------------------

def print_report(report: RewardReport | HarnessReport, format: str = "terminal") -> None:
    """Print report to stdout.

    Args:
        report: The reward/harness report to print.
        format: Output format -- "terminal", "markdown", or "json".
    """
    if format == "markdown":
        print(to_markdown(report))
    elif format == "json":
        print(to_json(report))
    else:
        print(to_terminal(report))
