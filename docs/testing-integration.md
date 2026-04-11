# Testing Integration: Four-Layer Complementary System

> Four layers, zero overlap, full coverage.

## The Problem

In the current setup, XiaoCe (小测) and ZhuoLong (浊龙) both test UI:

- **XiaoCe** was designed as white-box tester but evolved to "click every button" on the frontend
- **ZhuoLong** does black-box user journeys which naturally involves clicking buttons
- **Result:** both agents spend time on UI testing, catching similar issues, while API/DB/permission testing is under-covered

```
 CURRENT STATE (overlapping)

 XiaoCe:   [──── API ────][── DB ──][────── UI ──────]
 ZhuoLong: [──── UI journey ────────][── AI quality ──]
                                 ▲
                           OVERLAP ZONE
                     Both clicking buttons,
                     both testing UI rendering
```

The overlap wastes compute and test time. Worse, the areas where they overlap (UI clicks) are not where most bugs hide — 31.9% of bugs are logic errors caught by unit tests, not UI interactions.

---

## The New Four-Layer Testing Pyramid

```
                          ╱╲
                         ╱  ╲
                        ╱    ╲
                       ╱ 浊龙  ╲
                      ╱ ZhuoLong╲         User journeys, UI, AI quality,
                     ╱  (black   ╲        adversarial probing
                    ╱    box)     ╲       ~2 hours, pre-release
                   ╱───────────────╲
                  ╱   小测 v2        ╲
                 ╱   XiaoCe v2       ╲    API audit, DB state, permissions,
                ╱   (white box)       ╲   error handling, performance
               ╱───────────────────────╲  ~30 min, post-integration
              ╱     Simulation Tests     ╲
             ╱     (scenario-based)       ╲  Mock AI, call core functions,
            ╱      ~5 min, pre-push        ╲ check DB + logs
           ╱────────────────────────────────╲
          ╱       Automated (CI pipeline)     ╲
         ╱   pytest + mypy + ruff + bandit +    ╲  Every commit
        ╱    semgrep + detect-secrets             ╲ ~1 min
       ╱───────────────────────────────────────────╲
```

### Key Principle: Each Layer Has Exclusive Territory

No two layers test the same thing. If XiaoCe checks an API endpoint's response code, ZhuoLong does not call that API. If ZhuoLong tests a button, XiaoCe does not click it.

---

## Layer Responsibilities: Clear Boundaries

### Layer 1: Automated (CI Pipeline)

| Aspect | Detail |
|--------|--------|
| **What it does** | Unit tests, type checking, linting, security scan, secret detection |
| **What it does NOT do** | Integration tests, UI tests, AI quality checks |
| **Tools** | pytest, mypy, ruff, bandit, semgrep, detect-secrets |
| **Trigger** | Every commit (pre-commit hook) and every push (CI) |
| **Runtime** | < 1 minute |
| **Catches** | Syntax errors, type mismatches, logic bugs in pure functions, security patterns, leaked secrets, style violations |
| **Output** | PASS/FAIL + error details + coverage report |

**What belongs here:**
```
[x] Does calculate_price(items) return the correct total?
[x] Does mypy accept the type annotations?
[x] Are there any hardcoded passwords?
[x] Does ruff pass without errors?
```

**What does NOT belong here:**
```
[ ] Does the checkout page render correctly?
[ ] Can a user complete the purchase flow?
[ ] Does the AI response make sense?
```

### Layer 2: Simulation Tests

| Aspect | Detail |
|--------|--------|
| **What it does** | Calls core functions with mock AI, checks DB state and logs |
| **What it does NOT do** | Render UI, use real AI models, test user experience |
| **Tools** | Python scripts, mock objects, `dev_` prefixed test users |
| **Trigger** | Pre-push (git hook) or manual |
| **Runtime** | < 5 minutes |
| **Catches** | Integration failures, DB state corruption, message flow errors, async issues |
| **Output** | Scenario results + DB state snapshots + log excerpts |

**What belongs here:**
```
[x] Does process_message() save the conversation to DB correctly?
[x] Does the routing logic send to the right agent?
[x] Does the memory system update after a user message?
[x] Does the quota system decrement correctly?
```

**What does NOT belong here:**
```
[ ] Does the chat interface display the message?
[ ] Is the AI response helpful?
[ ] Can the user see their quota balance?
```

**Test data isolation:** All simulation tests use `dev_simtest` user IDs. Tests clean up after themselves. Never touch real user data.

### Layer 3: XiaoCe v2 (White-Box Audit)

| Aspect | Detail |
|--------|--------|
| **What it does** | API response validation, DB state audit, permission boundary testing, error handling verification, performance checks |
| **What it does NOT do** | Click UI buttons, test visual rendering, evaluate AI quality, run user journeys |
| **Tools** | HTTP client (requests/httpx), DB queries, log analysis |
| **Trigger** | Post-integration or on-demand |
| **Runtime** | ~30 minutes |
| **Catches** | API contract violations, permission bypasses, missing error handling, slow queries, incorrect DB state |
| **Output** | Audit report with evidence (request/response pairs, DB snapshots, timing data) |

**XiaoCe v2 redefined role — Internal Auditor:**

```
BEFORE (v1): XiaoCe = "test everything including UI"
AFTER  (v2): XiaoCe = "audit what users can't see"

XiaoCe v2 focuses exclusively on:
├── API Correctness
│   ├── Every endpoint returns correct status codes
│   ├── Response schema matches spec
│   ├── Error responses have proper format
│   └── Rate limiting works correctly
├── Database Integrity
│   ├── Data is stored correctly after operations
│   ├── Relationships are maintained
│   ├── Cascading deletes work
│   └── Concurrent writes don't corrupt state
├── Permission Boundaries
│   ├── Free user can't access Pro features
│   ├── User A can't see User B's data
│   ├── Expired tokens are rejected
│   └── Admin endpoints require admin auth
├── Error Handling
│   ├── Invalid input returns 400, not 500
│   ├── Missing resources return 404
│   ├── Server errors are logged with context
│   └── Graceful degradation when dependencies fail
└── Performance
    ├── Key endpoints respond within SLA (< 500ms)
    ├── Database queries use indexes
    ├── No N+1 query patterns
    └── Memory usage stays within bounds
```

**What XiaoCe v2 does NOT do anymore:**
```
[ ] Click buttons on the frontend
[ ] Check if pages render correctly
[ ] Test CSS/layout/responsive design
[ ] Evaluate AI response quality
[ ] Walk through user journeys
```

### Layer 4: ZhuoLong (Black-Box QA)

| Aspect | Detail |
|--------|--------|
| **What it does** | User journey testing, UI interaction, AI response quality, adversarial probing, accessibility |
| **What it does NOT do** | Call APIs directly, query databases, check server logs, verify backend state |
| **Tools** | Playwright (web), screen-tap + automator (mobile), AI quality scorer |
| **Trigger** | Pre-release or on-demand |
| **Runtime** | ~2 hours |
| **Catches** | UX failures, broken user flows, AI quality issues, security from user perspective, accessibility violations |
| **Output** | Test report with screenshots, journey recordings, AI quality scores (5 dimensions) |

**ZhuoLong's exclusive territory:**
```
ZhuoLong tests from pure user perspective:
├── User Journeys
│   ├── Can a new user sign up and complete onboarding?
│   ├── Can a user create, edit, and delete a project?
│   ├── Does the payment flow work end-to-end?
│   └── Can a user recover from errors gracefully?
├── UI Quality
│   ├── Do all buttons respond to clicks?
│   ├── Are loading states shown during async operations?
│   ├── Does the layout work on different screen sizes?
│   └── Are error messages user-friendly?
├── AI Response Quality (5 dimensions)
│   ├── Relevance: Does the AI answer the question?
│   ├── Accuracy: Is the information correct?
│   ├── Helpfulness: Does it solve the user's problem?
│   ├── Safety: Does it refuse inappropriate requests?
│   └── Consistency: Is the persona maintained?
├── Adversarial Probing
│   ├── Prompt injection attempts
│   ├── Boundary testing (extreme inputs)
│   ├── Rate abuse (rapid-fire requests)
│   └── Permission escalation attempts from UI
└── Cross-Browser/Device
    ├── Chrome, Safari, Firefox
    ├── Mobile responsive
    └── Slow network simulation
```

**What ZhuoLong does NOT do:**
```
[ ] Call API endpoints directly (use the UI instead)
[ ] Query the database to verify state
[ ] Read server logs
[ ] Check code coverage
[ ] Verify internal data structures
```

**Verification method:** ZhuoLong verifies results by **performing another user action**, not by checking the database. Example: after creating a project, it navigates to the project list to see if it appears — it does not query `SELECT * FROM projects`.

---

## Complementarity Matrix

Which problems are caught by which layer?

| Problem Type | Automated | Simulation | XiaoCe v2 | ZhuoLong |
|-------------|:---------:|:----------:|:---------:|:--------:|
| **Logic error in pure function** | **P** | | | |
| **Type mismatch** | **P** | | | |
| **Leaked secret** | **P** | | | |
| **Style violation** | **P** | | | |
| **Security pattern (OWASP)** | **P** | | | |
| **DB state corruption after operation** | | **P** | S | |
| **Message routing error** | | **P** | | |
| **Async race condition** | | **P** | | |
| **Memory/quota not updating** | | **P** | S | |
| **API returns wrong status code** | | | **P** | |
| **Permission bypass (API level)** | | | **P** | |
| **Missing error handling** | | | **P** | |
| **Slow query / N+1** | | | **P** | |
| **Response schema mismatch** | | | **P** | |
| **Button doesn't work** | | | | **P** |
| **User can't complete a task** | | | | **P** |
| **AI response is wrong/unhelpful** | | | | **P** |
| **UI layout broken** | | | | **P** |
| **Error message confusing** | | | | **P** |
| **Prompt injection succeeds** | | | | **P** |
| **Cross-browser rendering** | | | | **P** |

**P** = Primary responsibility, **S** = Secondary (may catch incidentally but not the goal)

---

## What We Eliminate: Redundancy Reduction

### Before (Overlapping)

```
XiaoCe v1 time budget:
  API testing:    30%
  DB testing:     20%
  UI clicking:    40%  ← OVERLAP with ZhuoLong
  Permissions:    10%

ZhuoLong time budget:
  User journeys:  50%  ← 30% overlaps with XiaoCe UI clicking
  AI quality:     20%
  Security:       15%
  Accessibility:  15%
```

**Overlap: ~35% of total testing time spent on duplicate UI work.**

### After (Complementary)

```
XiaoCe v2 time budget:
  API audit:      35%
  DB integrity:   25%
  Permissions:    20%
  Error handling: 10%
  Performance:    10%
  UI clicking:     0%  ← ELIMINATED

ZhuoLong time budget:
  User journeys:  40%
  UI quality:     15%
  AI quality:     20%
  Adversarial:    15%
  Cross-device:   10%
  API calls:       0%  ← ELIMINATED
```

**Overlap: 0%. Each layer has exclusive territory.**

### Time Savings

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| XiaoCe runtime | ~45 min | ~30 min | -33% (no UI clicking) |
| ZhuoLong runtime | ~2.5 hrs | ~2 hrs | -20% (no API verification) |
| Issues found per hour | ~3 | ~5 | +67% (focused testing) |
| Duplicate findings | ~15% | ~0% | Eliminated |

---

## Trigger Matrix: When Each Layer Runs

```
Developer action          Automated   Simulation   XiaoCe v2   ZhuoLong
─────────────────────     ─────────   ──────────   ─────────   ────────
git commit                   [x]
git push                     [x]         [x]
PR created                   [x]         [x]          [x]
Pre-release                  [x]         [x]          [x]        [x]
Hotfix                       [x]         [x]
On-demand                    [x]         [x]          [x]        [x]
Production incident                                               [x]
```

### Why ZhuoLong Only Runs Pre-Release

ZhuoLong is expensive (2 hours, uses Playwright/screen-tap, may need real devices). Running it on every commit would waste resources. It runs when:

1. **Pre-release:** Full user journey validation before users see changes
2. **On-demand:** When a specific user flow is suspected broken
3. **Production incident:** When users report issues, ZhuoLong reproduces them

### Why Simulation Tests Run on Push (Not Commit)

Simulation tests take 5 minutes — too slow for every commit, but fast enough for every push. They catch integration issues that unit tests miss, without the overhead of full acceptance testing.

---

## Migration Path: Current State to New Model

### Phase 1: Separate Concerns (Week 1)

1. **Update XiaoCe agent definition:** Remove all UI testing instructions. Add API/DB/permission/error/performance audit instructions.
2. **Update ZhuoLong agent definition:** Remove API verification instructions. Add explicit "never call API directly" rule.
3. **No code changes needed** — this is purely instruction changes in agent `.md` files.

### Phase 2: Add Automation (Week 2-3)

1. **Convert simulation scripts to pytest:** Current `dev_simtest` scripts become proper pytest fixtures.
2. **Set up pre-commit hooks:** ruff + detect-secrets (fast, runs on commit).
3. **Set up pre-push hooks:** mypy + bandit + pytest (medium, runs on push).

### Phase 3: Integrate Pipeline (Week 4)

1. **Build harness runner:** Single entry point that orchestrates all four layers.
2. **Reward scoring:** Each layer contributes to the multi-dimensional score.
3. **Dashboard:** Visualization of scores over time, per project.

### Phase 4: Continuous Improvement (Ongoing)

1. **Track which layer catches which bugs:** Validate the complementarity matrix against real data.
2. **Adjust layer boundaries:** If XiaoCe catches UI bugs through API testing, that's fine. If it starts rendering pages, realign.
3. **Tune reward weights:** As bug distribution shifts (more projects, different types), adjust the seven-dimension weights.

---

## FAQ

**Q: What if a bug spans two layers?**
A: Most bugs have a primary detection layer. A button that doesn't work (ZhuoLong) might be caused by an API error (XiaoCe). ZhuoLong finds the symptom, XiaoCe finds the root cause. Both are valuable and complementary.

**Q: What if XiaoCe finds a UI issue through API testing?**
A: That's fine. XiaoCe might discover that an endpoint returns HTML with a missing `<button>` tag. The rule is XiaoCe doesn't *click* buttons, not that it can't inspect HTML responses.

**Q: Why not merge XiaoCe and ZhuoLong into one agent?**
A: Different tools, different perspectives, different execution environments. XiaoCe runs in-process with direct API/DB access. ZhuoLong runs in a browser/device simulator. Merging them would create a bloated agent that's hard to maintain and debug.

**Q: Can we run all four layers in parallel?**
A: Automated and Simulation can run in parallel (independent). XiaoCe should run after Automated passes (no point auditing APIs if unit tests fail). ZhuoLong should run after XiaoCe passes (no point testing UI if APIs are broken). The cascade saves time on failures.

**Q: How does this integrate with the RL reward system?**
A: Each layer feeds a score into the reward function. Automated contributes to functional correctness, type safety, security, secret safety, and code style dimensions. Simulation contributes to functional correctness and spec compliance. XiaoCe contributes to all dimensions from an audit perspective. ZhuoLong contributes to spec compliance (user can complete intended tasks) and security (adversarial probing).
