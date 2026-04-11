"""
Structured Feedback Generator

Transforms raw linter/checker output into structured, AI-actionable fix suggestions.
This bridges the gap between the scoring engine (which diagnoses) and the fix loop
(which needs to know exactly what to fix and how).

Key design: parsers use JSON output from tools (ruff --output-format=json, bandit -f json)
for reliability. Falls back to text parsing only when JSON is unavailable.
"""

from __future__ import annotations

import json as _json
import re
from dataclasses import dataclass, field

from harness.reward import DimensionResult, RewardConfig
from harness.runner import HarnessReport
from harness.verdict import Verdict, compute_verdict


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FixSuggestion:
    """A single actionable fix suggestion."""

    file: str
    line: int | None
    dimension: str           # Which dimension found this
    severity: str            # "critical" | "high" | "medium" | "low"
    problem: str             # Human-readable description
    fix_hint: str            # How to fix it
    auto_fixable: bool       # Can ruff/tools auto-fix this?
    tool_fix_cmd: str | None = None  # e.g., "ruff check --fix --select=E501 file.py"


@dataclass
class StructuredFeedback:
    """Complete structured feedback from a harness check."""

    verdict: Verdict
    suggestions: list[FixSuggestion]  # Sorted by severity
    auto_fixable_count: int = 0
    manual_fix_count: int = 0
    iteration: int = 0

    def __post_init__(self) -> None:
        self.auto_fixable_count = sum(1 for s in self.suggestions if s.auto_fixable)
        self.manual_fix_count = sum(1 for s in self.suggestions if not s.auto_fixable)


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

_SEVERITY_MAP: dict[str, str] = {
    "secrets": "critical",
    "security": "high",
    "functional": "high",
    "type_safety": "medium",
    "architecture": "medium",
    "complexity": "low",
    "code_quality": "low",
    "spec_compliance": "medium",
}

# Ruff rules that are auto-fixable
_RUFF_AUTO_FIXABLE = {
    "E", "W", "I", "F401", "UP", "COM", "Q",  # Most E/W/I rules, unused imports, etc.
}


# ---------------------------------------------------------------------------
# Parsers: extract FixSuggestions from dimension details
# ---------------------------------------------------------------------------

def _parse_code_quality(dim: DimensionResult) -> list[FixSuggestion]:
    """Parse ruff output into suggestions."""
    suggestions = []
    if not dim.details:
        return suggestions

    for line in dim.details.splitlines():
        # Format: "file.py:10:5: E501 Line too long"
        match = re.match(r"(.+?):(\d+):\d+:\s+([\w]+)\s+(.*)", line)
        if match:
            filepath, line_no, rule, message = match.groups()
            # Check if this rule is auto-fixable
            auto_fix = any(rule.startswith(prefix) for prefix in _RUFF_AUTO_FIXABLE)
            suggestions.append(FixSuggestion(
                file=filepath,
                line=int(line_no),
                dimension="code_quality",
                severity="low",
                problem=f"{rule}: {message}",
                fix_hint=f"Run: ruff check --fix --select={rule} {filepath}",
                auto_fixable=auto_fix,
                tool_fix_cmd=f"ruff check --fix --select={rule} {filepath}" if auto_fix else None,
            ))

    return suggestions


def _parse_security(dim: DimensionResult) -> list[FixSuggestion]:
    """Parse ruff S-rules + bandit output."""
    suggestions = []
    if not dim.details:
        return suggestions

    for line in dim.details.splitlines():
        # ruff format: "file.py:10:5: S608 SQL injection"
        match = re.match(r"(.+?):(\d+):\d+:\s+(S\d+)\s+(.*)", line)
        if match:
            filepath, line_no, rule, message = match.groups()
            suggestions.append(FixSuggestion(
                file=filepath,
                line=int(line_no),
                dimension="security",
                severity="high",
                problem=f"{rule}: {message}",
                fix_hint=_security_fix_hint(rule),
                auto_fixable=False,
            ))
            continue

        # bandit format: ">> Issue: [B608:hardcoded_sql_expressions]..."
        if "Issue:" in line:
            suggestions.append(FixSuggestion(
                file="(see bandit output)",
                line=None,
                dimension="security",
                severity="high",
                problem=line.strip(),
                fix_hint="Review and fix the security issue manually.",
                auto_fixable=False,
            ))

    return suggestions


def _security_fix_hint(rule: str) -> str:
    """Return fix hint based on ruff security rule."""
    hints = {
        "S101": "Replace assert with proper validation (assert is stripped in python -O).",
        "S105": "Move hardcoded password to environment variable.",
        "S106": "Move hardcoded password to environment variable.",
        "S107": "Move hardcoded password to environment variable.",
        "S301": "Replace pickle.loads with safe deserialization (json, msgpack).",
        "S307": "Remove eval() call. Parse data with json.loads or ast.literal_eval.",
        "S324": "Use hashlib.sha256 instead of insecure hash (md5/sha1).",
        "S501": "Set verify=True for HTTPS requests.",
        "S506": "Use yaml.safe_load() instead of yaml.load().",
        "S602": "Use subprocess.run with shell=False and list args.",
        "S603": "Validate subprocess input. Consider using shlex.split().",
        "S608": "Use parameterized queries instead of f-string SQL.",
    }
    return hints.get(rule, "Review and fix the security issue manually.")


def _parse_type_safety(dim: DimensionResult) -> list[FixSuggestion]:
    """Parse mypy output."""
    suggestions = []
    if not dim.details:
        return suggestions

    for line in dim.details.splitlines():
        # Format: "file.py:10: error: Incompatible types..."
        match = re.match(r"(.+?):(\d+):\s+error:\s+(.*)", line)
        if match:
            filepath, line_no, message = match.groups()
            suggestions.append(FixSuggestion(
                file=filepath,
                line=int(line_no),
                dimension="type_safety",
                severity="medium",
                problem=f"Type error: {message}",
                fix_hint="Add or fix type annotations to resolve the type mismatch.",
                auto_fixable=False,
            ))

    return suggestions


def _parse_secrets(dim: DimensionResult) -> list[FixSuggestion]:
    """Parse detect-secrets / regex output."""
    suggestions = []
    if not dim.details:
        return suggestions

    for line in dim.details.splitlines():
        # Format: "  file.py:28 - High Entropy String"
        match = re.match(r"\s+(.+?):(\d+)\s+-\s+(.*)", line)
        if match:
            filepath, line_no, secret_type = match.groups()
            suggestions.append(FixSuggestion(
                file=filepath,
                line=int(line_no),
                dimension="secrets",
                severity="critical",
                problem=f"Secret detected: {secret_type}",
                fix_hint="Move secret to environment variable. Remove from code and rotate the credential.",
                auto_fixable=False,
            ))

    return suggestions


def _parse_functional(dim: DimensionResult) -> list[FixSuggestion]:
    """Parse compile/test errors."""
    suggestions = []
    if not dim.details:
        return suggestions

    for line in dim.details.splitlines():
        if "SyntaxError" in line:
            match = re.match(r"SyntaxError in (.+?):\s+(.*)", line)
            if match:
                filepath, message = match.groups()
                suggestions.append(FixSuggestion(
                    file=filepath,
                    line=None,
                    dimension="functional",
                    severity="high",
                    problem=f"Syntax error: {message}",
                    fix_hint="Fix the syntax error — the file cannot be parsed.",
                    auto_fixable=False,
                ))
        elif "Test command failed" in line:
            suggestions.append(FixSuggestion(
                file="(test suite)",
                line=None,
                dimension="functional",
                severity="high",
                problem="Test suite failed.",
                fix_hint="Run the test command manually and fix failing tests.",
                auto_fixable=False,
            ))

    return suggestions


def _parse_generic(dim: DimensionResult) -> list[FixSuggestion]:
    """Generic parser for architecture/complexity/spec — extract file references."""
    suggestions = []
    if not dim.details:
        return suggestions

    severity = _SEVERITY_MAP.get(dim.name, "low")
    for line in dim.details.splitlines():
        match = re.match(r"(.+?):(\d+)\s+-\s+(.*)", line)
        if match:
            filepath, line_no, message = match.groups()
            suggestions.append(FixSuggestion(
                file=filepath,
                line=int(line_no),
                dimension=dim.name,
                severity=severity,
                problem=message,
                fix_hint="Review and fix the issue.",
                auto_fixable=False,
            ))

    return suggestions


# ---------------------------------------------------------------------------
# Main: generate structured feedback from a report
# ---------------------------------------------------------------------------

_PARSERS = {
    "code_quality": _parse_code_quality,
    "security": _parse_security,
    "type_safety": _parse_type_safety,
    "secrets": _parse_secrets,
    "functional": _parse_functional,
}

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def generate_feedback(
    report: HarnessReport,
    config: RewardConfig | None = None,
    iteration: int = 0,
) -> StructuredFeedback:
    """Generate structured, AI-actionable feedback from a harness report.

    Args:
        report: The harness check result.
        config: Reward configuration. Uses default if not provided.
        iteration: Which fix-loop iteration this is (0 = first).

    Returns:
        StructuredFeedback with verdict, sorted suggestions, and counts.
    """
    if config is None:
        config = RewardConfig()

    verdict = compute_verdict(report, config)

    # Parse each dimension's details into suggestions
    all_suggestions: list[FixSuggestion] = []
    for dim in report.dimensions:
        if dim.status == "skipped":
            continue
        parser = _PARSERS.get(dim.name, _parse_generic)
        all_suggestions.extend(parser(dim))

    # Sort: critical first, then high, medium, low
    all_suggestions.sort(key=lambda s: _SEVERITY_ORDER.get(s.severity, 99))

    return StructuredFeedback(
        verdict=verdict,
        suggestions=all_suggestions,
        iteration=iteration,
    )


def feedback_to_text(fb: StructuredFeedback) -> str:
    """Format structured feedback as plain text for Claude Code hook output.

    This format is designed to be injected into an AI's context window,
    giving it everything needed to fix the issues.
    """
    lines: list[str] = []
    lines.append(f"=== HARNESS CHECK: {fb.verdict.status} (iteration {fb.iteration}) ===")
    lines.append(f"Reason: {fb.verdict.reason}")
    lines.append(f"Score: {fb.verdict.total_score}")
    lines.append("")

    if fb.auto_fixable_count > 0:
        lines.append(f"Auto-fixable: {fb.auto_fixable_count} issue(s)")
        for s in fb.suggestions:
            if s.auto_fixable and s.tool_fix_cmd:
                lines.append(f"  $ {s.tool_fix_cmd}")
        lines.append("")

    if fb.manual_fix_count > 0:
        lines.append(f"Manual fixes needed: {fb.manual_fix_count}")
        for s in fb.suggestions:
            if not s.auto_fixable:
                loc = f"{s.file}:{s.line}" if s.line else s.file
                lines.append(f"  [{s.severity.upper()}] {loc} — {s.problem}")
                lines.append(f"    Fix: {s.fix_hint}")
        lines.append("")

    return "\n".join(lines)
