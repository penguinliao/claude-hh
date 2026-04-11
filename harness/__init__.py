"""
Harness — code quality verification engine for AI-generated code.

Core API:
  check(files, mode) -> HarnessReport     # Run checks
  compute_verdict(report) -> Verdict       # PM-facing gate decision
  generate_feedback(report) -> Feedback    # AI-actionable fix suggestions
  run_fix_loop(files) -> FixLoopResult     # Auto-fix loop

v2.0 additions:
  pipeline: start/advance/status/reset    # 7-stage pipeline state machine
  telemetry: log_check/report             # SQLite telemetry
  health: check_health                    # Dependency health check
"""

from harness.runner import check, check_quick, check_standard, check_full, HarnessReport
from harness.verdict import Verdict, compute_verdict
from harness.feedback import StructuredFeedback, generate_feedback
from harness.autofix import run_fix_loop, fix_and_report, FixLoopResult
from harness.pipeline import start as pipeline_start, advance as pipeline_advance
from harness.pipeline import get_state, is_code_write_allowed, status as pipeline_status
from harness.telemetry import log_check, report as telemetry_report, CheckEvent
from harness.health import check_health

__all__ = [
    # Core check
    "check",
    "check_quick",
    "check_standard",
    "check_full",
    "HarnessReport",
    # Verdict (PM-facing)
    "Verdict",
    "compute_verdict",
    # Feedback (AI-actionable)
    "StructuredFeedback",
    "generate_feedback",
    # Auto-fix loop
    "run_fix_loop",
    "fix_and_report",
    "FixLoopResult",
    # v2.0: Pipeline
    "pipeline_start",
    "pipeline_advance",
    "pipeline_status",
    "get_state",
    "is_code_write_allowed",
    # v2.0: Telemetry
    "log_check",
    "telemetry_report",
    "CheckEvent",
    # v2.0: Health
    "check_health",
]
