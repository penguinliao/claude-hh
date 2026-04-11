# Multi-Dimensional Reward Functions

> One number cannot capture code quality. Seven dimensions can.

## Overview

The reward system evaluates every AI-generated code change across seven dimensions. Each dimension has a weight derived from empirical bug data (367 bugs across real projects) and a dedicated toolchain for automated scoring.

---

## Seven-Dimension Weight System

| Dimension | Weight | Tool(s) | Why This Weight | Bugs Addressed |
|-----------|--------|---------|-----------------|----------------|
| **Functional Correctness** | 35% | pytest | Largest bug category by far (117/367) | Logic errors, wrong output, missing behavior |
| **Spec Compliance** | 20% | Custom checker | Second most common failure: built wrong thing | Missing features, misunderstood requirements |
| **Type Safety** | 15% | mypy --strict | Type errors cause subtle runtime bugs | None references, wrong types, missing returns |
| **Security** | 12% | bandit + semgrep | Low frequency but catastrophic impact | SQL injection, XSS, insecure defaults |
| **Architecture Compliance** | 8% | Custom rules + L4 review | Prevents long-term codebase degradation | Convention violations, circular imports |
| **Secret Safety** | 5% | detect-secrets | Zero tolerance — any leak is critical | API keys, passwords, tokens in code |
| **Code Style** | 5% | ruff | Lowest direct impact but affects readability | Formatting, naming, import order |

### Why Functional Correctness Gets 35%

From the 367-bug analysis:

```
  Bug Category                    Count    Percentage
  ─────────────────────────────   ─────    ──────────
  Logic / functional errors        117      31.9%     ← Largest category
  Runtime / integration             89      24.3%
  Type / safety                     68      18.5%
  Spec / requirement mismatch      37      10.1%
  Architecture / design             31       8.4%
  UX / AI quality                   25       6.8%
```

**117 out of 367 bugs (31.9%) are pure functional errors** — the code runs, but produces the wrong result. This is the single biggest opportunity for improvement, so it gets the highest weight.

---

## Dimension Scoring Details

### 1. Functional Correctness (35%)

**What it measures:** Does the code produce correct outputs for correct inputs?

| Score Range | Criteria |
|-------------|----------|
| 90-100 | All tests pass, coverage ≥ 80% on changed lines, edge cases covered |
| 70-89 | All tests pass, coverage ≥ 60%, some edge cases missing |
| 50-69 | Most tests pass, 1-2 failures on non-critical paths |
| 30-49 | Multiple test failures, core logic has errors |
| 0-29 | Majority of tests fail, fundamental logic is wrong |

**Scoring method:**
```python
def score_functional(test_results, coverage):
    pass_rate = test_results.passed / test_results.total
    cov_factor = min(coverage.diff_coverage / 80.0, 1.0)  # Cap at 80%
    edge_bonus = 0.1 if test_results.edge_cases_covered else 0.0

    raw = (pass_rate * 0.7) + (cov_factor * 0.2) + edge_bonus
    return min(raw * 100, 100)
```

### 2. Spec Compliance (20%)

**What it measures:** Does the code implement what was specified?

| Score Range | Criteria |
|-------------|----------|
| 90-100 | All checklist items verified in code, no extraneous additions |
| 70-89 | All critical items present, 1-2 minor items missing |
| 50-69 | Most items present, 1 critical item missing |
| 30-49 | Multiple critical items missing |
| 0-29 | Fundamental mismatch between spec and implementation |

**Scoring method:**
```python
def score_spec_compliance(spec_checklist, code_diff):
    verified = 0
    critical_missing = 0

    for item in spec_checklist:
        if item.verified_in_code(code_diff):
            verified += 1
        elif item.is_critical:
            critical_missing += 1

    completeness = verified / len(spec_checklist)
    critical_penalty = critical_missing * 0.2  # Each critical miss = -20%

    return max((completeness - critical_penalty) * 100, 0)
```

### 3. Type Safety (15%)

**What it measures:** Are types correct, complete, and consistent?

| Score Range | Criteria |
|-------------|----------|
| 90-100 | mypy --strict passes, all functions annotated, no `Any` escapes |
| 70-89 | mypy passes with minor issues, most functions annotated |
| 50-69 | Some type errors on non-critical paths |
| 30-49 | Multiple type errors, including on core functions |
| 0-29 | Pervasive type errors, no annotations |

**Tool:** `mypy --strict --no-error-summary`

**Scoring:**
```python
def score_type_safety(mypy_output, changed_files):
    errors = mypy_output.errors_in(changed_files)
    total_lines = sum(f.line_count for f in changed_files)

    error_density = len(errors) / max(total_lines, 1)
    annotation_coverage = mypy_output.annotation_rate(changed_files)

    # Density: 0 errors = 1.0, >5 per 100 lines = 0.0
    density_score = max(1.0 - (error_density * 20), 0.0)

    return (density_score * 0.7 + annotation_coverage * 0.3) * 100
```

### 4. Security (12%)

**What it measures:** Are there known vulnerability patterns?

| Score Range | Criteria |
|-------------|----------|
| 90-100 | No bandit/semgrep findings, security best practices followed |
| 70-89 | Low-severity findings only, all with justification |
| 50-69 | Medium-severity findings, no high/critical |
| 30-49 | High-severity findings present |
| 0-29 | Critical vulnerability detected |

**Tools:** `bandit -r -f json` + `semgrep --config=auto`

**Severity weighting:**
```python
SEVERITY_WEIGHTS = {
    "critical": 25,   # One critical = -25 points
    "high":     15,
    "medium":    8,
    "low":       3,
    "info":      1,
}

def score_security(bandit_results, semgrep_results):
    all_findings = bandit_results + semgrep_results
    total_penalty = sum(SEVERITY_WEIGHTS[f.severity] for f in all_findings)
    return max(100 - total_penalty, 0)
```

### 5. Architecture Compliance (8%)

**What it measures:** Does the code fit the codebase's conventions and structure?

| Score Range | Criteria |
|-------------|----------|
| 90-100 | Follows all project conventions, proper module boundaries |
| 70-89 | Minor convention deviations, no structural issues |
| 50-69 | Noticeable convention violations, but functional |
| 30-49 | Architectural violations (circular imports, wrong layer access) |
| 0-29 | Fundamental structural problems |

**Checked patterns:**
- Import direction: `api/` imports from `core/`, never reverse
- No circular imports (detected by import graph analysis)
- Database access only through `core/db.py`, not raw SQL in routes
- Config access through `core/config.py`, not `os.environ` directly
- Error handling follows project pattern (custom exceptions, not bare `except`)

### 6. Secret Safety (5%)

**What it measures:** Are there any secrets in the code?

This dimension is **binary with override**: any detected secret = score 0, no secrets = score 100.

**Tool:** `detect-secrets scan --baseline .secrets.baseline`

```python
def score_secret_safety(scan_results):
    new_secrets = scan_results.new_findings()
    if len(new_secrets) > 0:
        return 0   # Absolute zero — this is a gate, not a gradient
    return 100
```

### 7. Code Style (5%)

**What it measures:** Does the code follow formatting and naming conventions?

| Score Range | Criteria |
|-------------|----------|
| 90-100 | ruff check passes, ruff format matches, clean imports |
| 70-89 | Minor style issues (spacing, trailing whitespace) |
| 50-69 | Multiple style violations, inconsistent formatting |
| 30-49 | Significant style issues affecting readability |
| 0-29 | No adherence to project style |

**Tool:** `ruff check --output-format=json` + `ruff format --check`

---

## Gate Rules

Some conditions are absolute blockers, regardless of total score:

```
┌──────────────────────────────────────────────────────────┐
│                    HARD GATES (any = block)               │
│                                                          │
│  1. Functional Correctness < 60    → BLOCKED             │
│     "Core logic is broken"                               │
│                                                          │
│  2. Secret detected (any)          → BLOCKED             │
│     "Cannot ship secrets to repo"                        │
│                                                          │
│  3. Critical security finding      → BLOCKED             │
│     "Known exploit pattern found"                        │
│                                                          │
│  4. Import/syntax error            → BLOCKED             │
│     "Code doesn't parse"                                 │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                    SOFT GATE                              │
│                                                          │
│  5. Total weighted score < 70      → WARNING + REVIEW    │
│     "Below quality threshold, needs human review"        │
│                                                          │
│  6. Total weighted score ≥ 70      → PASS                │
│     "Ready for deployment"                               │
└──────────────────────────────────────────────────────────┘
```

**Gate evaluation order:** Hard gates first (fast), then soft gate (requires full scoring).

---

## Verification Cascade Pattern

Layers run in order of speed. If a fast check fails, slow checks never run.

```
Time ──────────────────────────────────────────────────▶

│ ruff     │ mypy      │ detect-   │ bandit/  │ pytest  │ L4      │
│ check    │ --strict  │ secrets   │ semgrep  │         │ review  │
│          │           │           │          │         │         │
│  ~2s     │  ~5s      │  ~3s      │  ~8s     │  ~30s   │  ~60s   │
│          │           │           │          │         │         │
│ Style    │ Types     │ Secrets   │ Security │ Logic   │ Design  │
│ (5%)     │ (15%)     │ (5%)      │ (12%)    │ (35%)   │ (8%)    │

  FAIL? ──→ STOP. Return feedback. Don't waste time on slower checks.
```

**Why this order:**
1. **ruff** (2s): Catches syntax errors and obvious style issues instantly
2. **mypy** (5s): Catches type errors that would cause test failures anyway
3. **detect-secrets** (3s): Hard gate — must run before any code reaches tests
4. **bandit/semgrep** (8s): Security issues that should block before functional testing
5. **pytest** (30s): Most expensive automated check, runs only on code that passes all static checks
6. **L4 review** (60s): AI-powered review, most expensive, runs only on code that passes all automated checks

---

## Combined Scoring Formula

```python
def calculate_total_score(dimensions: dict[str, float]) -> tuple[float, str]:
    """
    Calculate weighted total score and determine pass/fail.

    Args:
        dimensions: {dimension_name: score_0_to_100}

    Returns:
        (total_score, verdict)  where verdict is PASS/WARNING/BLOCKED
    """
    WEIGHTS = {
        "functional_correctness": 0.35,
        "spec_compliance":        0.20,
        "type_safety":            0.15,
        "security":               0.12,
        "architecture":           0.08,
        "secret_safety":          0.05,
        "code_style":             0.05,
    }

    # ── Hard gates ──
    if dimensions["functional_correctness"] < 60:
        return (dimensions["functional_correctness"], "BLOCKED:functional")

    if dimensions["secret_safety"] == 0:
        return (0, "BLOCKED:secret_leaked")

    if dimensions["security"] < 20:  # Critical finding
        return (dimensions["security"], "BLOCKED:critical_security")

    # ── Weighted total ──
    total = sum(
        WEIGHTS[dim] * dimensions[dim]
        for dim in WEIGHTS
    )

    # ── Soft gate ──
    if total < 70:
        return (total, "WARNING:below_threshold")

    return (total, "PASS")


# Example: a typical successful submission
score, verdict = calculate_total_score({
    "functional_correctness": 92,   # All tests pass, good coverage
    "spec_compliance":        85,   # One minor item missing
    "type_safety":            78,   # Some annotations missing
    "security":               95,   # No findings
    "architecture":           80,   # Follows conventions
    "secret_safety":         100,   # No secrets
    "code_style":             88,   # Minor style issues
})
# score = 88.15, verdict = "PASS"


# Example: a blocked submission
score, verdict = calculate_total_score({
    "functional_correctness": 45,   # Multiple test failures
    "spec_compliance":        70,
    "type_safety":            60,
    "security":               80,
    "architecture":           75,
    "secret_safety":         100,
    "code_style":             90,
})
# score = 45, verdict = "BLOCKED:functional"
# AI receives: "Functional correctness at 45% (threshold: 60%).
#               Fix failing tests before proceeding."
```

---

## Tool Configuration Reference

### ruff (Code Style)
```toml
# ruff.toml
target-version = "py311"
line-length = 100

[lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "SIM", "TCH"]
ignore = ["E501"]  # Line length handled by formatter

[format]
quote-style = "double"
indent-style = "space"
```

### mypy (Type Safety)
```ini
# mypy.ini
[mypy]
python_version = 3.11
strict = True
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True

[mypy-tests.*]
disallow_untyped_defs = False
```

### bandit (Security)
```yaml
# bandit.yaml
skips:
  - B101  # assert in test files is fine
  - B601  # shell=True flagged but sometimes needed
tests:
  - B102  # exec
  - B103  # set_bad_file_permissions
  - B104  # hardcoded_bind_all
  - B105  # hardcoded_password
  - B106  # hardcoded_password_funcarg
  - B108  # hardcoded_tmp_directory
  - B301  # pickle
  - B302  # marshal
  - B303  # md5/sha1
  - B324  # hashlib insecure
  - B501  # request_with_no_cert_validation
  - B502  # ssl_with_bad_version
  - B506  # yaml_load
  - B608  # hardcoded_sql_expressions
  - B609  # linux_commands_wildcard_injection
```

### semgrep (Security + Patterns)
```yaml
# .semgrep/ai-patterns.yaml
rules:
  - id: no-raw-sql-in-routes
    pattern: |
      db.execute($SQL)
    paths:
      include: ["api/"]
    message: "Use ORM queries in route handlers, not raw SQL"
    severity: WARNING

  - id: no-json-in-user-response
    pattern: |
      json.dumps($DATA)
    paths:
      include: ["api/"]
    message: "Use response models, don't dump raw JSON to users"
    severity: WARNING

  - id: no-bare-except
    pattern: |
      except:
          ...
    message: "Catch specific exceptions, not bare except"
    severity: ERROR
```

### detect-secrets (Secret Safety)
```json
{
  "version": "1.4.0",
  "plugins_used": [
    {"name": "ArtifactoryDetector"},
    {"name": "AWSKeyDetector"},
    {"name": "AzureStorageKeyDetector"},
    {"name": "BasicAuthDetector"},
    {"name": "CloudantDetector"},
    {"name": "DiscordBotTokenDetector"},
    {"name": "HexHighEntropyString", "limit": 3.0},
    {"name": "JwtTokenDetector"},
    {"name": "KeywordDetector"},
    {"name": "PrivateKeyDetector"},
    {"name": "SlackDetector"},
    {"name": "SoftlayerDetector"},
    {"name": "StripeDetector"},
    {"name": "TwilioKeyDetector"}
  ],
  "filters_used": [
    {"path": "detect_secrets.filters.allowlist_filter"},
    {"path": "detect_secrets.filters.common.is_baseline_file"},
    {"path": "detect_secrets.filters.common.is_test_file"}
  ]
}
```

---

## Research Basis

### RACE Four-Dimension Framework
The RACE framework (Readability, Architecture, Correctness, Efficiency) validates multi-dimensional code evaluation. Our seven dimensions extend RACE with security-specific dimensions justified by the AI coding context where secret leakage and vulnerability injection are elevated risks.

### CodeScene Code Health
CodeScene's research shows that maintaining code health scores ≥ 9.4/10 correlates with 2x fewer defects. Our architecture compliance dimension (8%) captures similar structural health metrics, focusing on the patterns most relevant to AI-generated code.

### Veracode Security Report
Veracode's State of Software Security report shows only 55% of applications pass OWASP security checks on first scan. AI-generated code has an even lower pass rate due to training data including insecure patterns. Our security (12%) and secret safety (5%) dimensions directly target this gap, with a hard gate ensuring zero tolerance for critical findings.
