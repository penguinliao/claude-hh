"""
Health Check — validate all harness dependencies in one command.

Usage:
  python3 -m harness.health

Output:
  ✅ ruff 0.8.1         installed
  ✅ bandit 1.7.9       installed
  ⚠️ detect-secrets     not installed (fallback to regex)
  ✅ telemetry.db       writable
  Overall: HEALTHY (1 warning)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolStatus:
    """Status of a single dependency."""

    name: str
    installed: bool
    version: str = ""
    required: bool = True  # False = optional (fallback exists)
    note: str = ""


@dataclass
class HealthReport:
    """Overall harness health."""

    tools: list[ToolStatus] = field(default_factory=list)
    telemetry_writable: bool = False
    hooks_configured: int = 0
    hooks_expected: int = 4  # pre_edit, post_edit, pre_commit, stop_check
    overall: str = "unknown"  # healthy | degraded | broken

    def summary(self) -> str:
        """Human-readable health report."""
        lines = ["━━━ Harness Health Check ━━━", ""]

        warnings = 0
        errors = 0

        for t in self.tools:
            if t.installed:
                ver = f" {t.version}" if t.version else ""
                lines.append(f"  ✅ {t.name:<20}{ver}")
            elif t.required:
                errors += 1
                note = f" ({t.note})" if t.note else ""
                lines.append(f"  ❌ {t.name:<20}not installed{note}")
            else:
                warnings += 1
                note = f" ({t.note})" if t.note else ""
                lines.append(f"  ⚠️  {t.name:<20}not installed{note}")

        lines.append("")

        if self.telemetry_writable:
            lines.append("  ✅ telemetry.db       writable")
        else:
            warnings += 1
            lines.append("  ⚠️  telemetry.db       not writable")

        lines.append(f"  {'✅' if self.hooks_configured >= self.hooks_expected else '⚠️ '} hooks              {self.hooks_configured}/{self.hooks_expected} configured")
        if self.hooks_configured < self.hooks_expected:
            warnings += 1

        lines.append("")

        if errors > 0:
            self.overall = "broken"
            lines.append(f"  Overall: BROKEN ({errors} error(s), {warnings} warning(s))")
        elif warnings > 0:
            self.overall = "degraded"
            lines.append(f"  Overall: DEGRADED ({warnings} warning(s))")
        else:
            self.overall = "healthy"
            lines.append("  Overall: HEALTHY")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)


def _get_tool_version(name: str) -> str:
    """Try to get tool version string."""
    try:
        result = subprocess.run(
            [name, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        output = (result.stdout + result.stderr).strip()
        # Extract version number from first line
        first_line = output.splitlines()[0] if output else ""
        return first_line.split()[-1] if first_line else ""
    except Exception:
        return ""


def check_health() -> HealthReport:
    """Run full health check. Never raises."""
    from harness.hook_runner import expand_tool_path
    expand_tool_path()
    report = HealthReport()

    # Required tools
    for name in ["ruff", "bandit", "mypy"]:
        installed = shutil.which(name) is not None
        version = _get_tool_version(name) if installed else ""
        report.tools.append(ToolStatus(
            name=name, installed=installed, version=version, required=True,
        ))

    # Optional tools (have fallbacks)
    for name, note in [
        ("detect-secrets", "fallback to regex"),
        ("radon", "complexity checks skipped"),
    ]:
        installed = shutil.which(name) is not None
        version = _get_tool_version(name) if installed else ""
        report.tools.append(ToolStatus(
            name=name, installed=installed, version=version,
            required=False, note=note,
        ))

    # Telemetry DB
    try:
        db_dir = Path.home() / ".harness"
        db_dir.mkdir(parents=True, exist_ok=True)
        test_file = db_dir / ".health_check_test"
        test_file.write_text("ok")
        test_file.unlink()
        report.telemetry_writable = True
    except Exception:
        report.telemetry_writable = False

    # Hooks configuration
    try:
        settings_path = Path.home() / ".claude" / "settings.json"
        if settings_path.exists():
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
            hooks = settings.get("hooks", {})
            configured = 0
            for event_type in ["PreToolUse", "PostToolUse", "Stop"]:
                if event_type in hooks:
                    entries = hooks[event_type]
                    for entry in entries:
                        hook_list = entry.get("hooks", [])
                        for h in hook_list:
                            cmd = h.get("command", "")
                            if "harness" in cmd:
                                configured += 1
            report.hooks_configured = configured
    except Exception:
        report.hooks_configured = 0

    # Compute overall
    report.summary()  # Side effect: sets report.overall
    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    r = check_health()
    print(r.summary())
