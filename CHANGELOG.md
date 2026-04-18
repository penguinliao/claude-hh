# Changelog

All notable changes to Claude H-H (harness-engineering) are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
the project uses [Semantic Versioning](https://semver.org/).

## [0.3.2] — 2026-04-18

Batch patch release focused on one recurring anti-pattern: **defensive
mechanisms whose intent is correct but whose granularity was too coarse,
hurting the normal path**. v0.3.1 landed the first fix (cooldown only after
FAIL, not on linear progression); v0.3.2 ships five more of the same shape,
plus Chinese wording tuned for non-technical PMs. Every change is covered by
a new AC script (`.harness/test_ac_v032_batch.py`, 14 checks) and the
existing cooldown AC still passes.

Why "defense is right, granularity was wrong" matters: the project's north
star is letting a non-technical PM ship production-grade code safely.
Physical enforcement beats AI promises — but only when the enforcement fires
on real risk, not on every normal step. A 30s cooldown on every `advance`
turned a 5-minute route into 30 minutes with zero added safety.

### Fixed

- **TEST stage ran scripts serially with no live progress**
  (`harness/pipeline.py`)
  N test scripts × 120s timeout meant a 24-script project could block for
  ~48 minutes worst-case, showing a blank screen. Scripts are now executed
  via `ThreadPoolExecutor` with `as_completed`, and each completion prints
  `[harness] 🧪 [i/N] name ✅/❌` live. Concurrency is configurable via
  `HARNESS_TEST_WORKERS` (default **2**). The default is deliberately
  conservative — legacy tests that share `/tmp` markers keyed on the
  project's md5 can race when many subprocesses touch them at once. Two
  workers still delivers ~2× speedup. Projects whose tests are fully
  isolated can set `HARNESS_TEST_WORKERS=4` for a bigger win. A final
  **serial retry pass** reruns any script that failed under parallel
  load — if it passes on retry, harness reports it as a parallel race
  rather than a real failure, so flakiness from shared state doesn't
  block advance.
- **`pre_commit` hook ran `tsc --noEmit` and `check_standard` serially**
  (`hooks/pre_commit.py`)
  On TypeScript projects this was 30s + 30s = 60s per commit. The two checks
  are independent; they now run concurrently via a 2-worker pool and the
  commit gate halves in wall time. `tsc` hard-fail still blocks the commit
  with the same semantics as before.
- **`pre_edit` spec-scope path comparison was case-sensitive on
  macOS-APFS** (`hooks/pre_edit.py`)
  APFS is case-insensitive by default; a spec listing `Foo.py` while the
  file on disk is `foo.py` previously false-rejected every edit. The
  `norm` lambda now lowercases both sides. The match is still exact-path
  (no glob widening).
- **Advance-cooldown wording blamed the PM for "blind retry"**
  (`harness/pipeline.py`)
  The old reason — "advance冷却中（…防止盲目重试）" — used jargon the PM
  didn't recognize. Rewritten as "刚刚 advance 失败过（X 秒前），再等 Y 秒
  可重试。建议先 retreat 回 IMPLEMENT 修复代码，不要原地重试。" The PM
  now sees the next concrete action.
- **REVIEW-stage failure reason did not tell the PM where to look**
  (`harness/pipeline.py`)
  Previously showed "总分 42/100 (blocked by: security)" with no pointer
  to the generated review document. Now appends "📖 详细问题见
  .harness/review.md" and "下一步：retreat 回 IMPLEMENT 修复 → advance
  重审."
- **Pipeline completion was silent** (`harness/pipeline.py`)
  Final reason was the English literal "Pipeline complete!" — the PM still
  had to inspect `pipeline.json` to confirm it was safe to stop Claude.
  Rewritten to "🎉 Pipeline 全部阶段已通过！代码已审查、测试已通过。可以
  安全停止 Claude 或开始部署。"
- **CLI `advance` ignored the completion reason** (`harness/pipeline.py`)
  The CLI's advance command hard-coded `print("Pipeline complete!")` on
  completion, which meant hotfix11's celebratory reason was invisible to
  PMs using the CLI (only programmatic callers saw it via
  `AdvanceResult.reason`). Now prints `result.reason` so the new wording
  actually reaches stdout.

### Tests

- `.harness/test_ac_v032_batch.py` — 14 assertions covering all six fixes
  (parallel walltime + live-progress substring, `ThreadPoolExecutor`
  presence in `pre_commit`, `.lower()` in the pre_edit norm lambda,
  cooldown reason free of jargon and mentioning retreat, REVIEW reason
  pointing at `review.md`, completion reason carrying a celebratory
  marker). All pass.
- `.harness/test_ac_cooldown_fail_only.py` — updated to use a cooldown
  discriminator (`"冷却"` or `"失败过"` or `"再等"`) so it works against
  both pre- and post-v0.3.2 wording. Still 6/6 green.

### Why *not* (scope discipline)

Ideas that look similar but were deferred after the same "initial intent vs.
blast radius" lens:

- Unlocking `.harness/test_*.py` during IMPLEMENT — breaks cognitive
  isolation; existing `change_request.md` channel covers the legitimate case.
- Allowing `spec.md` edits in any stage — same, and the retreat path exists.
- Stretching pipeline expiry from 4 h to 8 h — a feature conversation, not
  a regression.
- Caching `spec_validator` AST scans — real performance win, but cache
  invalidation risk outweighs the benefit in a patch release.
- Narrowing `stop_check` deflection patterns — no user complaints, kept
  conservative.

## [0.3.1] — 2026-04-17

First dogfood-driven bugfix release. Every change in this version walked
through its own pipeline (SPEC → IMPLEMENT → REVIEW → TEST) and is covered
by at least one AC script under `.harness/test_*.py`.

### Fixed

- **Security hard gate bypass for non-Python files** (`harness/reward.py`)
  `score_secrets` was filtering inputs to `.py` only, so a `.env` file
  containing an AWS-style key passed the `secrets` hard gate with score 100.
  Now scans the full input regardless of extension.
- **`score_functional` silently accepting failed tests** (`harness/reward.py`)
  When all input files were `test_*.py` (total importable = 0), the function
  returned 100 without running `test_cmd`. A failing pytest run was masked as
  a perfect score. Now `test_cmd` is honoured in the `total == 0` branch.
- **`stop_check` infinite loop on legitimate waits** (`hooks/stop_check.py`)
  The pipeline-incomplete block fired on every stop, including when Claude
  was asking the user a question or waiting on a background agent. Added
  three escape valves:
  - A: trailing `?`/`？`, `Y/N`/`X/Y` (case-insensitive), or Chinese asking
    phrases.
  - B: short responses (<300 chars) matching waiting patterns in Chinese
    (等待/稍等/处理中/…) and English (processing, waiting for, …).
  - C: loop-breaker — same normalized response blocks ≥3 times → release.
- **`stop_check` dead code referencing removed patterns**
  An unreachable text-scanning block was shadowed by an earlier marker check.
  Removed the block and the `_DEPLOY_DONE_PATTERNS` list.
- **`post_agent` false "missing test scripts" block** (`hooks/post_agent.py`)
  `project_root = ctx.project_root or os.getcwd()` fell back to the calling
  shell's cwd, which frequently is not the harness project root. Added a
  four-tier resolver: `ctx.project_root` → `$HARNESS_PROJECT` → walk-up
  `.harness/` search → `os.getcwd()`.
- **Bandit deduplication count showed 0** (`harness/reward.py`)
  The formula `bandit_count + len(seen_locations) - issue_count` simplifies
  to 0. Now reports `X unique issue(s) (M deduplicated from N total)`.

### Added

- **Decision log for stop hook**
  `stop_check` writes one line to `<project>/.harness/hook.log` whenever a
  pipeline-incomplete check reaches a decision (block or bypass A/B/C),
  making hook behaviour auditable.
- **Brief-requirement gate on SPEC→IMPLEMENT advance** (`harness/pipeline.py`,
  `harness/spec_file.py`)
  The SPEC stage now parses `## 测试策略` in `spec.md` and blocks advance if
  `小测审计: 需要` or `浊龙验收: 需要` is declared without the matching
  `.harness/<role>_brief.md` file.
- **Marker lifecycle on pipeline start/reset** (`harness/pipeline.py`,
  `hooks/pre_commit.py`)
  `/tmp/harness_tested_*` and `/tmp/harness_deployed_*` markers are cleared
  when a new pipeline starts or an existing one is reset. Test markers are
  written by a PostToolUse Bash hook when a real test command exits 0.
- **Code-file-write detection in Bash** (`hooks/pre_commit.py`)
  Detects `>` / `tee` / `sed -i` / `cp` / `mv` targeting `.py`/`.ts`/`.tsx`/
  `.vue`/`.js`/`.jsx` outside `/tmp/` and blocks them, forcing all code
  changes through `Edit`/`Write` tools and the standard gate.
- **IMPLEMENT-stage advance reminder** (`hooks/post_edit.py`)
  After a successful edit in Stage 3, the hook appends a reminder that
  advancing now would likely skip the remainder of the Agent's work.

### Changed

- **`hooks/post_edit.py`** now runs `fail-closed` — a crashed hook aborts
  instead of silently passing.
- **`hooks/pre_commit.py`** normalizes `ssh`/`scp` command matching to
  accept absolute paths (e.g. `/usr/bin/ssh …`).
- **Documentation** (`CLAUDE.md`)
  TEST stage documented as four gates (G1–G4) instead of three; hook count
  corrected from 5 to 6.

### Dogfood note

These fixes were discovered and validated by running Claude H-H on itself.
The third hotfix (stop_check escape valves) was caught in the wild by an
unrelated project session and fixed within the next dogfood cycle.

### Housekeeping

- Added `.claude/`, `findings.md`, `progress.md`, `task_plan.md` to
  `.gitignore` — these are per-session artifacts, not source.
- Aligned `pyproject.toml` version (`0.1.0` → `0.3.1`) with the versions
  already referenced in the README and `CLAUDE.md`.

## [0.3.0]

First `Claude H-H` branded release (rebrand from `Claude Rails`). See git
log for the commit-level changelog prior to the introduction of this file.
