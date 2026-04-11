# Harness Engineering: Full-Lifecycle Architecture

> Give AI a proper engineering environment, and it will build better software.

## Design Philosophy

Harness Engineering rests on two pillars:

| Pillar | What It Is | Analogy |
|--------|-----------|---------|
| **Hard Infrastructure** | Environments, tools, templates, configs, hooks | The kitchen equipment a chef needs before cooking |
| **Soft Process** | RL-style verification loops with multi-dimensional rewards | The taste-test feedback loop that makes the dish great |

Neither pillar works alone. Infrastructure without verification is a well-equipped kitchen with no quality control. Verification without infrastructure is a critic judging food cooked on a campfire.

**Core thesis:** 367 bugs analyzed across real AI-coded projects reveal a single root cause — AI lacks automated feedback during development. It codes blind. Harness Engineering gives it eyes, ears, and a scorecard.

---

## Six-Layer Verification Architecture

Every AI-generated change passes through six verification layers before it reaches users. Each layer targets a specific failure mode.

```
┌─────────────────────────────────────────────────────────────────┐
│                    AI generates code change                      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  L0  SPEC CONFIRMATION                                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ "Is this what was asked for?"                             │  │
│  │ • Requirement checklist auto-generated from task brief    │  │
│  │ • Each checklist item verified against code diff          │  │
│  │ • Missing items → block + report gap                      │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Prevents: building the wrong thing (37 bugs / 10.1%)           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PASS
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  L1  MODULE SELF-TEST                                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ "Does each function do what it should?"                   │  │
│  │ • Auto-generated unit tests per changed function          │  │
│  │ • pytest execution with coverage gate (≥80% on diff)      │  │
│  │ • Edge cases from spec + type hints                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Prevents: single-function logic errors (117 bugs / 31.9%)     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PASS
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  L2  EXECUTION VERIFICATION                                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ "Does it run without crashing?"                           │  │
│  │ • Import check: all modules importable                    │  │
│  │ • Runtime smoke test: key endpoints return 200            │  │
│  │ • Integration: DB connects, APIs respond, queues work     │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Prevents: runtime crashes & integration failures (89 bugs)    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PASS
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  L3  STATIC ANALYSIS                                            │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ "Does it meet code quality standards?"                    │  │
│  │ • Type safety: mypy --strict on changed files             │  │
│  │ • Security: bandit + semgrep rules                        │  │
│  │ • Secrets: detect-secrets scan                            │  │
│  │ • Style: ruff check + ruff format --check                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Prevents: type errors, security holes, leaked keys (68 bugs)  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PASS
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  L4  CROSS-REVIEW                                               │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ "What did I miss?"                                        │  │
│  │ • Second AI agent reviews diff with fresh context         │  │
│  │ • Checks: error handling, edge cases, concurrency         │  │
│  │ • Architecture compliance: does it fit the codebase?      │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Prevents: blind spots & architectural drift (31 bugs)         │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PASS
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  L5  FINAL ACCEPTANCE                                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ "Is the user happy?"                                      │  │
│  │ • XiaoCe (小测): white-box audit — API, DB, permissions   │  │
│  │ • ZhuoLong (浊龙): black-box QA — user journeys, UI, AI  │  │
│  │ • Both generate evidence (screenshots, logs, scores)      │  │
│  └───────────────────────────────────────────────────────────┘  │
│  Prevents: UX failures & integration-level regressions (25)    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ PASS
                           ▼
                    ✅ Ready to deploy
```

### Cascade Principle

Layers execute in order. **Fail fast:** if L0 fails, L1-L5 never run. This saves compute and gives the AI the most actionable feedback first.

```
L0 fail → "You built the wrong thing. Re-read the spec."
L1 fail → "Function X returns wrong result for input Y."
L2 fail → "ImportError in module Z at line 42."
L3 fail → "Type error: expected str, got Optional[str]."
L4 fail → "Missing error handling for network timeout."
L5 fail → "User can't complete checkout flow."
```

---

## Hard Infrastructure Components

### 1. `shared-lib` — Reusable Modules

Common code extracted once, used across all projects:

| Module | Purpose | Prevents |
|--------|---------|----------|
| `memory/` | Natural language memory with index separation | Every project reinventing memory |
| `routing/` | Model router (cheap model for dirty work, strong for core) | Wrong model selection |
| `compression/` | Context compaction (3-level, 9-part summary) | Context window overflow |
| `auth/` | JWT rotation + permission checks | Security holes in auth |
| `testing/` | Test harness runners + report generators | Inconsistent test execution |

### 2. `project-template` — Standardized Scaffolding

```
project-name/
├── .claude/
│   ├── CLAUDE.md          # Project-specific instructions
│   ├── agents/            # Agent definitions (xiaoming, xiaoyi, etc.)
│   └── skills/            # Reusable skill definitions
├── core/
│   ├── __init__.py
│   ├── config.py          # Settings with validation
│   ├── db.py              # Database with CREATE IF NOT EXISTS
│   └── models.py          # Data models
├── api/
│   ├── routes.py
│   └── middleware.py
├── tests/
│   ├── conftest.py        # Shared fixtures
│   ├── test_unit/         # L1 tests
│   ├── test_integration/  # L2 tests
│   └── test_simulation/   # Scenario-based simulation tests
├── harness/
│   ├── l0_spec.py         # Spec confirmation runner
│   ├── l1_unit.py         # Unit test runner
│   ├── l2_runtime.py      # Execution verification
│   ├── l3_static.py       # Static analysis orchestrator
│   ├── l4_review.py       # Cross-review coordinator
│   └── l5_acceptance.py   # Final acceptance trigger
├── pyproject.toml
├── Makefile               # make verify, make deploy, make test
└── .pre-commit-config.yaml
```

### 3. `configs` — Shared Tool Configurations

Pre-tuned configurations for all static analysis tools:

- `ruff.toml` — Linting + formatting rules aligned with project conventions
- `mypy.ini` — Strict type checking with per-module overrides
- `bandit.yaml` — Security checks excluding known false positives
- `.semgrep/` — Custom rules for AI-specific patterns (prompt injection, JSON leakage)
- `.detect-secrets` — Baseline with project-specific allowlist
- `.pre-commit-config.yaml` — Git hooks that run L3 on every commit

### 4. `hooks` — Git & Deployment Hooks

```
pre-commit  →  L3 static analysis (fast, <10s)
pre-push    →  L1 unit tests + L2 smoke tests (<60s)
post-merge  →  Full L0-L4 verification
pre-deploy  →  L0-L5 complete pipeline + backup
post-deploy →  Health check + rollback trigger
```

---

## Full Lifecycle Coverage

Every phase of development has corresponding Harness components:

```
 REQUIREMENT    DESIGN       CODING       VERIFICATION    DEPLOYMENT
 ──────────    ──────       ──────       ────────────    ──────────

 ┌────────┐   ┌────────┐   ┌────────┐   ┌────────────┐  ┌──────────┐
 │ Brief  │──▶│ Spec   │──▶│ Code   │──▶│ L0-L5      │──▶│ Deploy   │
 │ Synth  │   │ Gen    │   │ + Test │   │ Pipeline   │  │ + Watch  │
 └────────┘   └────────┘   └────────┘   └────────────┘  └──────────┘

  Harness:     Harness:     Harness:     Harness:        Harness:
  • Self-      • Spec       • Template   • 6-layer       • Backup
    contained    template     scaffold     cascade       • Health
    brief      • Checklist  • shared-lib • Reward          check
  • Context      auto-gen   • Pre-commit   scoring      • Rollback
    injection  • Review       hooks      • Evidence        trigger
  • Cheap        gate                      capture      • Watchdog
    model                                                  cron
    screening
```

### Phase Details

**1. Requirement Phase**
- Brief synthesis: main agent compiles a self-contained brief for worker agents (they can't see conversation context)
- Cheap model screening: use Qwen/DeepSeek for classification, filtering, brief synthesis
- Degradation path: if brief synthesis fails, fall back to raw request

**2. Design Phase**
- Spec auto-generation: AI produces a checklist from the brief
- Architecture review: L4 cross-review agent checks design against codebase conventions
- Interface-first: multi-module collaboration starts with protocol definition

**3. Coding Phase**
- Template scaffolding: new files follow project-template structure
- shared-lib imports: no reinventing memory, routing, compression
- Pre-commit hooks: L3 runs on every save (fast feedback)

**4. Verification Phase**
- Six-layer cascade: L0 → L5 in sequence, fail-fast
- Multi-dimensional reward scoring: 7 dimensions, weighted by bug frequency data
- Evidence capture: screenshots, logs, scores — not just PASS/FAIL

**5. Deployment Phase**
- Backup before deploy (`.bak`)
- Health check after deploy
- Watchdog cron monitors uptime
- Rollback on failure: `kill + restart from backup`

---

## Testing Architecture: Four-Layer Pyramid

```
                    ╱╲
                   ╱  ╲
                  ╱ 浊龙 ╲          Black-box: user journeys, UI, AI quality
                 ╱  (L5b)  ╲        Trigger: pre-release / on-demand
                ╱────────────╲
               ╱    小测 v2    ╲      White-box audit: API, DB, permissions, perf
              ╱     (L5a)      ╲    Trigger: post-integration / on-demand
             ╱──────────────────╲
            ╱   Simulation Tests  ╲   Scenario-based: mock AI + check DB + logs
           ╱       (L1+L2)        ╲  Trigger: pre-push
          ╱────────────────────────╲
         ╱    Automated (L1+L2+L3)   ╲  Unit + integration + static analysis
        ╱         (every commit)       ╲ Trigger: pre-commit / pre-push
       ╱────────────────────────────────╲
```

### Layer Responsibilities

| Layer | What | Who/Tool | When | Catches |
|-------|------|----------|------|---------|
| **Automated** | Unit tests, import checks, type safety, linting, security scan | pytest, mypy, ruff, bandit, semgrep, detect-secrets | Every commit | 70% of bugs (logic, types, style, secrets) |
| **Simulation** | Scenario tests calling `process_message()` with mock AI | Python scripts, `dev_` prefixed test users | Pre-push | Integration failures, DB state issues |
| **XiaoCe v2** | API response codes, DB state, permission boundaries, error handling, performance | Automated + manual inspection | Post-integration | Backend correctness, authorization gaps |
| **ZhuoLong** | User journeys end-to-end, UI rendering, AI response quality, adversarial probing | Playwright / screen-tap + automator | Pre-release | UX failures, AI quality issues, security |

### Complementarity, Not Redundancy

Each layer has a clear "does" and "does not" boundary:

- **Automated** does: run fast, catch obvious errors. Does not: test user experience.
- **Simulation** does: verify business logic flows. Does not: render UI or test AI quality.
- **XiaoCe v2** does: audit internal correctness. Does not: click buttons or test UI layout.
- **ZhuoLong** does: test from user perspective. Does not: check database state or call APIs directly.

No two layers test the same thing. See [testing-integration.md](testing-integration.md) for the full complementarity matrix.

---

## Key Design Decisions

1. **Fail-fast cascade over parallel execution**: Early layers are cheap and fast. Running expensive L5 acceptance tests on code that fails L1 unit tests wastes time and obscures the root cause.

2. **Reward scoring over pass/fail**: A numerical score (0-100) across 7 dimensions gives AI richer gradient signal than binary PASS/FAIL. See [reward-functions.md](reward-functions.md).

3. **Evidence over assertions**: Every test layer produces artifacts (screenshots, logs, score breakdowns). "PASS" without evidence is not trusted.

4. **Degradation paths everywhere**: Brief synthesis fails → use raw request. AI review fails → skip L4, proceed with warning. Static analysis timeout → use cached results. No single tool failure blocks the entire pipeline.

5. **Natural language over structured config**: Agent instructions, quality criteria, and review guidelines are written in natural language. AI reads prose better than YAML.
