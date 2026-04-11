# RL Environment Design for AI-Assisted Coding

> A chef without taste buds can follow recipes but never master cooking. AI without feedback loops can generate code but never master engineering.

## Why RL Framework?

Traditional AI coding operates in open-loop mode: the model generates code, and a human (eventually) discovers what went wrong. This is like training a basketball player who never sees the ball go through (or miss) the hoop.

**The RL framework provides closed-loop feedback:** every code generation is an action, every verification result is a reward signal, and the AI learns which patterns lead to successful outcomes.

### The Analogy

| Cooking | AI Coding (Current) | AI Coding (Harness) |
|---------|---------------------|---------------------|
| Chef tastes while cooking | No tasting — ship and pray | Automated verification at every step |
| Adjusts seasoning in real-time | Fix bugs after user reports | Fix before commit based on reward signals |
| Learns from each dish | Each session starts from zero | Accumulated reward patterns shape behavior |
| Kitchen has thermometers, timers | IDE has syntax highlighting | 6-layer verification + 7-dimension scoring |

---

## The Evolution: Four Paradigms

```
   Paradigm             Feedback Loop        First-Pass Success Rate
   ─────────────────    ──────────────────   ──────────────────────

   Vibe Coding          None                 ~30-40%
   "Just generate it"   Human finds bugs     AI codes blind
                        days later

         │
         ▼

   Plan Coding           Spec → Code          ~45-55%
   "Think first"         Still no runtime     Better intent alignment
                         feedback             but still blind execution

         │
         ▼

   Spec Coding           Spec → Code → Test   ~55-65%
   "Verify against       Manual test writing  Tests exist but AI
    spec"                                     doesn't learn from them

         │
         ▼

   Harness Engineering   Spec → Code → Auto   ~75-85% (target)
   "RL feedback loop"    Verify → Reward →    Every failure is a
                         Improve              learning signal
```

### What Changes at Each Level

| Aspect | Vibe | Plan | Spec | Harness |
|--------|------|------|------|---------|
| Requirements | Verbal/vague | Written plan | Formal spec + checklist | Self-contained brief with acceptance criteria |
| Testing | Manual, after the fact | Some manual tests | Spec-derived tests | 6-layer automated pipeline |
| Feedback speed | Days (user reports) | Hours (review) | Minutes (test run) | Seconds (pre-commit hooks) |
| Learning | None | None | None | Reward signals accumulate |
| Typical bugs caught before deploy | 10-20% | 30-40% | 50-60% | 80-90% (target) |

---

## MDP Modeling

The AI coding process maps naturally to a Markov Decision Process:

### State (S)

The state at any point is the combination of:

```python
State = {
    "task_brief": str,           # What needs to be built
    "spec_checklist": list[str], # Acceptance criteria
    "current_code": dict,        # File contents (diff from baseline)
    "verification_results": {    # Results from completed layers
        "l0_spec": Optional[Score],
        "l1_unit": Optional[Score],
        "l2_runtime": Optional[Score],
        "l3_static": Optional[Score],
        "l4_review": Optional[Score],
        "l5_acceptance": Optional[Score],
    },
    "iteration": int,            # How many revision cycles
    "context_remaining": int,    # Tokens left in context window
}
```

### Action (A)

At each state, the AI can take one of:

| Action | Description | When Appropriate |
|--------|-------------|------------------|
| `generate_code` | Write new code or modify existing | Initial implementation |
| `write_test` | Create unit/integration tests | After initial code, before L1 |
| `fix_from_feedback` | Revise code based on verification failure | After any layer fails |
| `request_clarification` | Ask for spec clarification | When L0 spec check is ambiguous |
| `refactor` | Restructure without changing behavior | When L4 review flags architecture issues |
| `submit` | Declare done, trigger full pipeline | When all known issues resolved |

### Reward (R)

Multi-dimensional reward signal from six verification layers:

```
R(s, a) = Σ(layer_weight[i] × layer_score[i])   for i in L0..L5

Where:
  layer_weight = [0.10, 0.30, 0.20, 0.15, 0.10, 0.15]
  layer_score  = normalized score [0.0, 1.0] from each layer
```

See [reward-functions.md](reward-functions.md) for the detailed 7-dimension scoring within each layer.

**Reward shaping:**
- Partial credit for partial success (not binary)
- Negative reward for regression (breaking something that worked)
- Bonus for first-pass success (no revision needed)
- Time penalty: score decays slightly with each iteration

### Transition (T)

```
T(s, a) → s'

After action:
  generate_code  → Run L0-L3 (fast layers)
  write_test     → Run L1 (unit tests)
  fix_from_feedback → Re-run failed layer + all above
  submit         → Run L0-L5 (full pipeline)
```

The key insight: **transitions are deterministic** — the verification results for a given code state are reproducible. This makes the environment much more learnable than typical RL settings.

### Termination Conditions

An episode ends when:

| Condition | Outcome | Reward |
|-----------|---------|--------|
| All L0-L5 pass, total score ≥ 70 | **Success** | Full reward |
| Max iterations reached (5) | **Timeout** | Partial reward based on best score |
| Context window exhausted | **Resource limit** | Partial reward + penalty |
| AI declares unsolvable | **Abort** | Small reward for honesty |
| Critical security issue detected | **Emergency stop** | Strong negative reward |

---

## Six-Layer Reward Signals

Each layer provides a specific reward signal at a specific time:

### L0: Spec Confirmation

```
Trigger:   After initial code generation
Verifies:  Every spec checklist item has corresponding code
Reward:    checked_items / total_items
Blocks:    "Built the wrong thing" bugs

Example feedback to AI:
  "3/5 spec items implemented. Missing: error handling for empty input,
   rate limiting on /api/generate endpoint."
```

### L1: Module Self-Test

```
Trigger:   After code generation or test writing
Verifies:  Each function produces correct output for given inputs
Reward:    (tests_passed / tests_total) × coverage_factor
Blocks:    Logic errors in individual functions

Example feedback to AI:
  "test_calculate_price FAILED: expected 29.99, got 29.989999999999998
   (floating point comparison without tolerance)"
```

### L2: Execution Verification

```
Trigger:   After L1 passes
Verifies:  Code runs without crashes, endpoints respond, DB connects
Reward:    successful_checks / total_checks
Blocks:    Import errors, connection failures, runtime crashes

Example feedback to AI:
  "ImportError: cannot import 'UserModel' from 'core.models'
   (renamed to 'User' in recent refactor)"
```

### L3: Static Analysis

```
Trigger:   After L2 passes (or in parallel with L1)
Verifies:  Type safety, security, secrets, code style
Reward:    1.0 - (weighted_issues / max_expected_issues)
Blocks:    Type errors, security vulnerabilities, leaked secrets

Example feedback to AI:
  "mypy: Argument 1 to 'process' has incompatible type 'str | None';
   expected 'str' [line 42, core/handler.py]"
```

### L4: Cross-Review

```
Trigger:   After L3 passes
Verifies:  Error handling, edge cases, architecture fit
Reward:    Reviewer confidence score (0.0-1.0)
Blocks:    Missed error handling, architectural violations

Example feedback to AI:
  "Network timeout not handled in external_api_call() at line 87.
   All external calls in this codebase use retry_with_backoff()."
```

### L5: Final Acceptance

```
Trigger:   On submit action
Verifies:  End-to-end user experience (XiaoCe + ZhuoLong)
Reward:    (xiaoCe_score + zhuoLong_score) / 2
Blocks:    UX failures, AI quality issues, security bypasses

Example feedback to AI:
  "ZhuoLong: User journey 'create new project' fails at step 3 —
   'Save' button unresponsive after filling all fields.
   Screenshot: evidence/zhuolong_create_project_step3.png"
```

---

## Predicted Impact

Based on analysis of 367 bugs categorized by root cause:

| Layer | Bug Category | Count | % of Total | Expected Catch Rate | Bugs Prevented |
|-------|-------------|-------|-----------|---------------------|----------------|
| L0 | Wrong feature / missing requirement | 37 | 10.1% | 70% | 26 |
| L1 | Logic errors in functions | 117 | 31.9% | 85% | 99 |
| L2 | Runtime / integration failures | 89 | 24.3% | 90% | 80 |
| L3 | Type / security / style issues | 68 | 18.5% | 95% | 65 |
| L4 | Missed edge cases / arch drift | 31 | 8.4% | 60% | 19 |
| L5 | UX / AI quality issues | 25 | 6.8% | 70% | 18 |
| **Total** | | **367** | **100%** | | **307 (83.6%)** |

**Projected first-pass success rate improvement:** from ~40% baseline to ~75-85%.

Breakdown:
- L0 alone: +5-8% (catches wrong-direction work early)
- L1-L2: +20-25% (largest impact — catches logic and runtime errors)
- L3: +8-12% (catches what linters catch, before humans review)
- L4: +3-5% (diminishing returns, but catches subtle issues)
- L5: +2-6% (final safety net, catches integration-level issues)

**Total estimated improvement: +38-56 percentage points.**

---

## Research Foundation

This design draws on six key research contributions:

### 1. CodePRM (ACL 2025)
**Process Reward Models for code generation.**
Key insight: rewarding intermediate steps (not just final output) dramatically improves code quality. Our six-layer cascade is a practical implementation — each layer is a process reward checkpoint.

### 2. FunPRM (2026)
**Function-level Process Reward Models.**
Extension of CodePRM to function-level granularity. Validates our L1 design: testing each function independently provides better reward signal than testing the whole program.

### 3. Static Analysis as Feedback Loop (arXiv:2508.14419)
**Using static analysis tools as automated reward signals.**
Demonstrates that feeding linter/type-checker output back to LLMs improves code quality by 15-25%. Our L3 layer implements this directly with ruff, mypy, bandit, and semgrep.

### 4. Ralph Loop Pattern
**Repeated Automated Loop with Progressive Hardening.**
The principle that verification should escalate in strictness. Our L0→L5 cascade embodies this: cheap/fast checks first, expensive/thorough checks last.

### 5. Self-Spec (ICLR 2026)
**LLMs generating their own specifications before coding.**
Shows that AI writing specs first and coding against them reduces errors by 30%. Our L0 spec confirmation layer automates verification of this spec-then-code pattern.

### 6. Multi-Agent Reflexion
**Multiple AI agents reflecting on each other's output.**
Validates our L4 cross-review layer: a second agent reviewing the first agent's code catches 15-20% of bugs that self-review misses. The key is fresh context — the reviewer hasn't seen the implementation journey.

---

## Implementation Priorities

### Phase 1: Foundation (Week 1-2)
- L3 static analysis pipeline (ruff + mypy + bandit + detect-secrets)
- Pre-commit hooks running L3
- Shared configs for all tools

### Phase 2: Core Loop (Week 3-4)
- L1 auto-generated unit tests
- L2 runtime smoke tests
- Reward scoring with 7 dimensions

### Phase 3: Intelligence (Week 5-6)
- L0 spec confirmation (requires spec-generation capability)
- L4 cross-review (requires multi-agent coordination)
- Feedback-to-improvement loop

### Phase 4: Acceptance (Week 7-8)
- L5 XiaoCe v2 integration
- L5 ZhuoLong integration
- Full pipeline orchestration
- Dashboard for reward signal visualization
