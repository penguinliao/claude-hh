# Harness Engineering

> Non-technical PM / developer tool: improve AI-generated code accuracy from ~50% to 80%+, first try.

## See It in Action

```
  BLOCKED — Secret Safety

  Code Quality     95/100  PASS  (5%)
  Security         82/100  PASS  (12%)
  Type Safety      45/100  FAIL  (14%)
  Secret Safety   BLOCKED        (5%)

  Fix these to pass:
  1. [BLOCKED] Secret Safety: 1 secret(s) detected — config.py:28
  2. [FAIL] Type Safety (45/100): 3 type error(s)

  mode: standard | 4200ms | iteration: 1
```

The harness checks your code across 8 dimensions, tells you exactly what's wrong and how to fix it. Auto-fixes what it can (formatting, imports), escalates what it can't.

## Quick Start (30 seconds)

```bash
# 1. Install tools
pip install ruff bandit mypy radon detect-secrets

# 2. Check your code
cd your-project
python3 -c "
from harness import fix_and_report
print(fix_and_report(['your_file.py']))
"
```

That's it. The fix loop will:
1. Run all checks
2. Auto-fix what ruff can fix (imports, formatting, style)
3. Re-check
4. Tell you exactly what's left to fix manually

## What It Checks (8 Dimensions)

Weights based on analysis of 367 bugs across 8 production projects.

| Dimension | Weight | Tool | Why This Weight |
|-----------|--------|------|-----------------|
| Functional | 33% | compile + tests | 117/367 bugs were logic errors |
| Spec Compliance | 18% | LLM + AST + keyword | 37 bugs were "built wrong thing" |
| Type Safety | 14% | mypy --strict | Type errors cause subtle runtime bugs |
| Security | 12% | ruff S + bandit | Low frequency but catastrophic impact |
| Complexity | 8% | radon CC + MI | Predicts future maintainability issues |
| Architecture | 5% | custom rules | Prevents codebase decay over time |
| Secret Safety | 5% | detect-secrets | Zero tolerance: any leak = blocked |
| Code Quality | 5% | ruff | Readability and consistency |

**Hard gates** (any trigger = BLOCKED, regardless of total score):
- Secret leak detected
- Functional score < 60 (code doesn't work)
- Security score < 50 (dangerous vulnerabilities)

## Auto-Fix Loop

The key feature: instead of just reporting problems, harness fixes what it can and gives AI-actionable feedback for the rest.

```
Edit code
    ↓
Quick check (ruff + security, <5s)
    ↓ fail?
Auto-fix (ruff --fix)
    ↓ still fail?
Structured feedback → AI fixes code
    ↓ still fail?
Escalate to human
```

```python
from harness import run_fix_loop

result = run_fix_loop(["my_module.py"])
if result.escalated:
    print(f"Need human help: {result.escalation_reason}")
else:
    print(f"Passed after {len(result.iterations)} iteration(s)")
    print(f"Auto-fixed {result.auto_fixes_applied} issue(s)")
```

## Three Modes

| Mode | Speed | When to Use | What It Runs |
|------|-------|-------------|--------------|
| `quick` | <5s | After each edit | ruff + security |
| `standard` | <30s | Before commit | + mypy + functional + complexity |
| `full` | 1-2min | Before deploy | All 8 dimensions |

## Mutation Testing (Self-Verification)

How do you know the harness itself works? Inject known bugs, check if it catches them.

```python
from harness.mutation_test import run_mutation_test, print_mutation_report

report = run_mutation_test(["your_file.py"])  # 16 bug patterns
print_mutation_report(report)
```

Output:
```
━━━ Harness Security Gate Self-Test ━━━

  ✅ Hardcoded password → caught
  ✅ SQL injection → caught
  ✅ Unsafe pickle.loads → caught
  ❌ CORS wildcard → missed (known limitation)

━━━ Detection rate: 15/16 = 94% ━━━
```

## Project Structure

```
harness-engineering/
├── harness/                 # Core engine
│   ├── reward.py            #   8-dimension scoring (internal)
│   ├── runner.py            #   Check orchestration (3 modes)
│   ├── verdict.py           #   PASS/FAIL/BLOCKED gate decision
│   ├── feedback.py          #   Structured fix suggestions
│   ├── autofix.py           #   Auto-fix loop engine
│   ├── spec_validator.py    #   Spec compliance (LLM/AST/keyword)
│   ├── exec_verifier.py     #   Execution verification
│   ├── mutation_test.py     #   Self-verification (16 patterns)
│   └── reporter.py          #   Terminal/Markdown/JSON output
├── hooks/                   # Claude Code integration
│   ├── pre_edit.py          #   Pipeline stage gate (pre-edit)
│   ├── post_edit.py         #   Quality check + autofix (post-edit)
│   ├── pre_commit.py        #   Pre-commit full gate (pre-bash)
│   ├── post_agent.py        #   Agent output tracking
│   ├── stop_check.py        #   Session end notification
│   └── install_v2.py        #   Smart installer (merges settings.json)
├── foundation/              # Reusable infrastructure
│   ├── shared-lib/          #   Common Python modules
│   └── project-template/    #   New project scaffold
├── pipeline/                # 7-stage workflow prompts
└── docs/                    # Architecture & research
```

## For Developers

- [Architecture deep-dive](docs/architecture.md)
- [Reward function design](docs/reward-functions.md)
- [Single-focus principle](docs/single-focus-principle.md)
- [RL environment design](docs/rl-environment.md)
- [Testing integration](docs/testing-integration.md)

## Research Basis

Built on 2026 state-of-the-art:
- **Harness Engineering** (Mitchell Hashimoto) — environment > model
- **Self-Spec** (ICLR 2026) — spec-first +2-5% pass rate
- **Ralph Loop** (2026 standard practice) — execution feedback reduces 40% hotfix
- **FunPRM** (2026) — process reward > outcome reward
- **Static Analysis as Feedback** (arXiv:2508.14419) — security issues 40% → 13%

## License

MIT
