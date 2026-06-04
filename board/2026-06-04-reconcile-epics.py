"""Reconcile adds (2026-06-04): 3 goal-epics + 2 reliability work-items.

Per spec §B1/B2/B4/B5/B6. Create-only: items.json catches up on next fetch.py.
ids derived from title prefix before ':' — all asserted free first.
"""

from lib import add_draft_to_project, load_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

# id, title, body, fields
CARDS = [
    (
        "EPIC-LLM",
        "EPIC-LLM: LLM-ready — machine-readable EMHASS",
        """\
Strategic goal epic. Make EMHASS machine-readable for coding agents + LLM consumers,
framed as **single schema -> many generated surfaces** (`param_definitions.json` = SoT).

Member items: AC-2 / AC-2c (schema), AM-1 / AM-1b (openapi), AM-2 (config.md docs),
AG-8 (schema-driven config UI), plus future llms.txt and runtime config-validation
(Pydantic/jsonschema of merged config -> clear errors; attacks the #869 null-default class).

Done-criterion: schema spine published + openapi runtime payloads + config.md auto-generated
+ config validated at load + config form schema-driven, with no drift between them.
""",
        {
            "Status": "In Progress",
            "Category": "A: Code-Lifecycle",
            "Phase": "Phase 3",
            "Priority": "P1",
            "Effort": "L",
            "Scope": "Discussion-Only",
        },
    ),
    (
        "EPIC-EVCC",
        "EPIC-EVCC: EV-EVCC integration — shared-plan registry",
        """\
Strategic goal epic. EMHASS = whole-house planner, evcc = executor; coordinated via a
stateful shared-plan registry (RFC 0001, posted as Discussion #931, awaiting community/
David resonance).

Member items: EV-9 (cookbook NR/MQTT/EVCC recipe), CE-7 (GUI EV-section).

Downstream (sibling RFCs, public worked-example) is gated on #931 resonance and is not
carded yet. Done-criterion: a recommend-only plan-exchange contract that evcc can consume,
accepted in EMHASS-core or shipped as an agreed integration surface.
""",
        {
            "Status": "In Progress",
            "Category": "B: End-User-Ops",
            "Phase": "Phase 4",
            "Priority": "P1",
            "Effort": "XL",
            "Scope": "Discussion-Only",
        },
    ),
    (
        "EPIC-REL",
        "EPIC-REL: Reliability / regression-harness",
        """\
Strategic goal epic. Reliability is the floor under both other goals; the v0.17.x
contributor wave + our own #830 -> #875 regression show happy-path-only changes reach
production.

Pillars:
1. Optim feasibility smoke-gate (REL-1) — would have caught #875 (hybrid infeasible) + #869.
2. Schema drift-guard — AM-7 (param_definitions <-> config_defaults).
3. Battery-MILP constraint correctness — refs #875 / #935 / #936 / ISSUE-807-U-2 (SoC-clamp,
   set_nodischarge_to_grid, dynamic charge-power all cluster in the battery constraint set).
4. Forecast-fetch resilience — refs U-3 / U-5 / U-6 (consistent timeout/retry/fallback
   across all forecast.py providers).
""",
        {
            "Status": "In Progress",
            "Category": "Infra",
            "Phase": "Phase 3",
            "Priority": "P1",
            "Effort": "XL",
            "Scope": "Discussion-Only",
        },
    ),
    (
        "REL-1",
        "REL-1: Optim feasibility smoke-gate (CI)",
        """\
Flagship of EPIC-REL. A CI job that runs a full optimization over a small matrix of
reference configs (incl. hybrid + battery) and asserts the run is feasible and key outputs
are within sane bounds. Catches the regression class of #875 (hybrid infeasible) and #869.
Can ride alongside AM-7. Issue-first, then PR.
""",
        {
            "Status": "Candidates",
            "Category": "A: Code-Lifecycle",
            "Phase": "Phase 3",
            "Priority": "P1",
            "Effort": "M",
            "Scope": "Upstream",
        },
    ),
    (
        "REL-2",
        "REL-2: AGENTS.md enforcement tightening",
        """\
Make `check_def_loads` mandatory + add a vanilla-optim-smoke reference in AGENTS.md;
honor-system -> enforced. **Gated on #886 + #900 landing** so AGENTS.md can point at real
enforcement. Card exists for visibility only until then (Status Ideas, do not promote).
""",
        {
            "Status": "Ideas",
            "Category": "A: Code-Lifecycle",
            "Phase": "Phase 3",
            "Priority": "P2",
            "Effort": "S",
            "Scope": "Upstream",
        },
    ),
]


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]
    existing_ids = {i["id"] for i in data["items"]}

    for board_id, title, body, fields in CARDS:
        if board_id in existing_ids:
            print(f"SKIP {board_id}: id already exists — would collide, not creating")
            continue
        item_id, draft_id = add_draft_to_project(PROJECT_ID, title, body)
        print(f"created {board_id}: item={item_id} draft={draft_id}")
        for fname, val in fields.items():
            set_field(PROJECT_ID, item_id, field_ids[fname], option_ids[fname][val])
        print(f"  fields set: {fields}")

    print("=== Done — run fetch.py to ingest ===")


if __name__ == "__main__":
    main()
