#!/usr/bin/env python3
"""
Harness v2.0 Installer — generates settings.json hooks configuration.

Usage:
  python3 hooks/install_v2.py          # Show what would be installed
  python3 hooks/install_v2.py --apply  # Apply to settings.json
  python3 hooks/install_v2.py --verify # Run health check after install

What it does:
  1. Generates the hooks section for ~/.claude/settings.json
  2. Preserves all existing settings (permissions, model, plugins, etc.)
  3. Replaces bash hooks with Python hooks
  4. Adds new PreToolUse:Edit|Write pipeline gate
  5. Runs health check to verify dependencies
"""

import json
import os
import platform
import shlex
import sys
from datetime import datetime
from pathlib import Path

# Add harness to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


HARNESS_DIR = Path(__file__).resolve().parent.parent
HOOKS_DIR = HARNESS_DIR / "hooks"
SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
# C2: BACKUP_SUFFIX moved to apply_config() for accurate timestamp

# Marker to identify harness-managed hooks for smart merge (C4)
_HARNESS_HOOK_MARKER = str(HOOKS_DIR)


def _notification_command(message: str, title: str = "Claude Code", sound: str = "Glass") -> str:
    """C5: Platform-aware notification command."""
    if platform.system() == "Darwin":
        return f"osascript -e 'display notification \"{message}\" with title \"{title}\" sound name \"{sound}\"'"
    elif platform.system() == "Linux":
        return f'notify-send "{title}" "{message}" 2>/dev/null || true'
    else:
        # Windows or unknown — no-op, don't block
        return "echo >/dev/null"


def generate_hooks_config() -> dict:
    """Generate the complete hooks configuration for settings.json."""
    python = sys.executable or "python3"

    # C1: Use shlex.quote for safe path escaping
    def _cmd(hook_name: str) -> str:
        return f'{shlex.quote(python)} {shlex.quote(str(HOOKS_DIR / hook_name))}'

    return {
        "PreToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [{
                    "type": "command",
                    "command": _cmd("pre_edit.py"),
                    "timeout": 15,  # C8: was 5, too tight for Python startup
                }],
            },
            {
                "matcher": "Bash",
                "hooks": [{
                    "type": "command",
                    "command": _cmd("pre_commit.py"),
                    "timeout": 45,
                }],
            },
        ],
        "PostToolUse": [
            {
                "matcher": "Write|Edit",
                "hooks": [{
                    "type": "command",
                    "command": _cmd("post_edit.py"),
                    "timeout": 30,
                }],
            },
            {
                "matcher": "Agent",
                "hooks": [{
                    "type": "command",
                    "command": _cmd("post_agent.py"),
                    "timeout": 60,
                }],
            },
        ],
        "Stop": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": _notification_command("Claude 完成了，请查看结果", sound="Glass"),
                    },
                    {
                        "type": "command",
                        "command": _cmd("stop_check.py"),
                        "timeout": 10,
                    },
                ],
            },
        ],
        "Notification": [
            {
                "matcher": "",
                "hooks": [{
                    "type": "command",
                    "command": _notification_command("Claude 需要你的输入", sound="Ping"),
                }],
            },
        ],
    }


def preview() -> str:
    """Show what the hooks config would look like."""
    config = generate_hooks_config()
    return json.dumps({"hooks": config}, indent=2, ensure_ascii=False)


def _is_harness_hook(hook_entry: dict) -> bool:
    """C4: Check if a hook entry belongs to harness (by command path or notification pattern)."""
    cmd = hook_entry.get("command", "")
    if _HARNESS_HOOK_MARKER in cmd:
        return True
    # Also match harness-generated notification commands (osascript/notify-send with our messages)
    harness_notification_phrases = ["Claude 完成了", "Claude 需要你的输入"]
    for phrase in harness_notification_phrases:
        if phrase in cmd:
            return True
    return False


def _merge_hooks(existing_hooks: dict, new_hooks: dict) -> dict:
    """C4: Smart merge — replace harness hooks, preserve user custom hooks.

    For each event type (PreToolUse, PostToolUse, etc.):
      - For each matcher group in existing config:
        - Remove harness-managed hook entries
        - Keep user-custom hook entries
      - Merge in new harness hooks, combining into same matcher group if matcher matches
    """
    merged = {}

    for event_type, new_matcher_groups in new_hooks.items():
        existing_groups = existing_hooks.get(event_type, [])

        # Index existing groups by matcher for easy lookup
        existing_by_matcher: dict[str, list] = {}
        for group in existing_groups:
            matcher = group.get("matcher", "")
            if matcher not in existing_by_matcher:
                existing_by_matcher[matcher] = []
            # Keep only non-harness hooks from existing config
            user_hooks = [h for h in group.get("hooks", []) if not _is_harness_hook(h)]
            if user_hooks:
                existing_by_matcher[matcher].extend(user_hooks)

        # Build merged groups
        result_groups = []
        seen_matchers = set()

        for new_group in new_matcher_groups:
            matcher = new_group.get("matcher", "")
            seen_matchers.add(matcher)
            combined_hooks = list(new_group.get("hooks", []))
            # C4: If user had custom hooks on the same matcher, append them
            if matcher in existing_by_matcher:
                combined_hooks.extend(existing_by_matcher[matcher])
            result_groups.append({"matcher": matcher, "hooks": combined_hooks})

        # Preserve user-only matcher groups that harness doesn't touch
        for matcher, user_hooks in existing_by_matcher.items():
            if matcher not in seen_matchers and user_hooks:
                result_groups.append({"matcher": matcher, "hooks": user_hooks})

        merged[event_type] = result_groups

    # Preserve event types that harness doesn't define (e.g. user-added custom events)
    for event_type, groups in existing_hooks.items():
        if event_type not in merged:
            # Keep only non-harness hooks
            cleaned = []
            for group in groups:
                user_hooks = [h for h in group.get("hooks", []) if not _is_harness_hook(h)]
                if user_hooks:
                    cleaned.append({"matcher": group.get("matcher", ""), "hooks": user_hooks})
            if cleaned:
                merged[event_type] = cleaned

    return merged


def apply_config() -> tuple[bool, str]:
    """Apply hooks config to settings.json. Returns (success, message)."""
    # C3: Auto-create settings.json if it doesn't exist
    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text("{}\n", encoding="utf-8")
        print(f"Created new settings file: {SETTINGS_PATH}")

    try:
        settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return False, f"Cannot read settings: {e}"

    # C2: Generate backup suffix at call time, not import time
    backup_suffix = f".backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_path = SETTINGS_PATH.with_suffix(backup_suffix)
    try:
        backup_path.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        return False, f"Cannot create backup: {e}"

    # C4: Smart merge — preserve user custom hooks
    existing_hooks = settings.get("hooks", {})
    new_hooks = generate_hooks_config()
    settings["hooks"] = _merge_hooks(existing_hooks, new_hooks)

    # Write back
    try:
        SETTINGS_PATH.write_text(
            json.dumps(settings, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        return False, f"Cannot write settings: {e}"

    return True, f"Hooks updated. Backup saved to {backup_path.name}"


def verify() -> str:
    """Run health check and return summary."""
    try:
        from harness.health import check_health
    except ImportError:
        return "⚠️ harness.health 模块不可用，跳过健康检查。请确认 harness 包已正确安装。"
    try:
        report = check_health()
        return report.summary()
    except Exception as e:
        return f"⚠️ 健康检查出错: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    args = sys.argv[1:]

    if "--apply" in args:
        ok, msg = apply_config()
        print(msg)
        if ok:
            print()
            print(verify())
        sys.exit(0 if ok else 1)

    elif "--verify" in args:
        print(verify())

    else:
        print("Preview of hooks configuration:")
        print()
        print(preview())
        print()
        print("To apply: python3 hooks/install_v2.py --apply")
        print("To verify: python3 hooks/install_v2.py --verify")
