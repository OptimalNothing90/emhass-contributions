# #875 Disentanglement Report — "Odd behavior following v0.17.4/5"

Date: 2026-06-03
Repo: davidusb-geek/emhass
Verified against: upstream/master @ cba33af (v0.17.6 line), full git history + tags
Account: OptimalNothing90

## Scope

One GitHub thread (#875) hiding **five distinct defects** that share a single visible symptom: infeasible solve / odd plan / battery to -200% SOC / `KeyError` on publish. Every claim below is cited to a thread quote, a `file:line`, or a commit, and reproduced where possible.

## Reporters → which bug each actually has

| Reporter | Inverter | Fingerprint | Maps to |
|---|---|---|---|
| g1za (OP) | non-hybrid (`inverter_is_hybrid:false`, `ac_output_max:1000` explicit) | infeasible → relaxed infeasible → `KeyError 'P_Load'`; stateful (every reboot, 2nd run OK); feasible on 0.17.2 (cost 3.44) | Cause 4 + Finding 2 |
| tmszdmsk | hybrid | -247% SOC, "Optimal (Relaxed)", restart-fixes | Cause 3 → Finding 1 |
| ztega | hybrid | `KeyError 'P_Load'` + 0.17.4 SOC-violating "Optimal"; stateful, restart-fixes | Cause 3 / Finding 1 + Finding 2 |
| rdeknijf | hybrid | A/B-proved `inverter_ac_output_max` default flip | Cause 3 (root) |
| joshm74 | n/a | percent-vs-fraction SOC (10/90, soc 65) worked ≤0.17.1, broke after | Candidate B |

## The five defects

### Finding 1 — Relaxed-LP drops battery/inverter constraints on cached paths → FIXED in v0.17.6

Relaxed retry guarded constraint re-application on `inv_stress_conf`/`batt_stress_conf`, which are `None` on any cached-problem path (`self.prob is not None`). Post-first-call retries ran with no SOC bounds / charge-discharge direction / DC-bus balance → battery to -247%, mislabeled "Optimal (Relaxed)".

- Fix: PR #885 (hossamnagy), commit `e272c16`, merged 2026-05-27, shipped v0.17.6. Guard flipped to feature flags (`inverter_is_hybrid`, `set_use_battery`) at `optimization.py:3462-3465`. Verified diff +6/-2.
- Status: resolved. Covers tmszdmsk's -247% and the relaxed-path half of ztega.

### Cause 3 — `inverter_ac_output_max`/`_input_max` default regressed 5000 → 0 → LIVE; ours; gated

`config_defaults.json` v0.17.2 = 5000; master = 0. Commit `1f26b03` ("align config_defaults with param_definitions, Option B per #830", 2026-05-12, in v0.17.3+) did it, undoing `221453e` (2025-12-20). Full `1f26b03` diff = exactly 4 keys: `historic_days_to_retrieve 9→2` and `load_forecast_method naive→typical` (both David-confirmed-correct) + the inverter pair (the only break).

Mechanism: `_add_hybrid_inverter_constraints` reads `inverter_ac_output_max` (`optimization.py:1180`); legacy CEC fallback fires only on `None` (`:1186`); a real 0 bypasses it and hard-caps AC at 0 → on hybrid the DC bus can't shed PV → genuinely infeasible.

- Ours: the #830 Option-B alignment, our commit, David-directed. Ownership comment already posted on #875 (do not repost).
- Fix: PR #934 (DRAFT, gated on David). Restore 5000, `param_definitions.json` first then `config_defaults.json`; hybrid feasibility regression test.

### Finding 2 — `publish_data` crashes `KeyError 'P_Load'` on double-infeasible → FIXED (our PR #933)

When MILP and relaxed LP are both infeasible, `perform_optimization` returns a frame with only `optim_status` (`optimization.py:3539-3547`). It's written to CSV; `publish_data` reloaded it (`command_line.py:2554-2557`, guarded only `is None`) and `_publish_standard_forecasts` did `opt_res_latest["P_Load"]` (`command_line.py:2270`) → KeyError.

- Fix: PR #933. Guard in `publish_data` (~:2557): if no `P_Load` column → log optim status + return None. Checks column presence not status string on purpose — relaxed "Optimal (Relaxed)" / "Optimal_Inaccurate" results carry P_Load and must still publish. Regression test `TestPublishInfeasibleGuard`.
- Status: READY, CI green. Robustness only. Hits g1za + ztega.

### Cause 4 — g1za's non-hybrid infeasibility → ROOT CAUSE PINNED

g1za is non-hybrid, so Cause 3's hybrid path returns early (`:1170`). Static trace of his exact inputs shows the problem is feasible in isolation. It is feasible on 0.17.2 (his log: cost 3.44) and infeasible on 0.17.3+, and stateful (first run after reboot fails, second succeeds; ztega reproduces independently). That rules out static input-infeasibility and points to a regression.

Bisect (good=v0.17.2, bad=v0.17.3, repro from g1za's posted config): first-bad = **`6901bef`** (PR #796, torsteinelv, "Fix logic flaw in grid/battery interaction constraints", first in v0.17.3). It reworked `set_nodischarge_to_grid`:

```python
# v0.17.2 (feasible) — power limit: total export may not exceed PV
if set_nodischarge_to_grid:
    constraints.append(p_grid_neg + p_pv >= 0)

# v0.17.3+ (infeasible) — binary coupling: discharge only while importing
if set_nodischarge_to_grid:
    constraints.append(E <= D)        # optimization.py:1307 (sibling set_nocharge_from_grid: D <= E, :1303)
```

The new rule also forbids the battery from discharging to cover **local load** during any export-capable timestep. For a config that must shed a large SOC (`soc_init 1.0 → soc_final 0.2`, ~21.6 kWh) with `set_nodischarge_to_grid:true` and few net-import timesteps, the battery has nowhere to place its energy and the solve is infeasible. Non-hybrid (AC-coupled) systems are hit hardest. The day-to-day PV/load variation explains the "restart fixes it" intermittency.

Reproduction (g1za's config, `.tmp/repro_g1za2.py`):

| scenario | v0.17.2 | v0.17.3 – v0.17.6 |
|---|---|---|
| PV ~7000 / load ~400, curtailment off | Optimal | Infeasible |
| PV ~9500 / load ~200, curtailment on | Optimal | Infeasible |

- #796 correctly fixed #795 (hybrid inverters like Deye that prioritize PV→load cannot export 100% PV while discharging). The binary coupling is just stricter than needed.
- Tracking: issue #936 (mechanism + repro + 3 fix directions: restore power-form / allow batt→load during export / gate `E <= D` on `inverter_is_hybrid`). Tagged torsteinelv + David. No fix PR yet — issue-first per AGENTS §5.

### Candidate B — out-of-band `soc_init` clamp removed → percent-vs-fraction runs away → DISTINCT regression, bad-input root

Commit `899c0bc` (v0.17.2, "allow out-of-band initial SOC recovery") removed the clamp (`soc_init = soc_min`/`soc_max`) and replaced it with pass-through ("keeping real initial SOC for optimization recovery", `utils.py:1518-1526`, verified against `899c0bc^`). Combined with the Big-M SOC-recovery trajectory, a percent-as-fraction misconfig (joshm74: bounds 10/90, soc 65) — previously clamped/tolerated ≤0.17.1 — now yields the runaway "-600%" plan.

- Distinct from Cause 3 (hybrid cap) and Cause 4 (g1za uses proper fractions). Root = bad input, amplified by missing validation.
- Tracking: issue #935. Design call for David: lenient clamp vs strict reject (SOC > 1). No PR till he picks.

## Disposition table

| Defect | Class | Status | Artifact |
|---|---|---|---|
| Finding 1 (relaxed drops constraints) | bug | Fixed v0.17.6 | PR #885 (upstream) |
| Finding 2 (`P_Load` KeyError) | robustness | Fixed, ready | PR #933 |
| Cause 3 (inverter default 0) | regression (ours) | live, gated | PR #934 (draft) |
| Cause 4 (g1za non-hybrid infeasible) | regression | root pinned, no fix yet | issue #936 |
| Candidate B (soc clamp removed) | regression, bad-input | live | issue #935 |

## scan of 1f26b03

Touched exactly 4 `config_defaults.json` keys: `historic_days_to_retrieve 9→2` + `load_forecast_method naive→typical` (David-confirmed-correct) + the `inverter_ac_output_max`/`_input_max` pair (the only break). No other bad-aligned defaults.

## Comms delivered on #875

- g1za reply asking for failing request JSON — issuecomment-4610775215.
- g1za root-cause follow-up (bisect to #796, workaround `set_nodischarge_to_grid:false`, points to #936) — issuecomment-4611719947.
- Pre-existing Cause-3 ownership comment — left untouched.

## Supporting infra

- PR #938 — raise `test_schema_contract.py` node subprocess timeout 30→120s (Windows CI flake, unrelated to the above; surfaced as the lone red on #934 and other PRs). Test-only.

## Open / blocked on others

- David on #934: confirm 5000 + guard placement → ready/merge.
- David on #935: clamp vs reject → PR.
- David + torsteinelv on #936: fix form → PR for Cause 4.
- #938 merge → rebase #934 to clear its Windows flake.
