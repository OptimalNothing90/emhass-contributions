"""One-shot: create AC-2c (runtime_output.json) board card + add audit-refs to AM-1b / AM-7.

Captures the 2026-05-29 runtime-schema-family research so AC-2c/AM-1b/AM-7 keep the context.
"""

from lib import (
    add_draft_to_project,
    append_to_body_idempotent,
    find_item,
    load_items,
    set_field,
)

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

FIELD = {
    "Status": "PVTSSF_lAHOAfZrVs4BV1jUzhROajQ",
    "Category": "PVTSSF_lAHOAfZrVs4BV1jUzhRW94U",
    "Phase": "PVTSSF_lAHOAfZrVs4BV1jUzhRW96Y",
    "Priority": "PVTSSF_lAHOAfZrVs4BV1jUzhRW9-k",
    "Effort": "PVTSSF_lAHOAfZrVs4BV1jUzhRW9-o",
    "Scope": "PVTSSF_lAHOAfZrVs4BV1jUzhRW9_k",
}
OPT = {
    "Status": {"Candidates": "b4dd802b"},
    "Category": {"Infra": "a4ba5af5"},
    "Phase": {"Phase 3": "ab73386d"},
    "Priority": {"P1": "8a1c3323"},
    "Effort": {"M": "a9a065e3"},
    "Scope": {"Upstream": "1e7b6ecd"},
}

AC2C_TITLE = "AC-2c: runtime_output.json - publish/output routing schema"
AC2C_BODY = """\
New `src/emhass/static/data/runtime_output.json` - machine-readable schema for the runtime
OUTPUT / publish-routing params (Bucket B). Sibling to AC-2b's runtime_params.json (input) in
the 4-file schema architecture (param_definitions / runtime_params / runtime_output / response-schemas).

Contents:
- 15x custom_*_id entity overrides - NESTED objects {entity_id, device_class, unit_of_measurement,
  friendly_name} (custom_pv_forecast_id, custom_load_forecast_id, custom_grid_forecast_id,
  custom_cost_fun_id, custom_batt_forecast_id, custom_batt_soc_forecast_id, custom_pv_curtailment_id,
  custom_hybrid_inverter_id, custom_optim_status_id, custom_unit_load_cost_id, custom_unit_prod_price_id,
  custom_deferrable_forecast_id [list], custom_predicted_temperature_id [list], custom_heating_demand_id [list]).
- publish_prefix (string, default "")
- entity_save (boolean, default false - persists result entities to data_path/entities)
- continual_publish (boolean - runtime override of the config publish loop)

plan_output_schema.md maps each result column -> its custom_*_id; keep consistent.

Needs its own brainstorm for the nested-object design (input:"object" w/ nested schema vs opaque).
PR-first / structurally-discussion-first like AC-2b.

Full research + classification: audits/2026-05-29-runtime-schema-family.md (Bucket B + section 3).
Downstream: AM-1b reads this for the /action + publish openapi. Effort M (15 nested entries + design).
"""

# --- create AC-2c (idempotency guard) ---
data = load_items()
try:
    find_item(data, "AC-2c")
    print("AC-2c already exists - skipping create")
except KeyError:
    item_id, _ = add_draft_to_project(PROJECT_ID, AC2C_TITLE, AC2C_BODY)
    print(f"created AC-2c: item={item_id}")
    for f, v in {
        "Status": "Candidates",
        "Category": "Infra",
        "Phase": "Phase 3",
        "Priority": "P1",
        "Effort": "M",
        "Scope": "Upstream",
    }.items():
        set_field(PROJECT_ID, item_id, FIELD[f], OPT[f][v])
    print("  fields set: Candidates/Infra/Phase 3/P1/M/Upstream")

# --- audit-refs into AM-1b / AM-7 (idempotent) ---
MARKER = "runtime-schema-family"
am1b_suffix = (
    "\n\n## Prep captured 2026-05-29\n"
    "Design context for the /action openapi composition is in "
    "`audits/2026-05-29-runtime-schema-family.md` (section 3 AM-1b + buckets A/B/C). AM-1b composes "
    "per-/action requestBodies from runtime_params.json (AC-2b) + runtime_output.json (AC-2c) + the "
    "overridable param_definitions entries; action->param map from treat_runtimeparams set_type "
    "branches. Gated on AC-4 merge + AC-2b + AC-2c.\n"
)
am7_suffix = (
    "\n\n## Bucket-E data captured 2026-05-29\n"
    "The 7 config-keys to align (in config_defaults, missing from param_definitions) + defaults are "
    "in `audits/2026-05-29-runtime-schema-family.md` (Bucket E): model_type=load_forecast, var_model, "
    "sklearn_model=KNeighborsRegressor, num_lags=48, split_date_delta=48h, perform_backtest=false, "
    "deferrable_load_groups=[] (data_path excluded - internal). Plus the shared-scalar drift-guard test.\n"
)
for bid, draft_id, suffix in [
    ("AM-1b", find_item(data, "AM-1b")["draft_id"], am1b_suffix),
    ("AM-7", find_item(data, "AM-7")["draft_id"], am7_suffix),
]:
    changed, _ = append_to_body_idempotent(draft_id, MARKER, suffix)
    print(f"{bid}: {'appended audit-ref' if changed else 'already had ref'}")

print("done")
