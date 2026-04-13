"""
Telemetry — append-only SQLite logger for all harness check events.

Design principles:
  1. NEVER block or crash the caller. All writes wrapped in try/except.
  2. NEVER raise exceptions. If DB is unwritable, silently drop the event.
  3. Append-only. No updates, no deletes (except via explicit CLI purge).

Usage:
  from harness.telemetry import log_check, report, CheckEvent
  log_check(CheckEvent(...))          # Fire-and-forget
  print(report(days=30))              # CLI report
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DB_DIR = Path.home() / ".harness"
_DB_PATH = _DB_DIR / "telemetry.db"

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS check_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    project TEXT,
    file_path TEXT,
    hook_type TEXT,
    mode TEXT,
    total_score REAL,
    passed INTEGER,
    blocked_by TEXT,
    dimensions_json TEXT,
    duration_ms INTEGER,
    iteration INTEGER DEFAULT 0,
    pipeline_stage INTEGER,
    error TEXT
)
"""


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class CheckEvent:
    """A single harness check event to log."""

    project: str = ""
    file_path: str = ""
    hook_type: str = ""          # post_edit | pre_commit | pipeline_gate | manual
    mode: str = ""               # quick | standard | full
    total_score: float = 0.0
    passed: bool = False
    blocked_by: str | None = None
    dimensions: dict = field(default_factory=dict)  # {name: score}
    duration_ms: int = 0
    iteration: int = 0
    pipeline_stage: int | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def _ensure_db() -> sqlite3.Connection:
    """Create DB directory and table if needed. Returns connection."""
    _DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), timeout=2)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_CREATE_TABLE)
    return conn


def log_check(event: CheckEvent) -> None:
    """Log a check event. Never raises, never blocks for long."""
    conn = None
    try:
        conn = _ensure_db()
        conn.execute(
            """INSERT INTO check_events
               (timestamp, project, file_path, hook_type, mode, total_score,
                passed, blocked_by, dimensions_json, duration_ms, iteration,
                pipeline_stage, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(),
                event.project,
                event.file_path,
                event.hook_type,
                event.mode,
                event.total_score,
                1 if event.passed else 0,
                event.blocked_by,
                json.dumps(event.dimensions, ensure_ascii=False),
                event.duration_ms,
                event.iteration,
                event.pipeline_stage,
                event.error,
            ),
        )
        conn.commit()
    except Exception:
        pass  # Telemetry loss is acceptable; hook crash is not.
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def report(days: int = 30, project: str | None = None) -> str:
    """Generate a human-readable telemetry report.

    Returns formatted text. Never raises.
    """
    conn = None
    try:
        conn = _ensure_db()
        conn.row_factory = sqlite3.Row
        since = (datetime.now() - timedelta(days=days)).isoformat()

        where = "WHERE timestamp > ?"
        params: list = [since]
        if project:
            where += " AND project = ?"
            params.append(project)

        # Build parameterized WHERE conditions
        conditions = ["timestamp > ?"]
        if project:
            conditions.append("project = ?")
        where_clause = "WHERE " + " AND ".join(conditions)

        # Total events and pass rate
        row = conn.execute(
            "SELECT COUNT(*) as total, SUM(passed) as passed FROM check_events " + where_clause,
            params,
        ).fetchone()
        total = row["total"] or 0
        passed = row["passed"] or 0

        if total == 0:
            return f"No check events in the last {days} days."

        pass_rate = passed / total * 100

        # Average score and iterations
        row2 = conn.execute(
            "SELECT AVG(total_score) as avg_score, AVG(iteration) as avg_iter FROM check_events " + where_clause,
            params,
        ).fetchone()
        avg_score = row2["avg_score"] or 0
        avg_iter = row2["avg_iter"] or 0

        # Most common blocked_by
        blocked_rows = conn.execute(
            "SELECT blocked_by, COUNT(*) as cnt FROM check_events "
            + where_clause + " AND blocked_by IS NOT NULL GROUP BY blocked_by ORDER BY cnt DESC LIMIT 5",
            params,
        ).fetchall()

        # Per-project breakdown
        project_rows = conn.execute(
            "SELECT project, COUNT(*) as total, SUM(passed) as passed FROM check_events "
            + where_clause + " GROUP BY project ORDER BY total DESC LIMIT 10",
            params,
        ).fetchall()

        # Most failed dimensions (parse dimensions_json)
        dim_failures: dict[str, int] = {}
        dim_rows = conn.execute(
            "SELECT dimensions_json FROM check_events " + where_clause + " AND dimensions_json IS NOT NULL",
            params,
        ).fetchall()
        for dr in dim_rows:
            try:
                dims = json.loads(dr["dimensions_json"])
                for name, score in dims.items():
                    if isinstance(score, (int, float)) and score < 60:
                        dim_failures[name] = dim_failures.get(name, 0) + 1
            except (json.JSONDecodeError, TypeError):
                continue

        # Format report
        lines = [
            f"━━━ Harness Telemetry Report (last {days} days) ━━━",
            "",
            f"  Total checks:    {total}",
            f"  Pass rate:       {pass_rate:.1f}%  ({passed}/{total})",
            f"  Average score:   {avg_score:.1f}",
            f"  Average iterations: {avg_iter:.1f}",
            "",
        ]

        if blocked_rows:
            lines.append("  Most common blockers:")
            for br in blocked_rows:
                lines.append(f"    {br['blocked_by']}: {br['cnt']} times")
            lines.append("")

        if dim_failures:
            sorted_dims = sorted(dim_failures.items(), key=lambda x: -x[1])
            lines.append("  Most failed dimensions (score < 60):")
            for name, count in sorted_dims[:5]:
                lines.append(f"    {name}: {count} failures")
            lines.append("")

        if project_rows:
            lines.append("  Per-project breakdown:")
            for pr in project_rows:
                p_total = pr["total"]
                p_passed = pr["passed"] or 0
                p_rate = p_passed / p_total * 100 if p_total else 0
                p_name = pr["project"] or "(unknown)"
                lines.append(f"    {p_name}: {p_rate:.0f}% pass ({p_passed}/{p_total})")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    except Exception as e:
        return f"Telemetry report error: {e}"
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def purge(days: int = 90) -> int:
    """Delete events older than N days. Returns count deleted. Never raises."""
    conn = None
    try:
        conn = _ensure_db()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = conn.execute(
            "DELETE FROM check_events WHERE timestamp < ?", (cutoff,)
        )
        count = cursor.rowcount
        conn.commit()
        return count
    except Exception:
        return 0
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    days = 30
    proj = None

    for arg in args:
        if arg.startswith("--days="):
            days = int(arg.split("=")[1])
        elif arg.startswith("--project="):
            proj = arg.split("=")[1]

    if args and args[0] == "purge":
        deleted = purge(days=days)
        print(f"Purged {deleted} events older than {days} days.")
    else:
        print(report(days=days, project=proj))
