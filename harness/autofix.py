"""
Auto-Fix Loop Engine

The core feedback loop:
  detect -> auto-fix (ruff --fix) -> re-check -> structured feedback -> [AI/human fix] -> pass or escalate

Reference patterns:
  - pre-commit's --fix: tools fix what they can, report what they can't
  - trunk check: auto-remediation with escalation
  - ruff --fix: safe subset of auto-fixable rules

Design:
  Iteration 1: Run check. If pass -> done.
  Iteration 2: Auto-fix (ruff --fix for fixable issues) -> re-check. If pass -> done.
  Iteration 3+: Generate structured feedback for AI/human -> they fix -> re-check.
  After max_iterations: Escalate.
"""

from __future__ import annotations

import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Callable

from harness.feedback import StructuredFeedback, generate_feedback, feedback_to_text
from harness.reward import RewardConfig
from harness.runner import HarnessReport, check


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class AutoFixConfig:
    """Configuration for the auto-fix loop."""

    max_iterations: int = 3       # Max fix-check cycles before escalating
    auto_fix_tools: bool = True   # Run ruff --fix automatically
    mode: str = "standard"        # Harness check mode
    spec_path: str | None = None
    test_cmd: str | None = None


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class FixLoopResult:
    """Result of running the auto-fix loop."""

    final_report: HarnessReport
    final_feedback: StructuredFeedback
    iterations: list[HarnessReport] = field(default_factory=list)
    auto_fixes_applied: int = 0
    escalated: bool = False
    escalation_reason: str | None = None


# ---------------------------------------------------------------------------
# Auto-fix: run ruff --fix on files
# ---------------------------------------------------------------------------

def _run_ruff_fix(files: list[str]) -> int:
    """Run ruff --fix on files. Returns number of fixes applied.

    Only fixes safe, deterministic rules (style, imports, formatting).
    Does NOT fix security or logic issues -- those require human judgment.
    """
    if not shutil.which("ruff"):
        return 0

    py_files = [f for f in files if f.endswith(".py")]
    if not py_files:
        return 0

    try:
        # First, count fixable issues
        before = subprocess.run(
            ["ruff", "check", "--output-format=json", "--no-fix", *py_files],
            capture_output=True, text=True, timeout=30,
        )
        before_count = before.stdout.count('"code":')

        # Apply fixes
        subprocess.run(
            ["ruff", "check", "--fix", *py_files],
            capture_output=True, text=True, timeout=30,
        )

        # Count remaining issues
        after = subprocess.run(
            ["ruff", "check", "--output-format=json", "--no-fix", *py_files],
            capture_output=True, text=True, timeout=30,
        )
        after_count = after.stdout.count('"code":')

        return max(0, before_count - after_count)
    except (subprocess.TimeoutExpired, Exception):
        return 0


# ---------------------------------------------------------------------------
# Core loop
# ---------------------------------------------------------------------------

def run_fix_loop(
    files: list[str],
    config: AutoFixConfig | None = None,
    reward_config: RewardConfig | None = None,
    on_feedback: Callable[[StructuredFeedback], None] | None = None,
) -> FixLoopResult:
    """Run the auto-fix loop: check -> fix -> re-check -> escalate.

    Args:
        files: List of file paths to check and fix.
        config: Auto-fix configuration. Uses defaults if not provided.
        reward_config: Reward scoring configuration. Uses defaults if not provided.
        on_feedback: Callback invoked with structured feedback after each iteration.
            This is the integration point for Claude Code hooks -- the hook receives
            structured feedback and can inject it into the AI's context.

    Returns:
        FixLoopResult with final report, iteration history, and escalation status.
    """
    if config is None:
        config = AutoFixConfig()
    if reward_config is None:
        reward_config = RewardConfig()

    iterations: list[HarnessReport] = []
    auto_fixes_total = 0

    for i in range(config.max_iterations):
        # Run check
        report = check(
            files,
            mode=config.mode,
            spec_path=config.spec_path,
            test_cmd=config.test_cmd,
        )
        report.iteration = i + 1
        iterations.append(report)

        # Generate feedback
        feedback = generate_feedback(report, reward_config, iteration=i + 1)

        # Notify callback
        if on_feedback:
            on_feedback(feedback)

        # If passed, we're done
        if report.passed:
            return FixLoopResult(
                final_report=report,
                final_feedback=feedback,
                iterations=iterations,
                auto_fixes_applied=auto_fixes_total,
            )

        # Iteration 1 failed: try auto-fix if enabled
        if i == 0 and config.auto_fix_tools:
            fixes = _run_ruff_fix(files)
            auto_fixes_total += fixes
            if fixes > 0:
                # Re-check after auto-fix (this becomes iteration 2)
                continue

        # Later iterations: feedback has been sent, wait for external fix
        # In hook mode, the AI receives the feedback and fixes code before next iteration
        # In CLI mode, this function returns and the caller decides what to do

    # Exhausted iterations -- escalate
    final_feedback = generate_feedback(
        iterations[-1], reward_config, iteration=config.max_iterations
    )

    return FixLoopResult(
        final_report=iterations[-1],
        final_feedback=final_feedback,
        iterations=iterations,
        auto_fixes_applied=auto_fixes_total,
        escalated=True,
        escalation_reason=(
            f"Failed after {config.max_iterations} iterations. "
            f"Remaining issues require human review."
        ),
    )


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

def fix_and_report(files: list[str], mode: str = "standard") -> str:
    """Run the fix loop and return a human-readable summary.

    Convenience function for use in scripts and hooks.
    """
    config = AutoFixConfig(mode=mode)
    result = run_fix_loop(files, config)

    lines: list[str] = []

    if result.final_report.passed:
        lines.append(f"PASS (after {len(result.iterations)} iteration(s))")
        if result.auto_fixes_applied > 0:
            lines.append(f"  Auto-fixed {result.auto_fixes_applied} issue(s)")
    elif result.escalated:
        lines.append(f"ESCALATE: {result.escalation_reason}")
        lines.append("")
        lines.append(feedback_to_text(result.final_feedback))
    else:
        lines.append(f"FAIL (iteration {len(result.iterations)})")
        lines.append("")
        lines.append(feedback_to_text(result.final_feedback))

    return "\n".join(lines)
