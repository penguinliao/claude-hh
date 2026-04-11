"""
Hook Runner — unified entry point for all harness hooks.

Design principles:
  1. NEVER crash the Claude Code session. Any unhandled exception → exit 0 (pass).
  2. Parse hook input from multiple sources: stdin JSON, env vars, CLI args.
  3. Log every invocation to telemetry (fire-and-forget).
  4. Provide structured output for Claude Code (stdout text shown to AI on exit 2).

Usage in hook scripts:
  from harness.hook_runner import run_hook, parse_hook_input

  def handle(ctx: HookContext) -> HookResult:
      # Your logic here
      return HookResult(exit_code=0)

  if __name__ == "__main__":
      sys.exit(run_hook(handle))
"""

from __future__ import annotations

import io
import json
import os
import signal
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable


# ---------------------------------------------------------------------------
# Fail-open logging — write to .harness/hook.log so user can debug
# ---------------------------------------------------------------------------

def _log_failopen(hook_type: str, reason: str, detail: str = "") -> None:
    """Append fail-open event to .harness/hook.log. Never raises."""
    try:
        log_dir = Path.cwd() / ".harness"
        if not log_dir.is_dir():
            log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "hook.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {hook_type or 'unknown'} FAIL-OPEN: {reason}"
        if detail:
            line += f" | {detail}"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class HookContext:
    """Parsed context available to hook handlers."""

    file_path: str = ""
    tool_name: str = ""
    tool_input: dict = field(default_factory=dict)
    hook_event: str = ""       # PreToolUse | PostToolUse | Stop | Notification
    project_root: str = ""     # Best-effort guess at project root
    raw_stdin: str = ""        # Full stdin for custom parsing


@dataclass
class HookResult:
    """Result from a hook handler."""

    exit_code: int = 0         # 0 = pass, 2 = block with feedback
    message: str = ""          # Shown to AI when exit_code == 2


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------

def parse_hook_input() -> HookContext:
    """Parse hook context from stdin JSON + env vars + CLI args.

    Claude Code hooks receive JSON on stdin with fields like:
      {"tool_name": "Edit", "tool_input": {"file_path": "/path/to/file", ...}}

    Also checks:
      - $CLAUDE_FILE_PATH env var
      - sys.argv[1] as file path
      - tool_input.file_path, tool_input.command for Bash tools
    """
    ctx = HookContext()

    # Read stdin with signal-based timeout (avoid indefinite blocking)
    # Fix #1: SIGALRM only on Unix; Windows falls back to plain read
    def _stdin_timeout_handler(signum, frame):
        raise TimeoutError("stdin read timed out")

    _has_alarm = hasattr(signal, "SIGALRM")

    try:
        if not sys.stdin.isatty():
            if _has_alarm:
                old_handler = signal.signal(signal.SIGALRM, _stdin_timeout_handler)
                signal.alarm(3)  # 3 second timeout
                try:
                    ctx.raw_stdin = sys.stdin.read()
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            else:
                # Windows: no SIGALRM, rely on external timeout from Claude Code
                ctx.raw_stdin = sys.stdin.read()
    except TimeoutError:
        ctx.raw_stdin = ""
        _log_failopen("", "stdin read timed out (3s alarm)", "")
    except Exception:
        ctx.raw_stdin = ""

    # Parse stdin JSON
    # Fix #10: log JSON parse failures for debugging
    stdin_data = {}
    if ctx.raw_stdin.strip():
        try:
            stdin_data = json.loads(ctx.raw_stdin)
        except (json.JSONDecodeError, TypeError) as e:
            _log_failopen("", "stdin JSON parse failed", f"{type(e).__name__}: {e}")

    # Extract fields from stdin JSON
    ctx.tool_name = stdin_data.get("tool_name", "")
    ctx.tool_input = stdin_data.get("tool_input", {})
    ctx.hook_event = stdin_data.get("hook_event", "")

    # Extract file path (priority: tool_input > env > argv)
    file_path = ""

    # From tool_input (Edit/Write tools)
    if isinstance(ctx.tool_input, dict):
        file_path = ctx.tool_input.get("file_path", "")
        # For Bash tools, try to extract file from command
        if not file_path and "command" in ctx.tool_input:
            file_path = ""  # Bash commands don't have a single file

    # From env var (fallback)
    if not file_path:
        file_path = os.environ.get("CLAUDE_FILE_PATH", "")

    # From CLI args (fallback)
    if not file_path and len(sys.argv) > 1:
        file_path = sys.argv[1]

    ctx.file_path = file_path

    # Best-effort project root detection
    ctx.project_root = _find_project_root(file_path)

    return ctx


def _find_project_root(file_path: str) -> str:
    """Find project root. Priority: HARNESS_PROJECT env > .harness walk-up > other markers > cwd.

    v3.1: Two-pass scan to fix monorepo root detection.
    Pass 1 looks ONLY for .harness (the definitive pipeline marker).
    Pass 2 falls back to .git / pyproject.toml / CLAUDE.md.
    This prevents CLAUDE.md in a parent dir from shadowing .harness in a child dir.
    """
    # Priority 1: explicit env var (solves cross-tree projects like ~/.claude/skills/ + ~/Desktop/project/)
    env_root = os.environ.get("HARNESS_PROJECT", "").strip()
    if env_root and Path(env_root).is_dir():
        return env_root

    if not file_path:
        return os.getcwd()

    path = Path(file_path).resolve()

    # Priority 2: first pass — look ONLY for .harness (definitive pipeline marker)
    for parent in [path.parent, *path.parent.parents]:
        if (parent / ".harness").is_dir():
            return str(parent)
        if parent == parent.parent:
            break

    # Priority 3: second pass — fallback to other markers
    fallback_markers = {".git", "pyproject.toml", "CLAUDE.md", "package.json", "tsconfig.json"}
    for parent in [path.parent, *path.parent.parents]:
        for marker in fallback_markers:
            if (parent / marker).exists():
                return str(parent)
        if parent == parent.parent:
            break

    # Priority 4: cwd
    return str(path.parent) if path.exists() else os.getcwd()


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def expand_tool_path() -> None:
    """Add common Python bin directories to PATH for tool discovery.

    Public function — also used by harness.health.
    Safe to call multiple times (skips already-added dirs).
    """
    extra_dirs = [
        Path.home() / "Library" / "Python" / "3.9" / "bin",
        Path.home() / "Library" / "Python" / "3.10" / "bin",
        Path.home() / "Library" / "Python" / "3.11" / "bin",
        Path.home() / "Library" / "Python" / "3.12" / "bin",
        Path.home() / ".local" / "bin",
    ]
    current = os.environ.get("PATH", "")
    for d in extra_dirs:
        ds = str(d)
        if d.is_dir() and ds not in current:
            os.environ["PATH"] = ds + os.pathsep + current
            current = os.environ["PATH"]


def run_hook(
    handler: Callable[[HookContext], HookResult],
    hook_type: str = "",
    fail_closed: bool = False,
) -> int:
    """Run a hook handler with full crash protection.

    Args:
        handler: Function that takes HookContext, returns HookResult.
        hook_type: Label for telemetry (e.g., "post_edit", "pre_edit").
        fail_closed: If True, exceptions return exit 2 (block). Default False (fail-open, exit 0).

    Returns:
        Exit code (0 = pass, 2 = block). NEVER raises.

    Guarantees:
        - If handler raises ANY exception → exit 0 (pass, fail-open) or exit 2 (fail-closed)
        - If stdin parsing fails → exit 0 (pass)
        - Telemetry logging failure → silently ignored
    """
    expand_tool_path()

    try:
        ctx = parse_hook_input()
    except Exception as e:
        # A4: visible fail-open notice so user knows hook didn't execute
        msg = f"[harness] ⚠️ {hook_type} hook输入解析失败(fail-open): {type(e).__name__}"
        print(msg, file=sys.stdout)
        _log_failopen(hook_type, "parse_hook_input failed", str(e))
        return 0

    try:
        result = handler(ctx)
        # Fix #7: detect async handler returning coroutine instead of HookResult
        if hasattr(result, "__await__") or hasattr(result, "cr_frame"):
            msg = f"[harness] ⚠️ {hook_type} handler是async函数，hook不支持async(fail-open)"
            print(msg, file=sys.stdout)
            print(msg, file=sys.stderr)
            _log_failopen(hook_type, "async handler not supported", "handler returned coroutine")
            return 0
    except Exception as e:
        _log_failopen(hook_type, "handler crashed", f"{type(e).__name__}: {e}")
        _log_error(hook_type, ctx, e)
        if fail_closed:
            msg = f"[harness] ❌ {hook_type} 检查异常(fail-closed): {e}"
            print(msg, file=sys.stdout)
            print(msg, file=sys.stderr)
            return 2
        msg = f"[harness] ⚠️ {hook_type} hook异常(fail-open): {type(e).__name__}: {e}"
        print(msg, file=sys.stdout)
        print(msg, file=sys.stderr)
        return 0

    # Fix #8: normalize exit_code — Claude Code only recognizes 0 (pass) and 2 (block)
    exit_code = result.exit_code
    if exit_code not in (0, 2):
        _log_failopen(hook_type, f"invalid exit_code {exit_code}, normalized to 2", "")
        exit_code = 2  # Treat unexpected codes as block (safer than silent pass)

    # Output message: stdout for AI (exit 2 block feedback), stderr for user visibility
    if result.message:
        print(result.message, file=sys.stdout)
        print(result.message, file=sys.stderr)

    # Log to telemetry (fire-and-forget)
    _log_invocation(hook_type, ctx, result)

    return exit_code


def _log_invocation(hook_type: str, ctx: HookContext, result: HookResult) -> None:
    """Log successful hook invocation to telemetry. Never raises."""
    try:
        from harness.telemetry import log_check, CheckEvent
        log_check(CheckEvent(
            project=os.path.basename(ctx.project_root),
            file_path=ctx.file_path,
            hook_type=hook_type,
            passed=result.exit_code == 0,
            error=result.message if result.exit_code != 0 else None,
        ))
    except Exception:
        pass


def _log_error(hook_type: str, ctx: HookContext, error: Exception) -> None:
    """Log hook error to telemetry + stderr. Never raises."""
    try:
        # Log to telemetry
        from harness.telemetry import log_check, CheckEvent
        log_check(CheckEvent(
            project=os.path.basename(ctx.project_root),
            file_path=ctx.file_path,
            hook_type=hook_type,
            passed=True,  # We're passing through (fail-open)
            error=f"Hook crashed: {type(error).__name__}: {error}",
        ))
    except Exception:
        pass

    try:
        # Also log to stderr for immediate visibility
        print(f"[harness] {hook_type} hook error (fail-open): {error}", file=sys.stderr)
    except Exception:
        pass
