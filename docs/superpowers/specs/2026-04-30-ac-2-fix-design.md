# AC-2-fix — Design

**Date:** 2026-04-30
**Card:** `AC-2-fix` (board/items.json)
**Audit source:** `audits/2026-04-28-param-definitions.md` (§3)
**Target repo:** `davidusb-geek/emhass` (via `OptimalNothing90/emhass` fork)
**Effort:** XS
**Phase / Priority:** Phase 1 / P2

## 1. Problem

`param_definitions.json` is the GUI-hint metadata that drives the EMHASS web config form. `config_defaults.json` is the authoritative runtime default source. The schema audit on 2026-04-28 found five entries where the schema defaults disagree with the runtime defaults, so new installations see initial form values that do not match what the solver actually uses.

Examples:
- `historic_days_to_retrieve`: schema says `2`, runtime uses `9`. Description in the schema literally reads "Defaults to 2" — schema lies to readers.
- `inverter_ac_output_max` / `inverter_ac_input_max`: schema says `0` (a "max" of zero is nonsensical), runtime uses `5000`.
- `load_forecast_method`: schema chooses `"typical"`, runtime + Description point at `"naive"`.

## 2. Goal

Bring the GUI schema back in line with the runtime defaults for the five audited mismatches. Single PR upstream, no behavior change in solver / runtime / tests, only schema-displayed initial form values change.

## 3. Decisions (from brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| 1 | PR scope | All 5 actionable items |
| 2 | Filing mode | Direct PR with audit link in body |
| 3 | Drift protection | None (no test, no script in upstream) |
| 4 | Approach | Single commit, inline before/after table + audit link |

## 4. Files touched

- **Edit:** `src/emhass/static/data/param_definitions.json` (in `claude-code/emhass/`, the fork)
- **No edit:** `src/emhass/data/config_defaults.json` (already correct — source of truth)
- **No edit:** `tests/` (per Decision 3)

## 5. Concrete edits

| Key | Field | Before | After |
|-----|-------|--------|-------|
| `historic_days_to_retrieve` | `default_value` | `2` | `9` |
| `historic_days_to_retrieve` | `Description` | `"...Defaults to 2"` | `"...Defaults to 9"` |
| `inverter_ac_output_max` | `default_value` | `0` | `5000` |
| `inverter_ac_input_max` | `default_value` | `0` | `5000` |
| `load_forecast_method` | `default_value` | `"typical"` | `"naive"` |
| `ignore_pv_feedback_during_curtailment` | `input` | `"bool"` | `"boolean"` |

Diff size: 5 hunks, ~6 changed lines. No structural changes, no key reordering.

Anchored line locations on current upstream tip (2026-04-30 re-verify):
- `historic_days_to_retrieve`: line 121-126
- `load_forecast_method`: line 152-157
- `inverter_ac_output_max`: line 214-219
- `inverter_ac_input_max`: line 220-225
- `ignore_pv_feedback_during_curtailment`: line 572-577

## 6. Branch + commit

**Branch:** `fix/param-definitions-default-mismatches`

**Account check:** `gh auth status` before push, switch to `OptimalNothing90` for upstream PR, switch back to `mschaepers` after.

**Commit message:**

```
fix(schema): correct param_definitions.json default mismatches

Five entries in param_definitions.json (GUI hint metadata) disagreed
with config_defaults.json (authoritative runtime defaults). Schema
defaults dictate initial form values shown to users; mismatches mislead
new installations. Source-of-truth (config_defaults.json) unchanged.

- historic_days_to_retrieve: 2 → 9 (default_value + Description text)
- inverter_ac_output_max: 0 → 5000
- inverter_ac_input_max: 0 → 5000
- load_forecast_method: "typical" → "naive"
- ignore_pv_feedback_during_curtailment: input "bool" → "boolean"

Findings derived from input-side schema audit cross-checking
param_definitions.json against config_defaults.json and
utils.treat_runtimeparams. Audit + reproducer:
https://github.com/OptimalNothing90/emhass-contributions/blob/master/audits/2026-04-28-param-definitions.md
```

## 7. PR body

**Title:** `fix(schema): correct 5 default mismatches in param_definitions.json`

**Body:**

```markdown
## Summary
Corrects 5 default-value / input-spelling mismatches in
`param_definitions.json` against `config_defaults.json`. Source-of-truth
(`config_defaults.json`) unchanged; only the GUI schema is brought back
in line so the web config form shows the actual runtime defaults.

## Before / After

| Key | Field | Before | After | Source |
|-----|-------|--------|-------|--------|
| historic_days_to_retrieve | default_value | 2 | 9 | config_defaults.json |
| historic_days_to_retrieve | Description | "...Defaults to 2" | "...Defaults to 9" | (text alignment) |
| inverter_ac_output_max | default_value | 0 | 5000 | config_defaults.json |
| inverter_ac_input_max | default_value | 0 | 5000 | config_defaults.json |
| load_forecast_method | default_value | "typical" | "naive" | config_defaults.json |
| ignore_pv_feedback_during_curtailment | input | "bool" | "boolean" | other booleans in file |

## Verification
Reproducer script + full audit:
https://github.com/OptimalNothing90/emhass-contributions/blob/master/audits/2026-04-28-param-definitions.md (Section 3)

Re-verified against current `master` tip on 2026-04-30 — all 5 still hold.

## Notes
- No behavior change in optimisation, solver, or runtime defaults — only
  the schema-displayed initial form values change.
- Sibling concerns tracked separately:
  - PR #817 (regression_model typo) — already merged
  - Issue #818 (ignore_pv_feedback_during_curtailment runtime wiring) — independent of the spelling fix here
```

## 8. Verification

**Pre-push:**

1. JSON syntax: `python -c "import json; json.load(open('src/emhass/static/data/param_definitions.json', encoding='utf-8'))"` → no error.
2. Re-run audit reproducer (`audits/2026-04-28-param-definitions.md` §6 script) → expect §3 mismatch list **empty**.
3. `pytest tests/` → green. No test loads `param_definitions.json` (verified via grep); existing tests touch the same keys only through `config_defaults.json` / `utils.py`, which are unchanged. Run as sanity check against unexpected coupling.
4. Container / UI smoke (per AGENTS.md §5): `docker compose up`, browser → config page, the five fields show new defaults.

**Post-merge:**

- Board card `AC-2-fix` → status `Done`.
- Audit doc gets §7 entry: `AC-2-fix merged in PR #N`.

## 9. Out of scope

- AC-2a (`unit` field additive) — separate PR, separate card.
- AC-2b (~38 missing keys) — depends on AC-2a, separate card.
- Issue #818 wiring (`ignore_pv_feedback_during_curtailment` runtime path) — only the spelling correction here; wiring stays open.
- Borderline `operating_hours_of_each_deferrable_load` array-shape (per Decision 1).
- Drift regression test / reproducer script in upstream (per Decision 3).
- Description-text refactors other than the one line on `historic_days_to_retrieve`.
- `load_peak_hour_periods` struct-keys (informational, no fix needed).

## 10. Risks

| Risk | Mitigation |
|------|-----------|
| Maintainer rejects `load_forecast_method "typical" → "naive"` as intentional | Drop that hunk on review request, keep remaining 4 fixes |
| Maintainer wants spelling fix coupled with #818 | Same: drop hunk, file separately |
| Maintainer questions `5000` choice for inverter max defaults | Reply: `config_defaults.json` is `5000`, source-of-truth consistency. No new policy choice introduced |
| Re-verify on push day reveals new drift | Audit reproducer re-run before push catches it; update PR body / scope accordingly |

## 11. Sequencing

This card is independent of AC-2a and AC-2b. Land first; AC-2a is additive (no conflict on default_value); AC-2b uses AC-2a's unit enum and may add ~38 entries (no conflict either).
