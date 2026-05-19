`pytest tests/` fails on master with:

```
FAILED tests/test_optimization.py::TestOptimization::test_load_deactivation_zero_operating_timesteps
AssertionError: np.int64(5) != 4 : Load 0 should have exactly 4 active timesteps
```

This fails the test workflow on every PR.

### Source

Test introduced 2026-03-09 in commit `a6e3ffa` by @sokorn ("Deactivate binary variables for non-thermal loads with 0 operating timesteps to reduce MIP solve time"). At that commit, the test passes.

On current master (`9627fc6`) the test fails. The 4 → 5 drift means load 0 stays active one timestep longer than the test fixture defines.

### Test fixture (summary)

The test sets up two deferrable loads:

- Load 0: `operating_hours_of_each_deferrable_load = 1`, `set_deferrable_max_startups = 1` — expected to run for exactly 4 timesteps (1 hour ÷ 15-minute step = 4) with a single startup.
- Load 1: `operating_hours_of_each_deferrable_load = 0` — expected fully deactivated.

The 5th active timestep on load 0 violates either the `set_deferrable_max_startups = 1` cap or the `operating_hours = 1` duration.

### Suspect range

Between `a6e3ffa` (test passing) and `9627fc6` (test failing), commits that touched `optimization.py` and could plausibly affect deferrable-load timestep behavior:

| Commit | Date | Title | Suspicion |
|---|---|---|---|
| `dfb57ac` (#805) | 2026-04-21 | "Pin currently-running single-constant loads to start of horizon" | **Primary suspect** — directly modifies single-constant load timestep pinning, exact area the test exercises |
| `c0fb242` (#819) | 2026-04-28 | "Feature: heatpump group hotwater" | Adds `deferrable_load_groups`, may indirectly affect non-grouped semi-cont loads |
| `9cd195c` | recent | "build(deps): update skforecast" | Dependency bump, unlikely but possible if CVXPY/numpy transitive changed |
| `3398bd2` (#842) | 2026-05-13 | "fix: normalize None timesteps and use .get() for safe optim_conf reads" | Recent fix in same code area |

Definitive root cause needs `git bisect` between `a6e3ffa` and `9627fc6` running this one test on each candidate. PR #805 is the most plausible single-commit cause given the test's setup (single-startup, single-constant load).

### Reproducer

```bash
git checkout master  # current tip 9627fc6
uv sync --extra test
uv run pytest tests/test_optimization.py::TestOptimization::test_load_deactivation_zero_operating_timesteps -v
```

Returns the assertion failure above.

### Possible directions

Two paths:

**(a) The test's expected value is stale.** If PR #805's "pin to start of horizon" intentionally extends single-constant loads by one timestep for correctness, the test's `assertEqual(active_timesteps_0, 4, ...)` needs an update to 5 with a comment explaining the new semantics.

**(b) The implementation regressed.** Single-startup or operating-hours constraint is being violated under the new pinning logic, and the test catches a real bug.

Which one is it? Needs reading PR #805's intent against the test's assertions. I haven't made that judgment — that's maintainer / feature-owner territory (cc @carposio for #805, @sokorn for the test).

### Impact

Test workflow stays red on every PR. Reviewers have to mentally subtract this when reading PR CI status. After it's cleared, the test workflow becomes a reliable signal again.

I can bisect to pinpoint the exact regression commit if that would help.
