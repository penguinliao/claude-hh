# Performance Baseline - harness-engineering - 2026-04-06

Measured on: macOS Darwin 25.4.0, Python 3.9.6
Test file: single-function clean Python file (2 lines)

| Endpoint/Function | Method | Avg Response Time | Target | Notes |
|-------------------|--------|-------------------|--------|-------|
| check_quick | Python API | 0.117s | <5s | 2 dimensions (ruff + security) |
| check_standard | Python API | 0.468s | <30s | 5 dimensions (+mypy +functional +complexity) |
| check_full | Python API | 0.578s | <120s | 8 dimensions (all) |
| run_fix_loop (pass) | Python API | 0.117s | <15s | 1 iteration, clean file |
| run_fix_loop (escalate) | Python API | 0.463s | <15s | 3 iterations, unfixable issues |
| fix_loop_hook.sh (fast path) | Shell hook | 0.197s | <5s | ruff clean + bandit clean -> exit 0 |
| fix_loop_hook.sh (slow path) | Shell hook | 0.465s | <15s | ruff fail -> Python fix_and_report -> 3 iterations |
| mutation_test (16 mutations) | Python API | ~2.0s | <60s | 100% detection rate |
| compute_verdict | Python API | <1ms | <100ms | Pure computation, no I/O |
| generate_feedback | Python API | <1ms | <100ms | Pure parsing, no I/O |
