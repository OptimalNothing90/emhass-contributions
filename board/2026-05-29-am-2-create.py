"""One-shot: create AM-2 board draft (param_def <-> config_defaults drift-guard test)."""

from lib import add_draft_to_project, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

TITLE = "AM-2: param_definitions <-> config_defaults shared-default drift-guard test"

BODY = """\
Add a CI test asserting that **shared scalar defaults agree** between
`src/emhass/static/data/param_definitions.json` (SoT) and
`src/emhass/data/config_defaults.json`.

## Why
David's 2026-05-12 decision (#830 / #845): `param_definitions.json` is the source of
truth for defaults; `config_defaults.json` aligns. The alignment is **not code-enforced**
- it drifted once (4 keys: historic_days_to_retrieve, load_forecast_method,
inverter_ac_output_max/input_max), fixed by #845. Nothing prevents recurrence.

Verified 2026-05-29: **no current drift** (4 saga keys aligned, 75 shared scalar keys
equal). This card is *prevention*, not a fix.

## Deliverable
- `tests/` test: for every key present in BOTH files with a scalar default, assert
  `param_definitions.default_value == config_defaults[key]` (type-aware compare).
- Exclude by design: array.* / object params (param_def stores a per-load **scalar
  template**; config_defaults stores a runnable **example** array - e.g.
  `nominal_power_of_deferrable_loads` 3000 vs [3000,750]) and the 8 runtime-only keys
  config_defaults has but param_def lacks (data_path, deferrable_load_groups, model_type,
  num_lags, perform_backtest, sklearn_model, split_date_delta, var_model).

## NOT in scope
Generating / eliminating `config_defaults.json` from `param_definitions.json`. config_defaults
is a runnable example config carrying multi-load example arrays + runtime-only keys param_def
does not have, so mechanical generation is infeasible without a deeper redesign (param_def
coverage = AC-2b and beyond) + maintainer sign-off.

## Related
- AM-1 (openapi.json) sources its `default` from param_def (SoT); this test protects that
  assumption. See `docs/superpowers/specs/2026-05-29-am-1-design.md` Decision #11.
- SoT decision: #830 / #845.
- PR-first, but flag in the PR body that it touches David's declared SoT domain.

Effort S, prevention-priority (P2).
"""

item_id, draft_id = add_draft_to_project(PROJECT_ID, TITLE, BODY)
print(f"created AM-2 draft: item={item_id} draft={draft_id}")

opts = {
    "Status": "Candidates",
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P2",
    "Effort": "S",
    "Scope": "Upstream",
}

# field/option ids (from items.json _meta, captured 2026-05-29)
FIELD = {
    "Status": "PVTSSF_lAHOAfZrVs4BV1jUzhROajQ",
    "Category": "PVTSSF_lAHOAfZrVs4BV1jUzhRW94U",
    "Phase": "PVTSSF_lAHOAfZrVs4BV1jUzhRW96Y",
    "Priority": "PVTSSF_lAHOAfZrVs4BV1jUzhRW9-k",
    "Effort": "PVTSSF_lAHOAfZrVs4BV1jUzhRW9-o",
    "Scope": "PVTSSF_lAHOAfZrVs4BV1jUzhRW9_k",
}
OPTION = {
    "Status": {"Candidates": "b4dd802b"},
    "Category": {"Infra": "a4ba5af5"},
    "Phase": {"Phase 3": "ab73386d"},
    "Priority": {"P2": "e37cacf7"},
    "Effort": {"S": "77b2c36d"},
    "Scope": {"Upstream": "1e7b6ecd"},
}

for field, val in opts.items():
    set_field(PROJECT_ID, item_id, FIELD[field], OPTION[field][val])
    print(f"  set {field} = {val}")

print("done")
