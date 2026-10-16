"""Board bookkeeping after the July-October 2026 pause (upstream 0.17.8 -> 0.18.6).

Run from board/ as OptimalNothing90 after `python fetch.py` showed 0 drift.
Idempotent: field sets are absolute, body edits use marker guards, new cards are
skipped when their id already exists in items.json.

1. ISSUE-807-U-2 (link, Todo): issue #807 was closed 2026-09-07 by PR #1107 (Sjeiz,
   in v0.18.3). Case B: issue card -> Done / Wont Do, PR-1107 link card added.
2. U-3 (Todo, P0): premise wrong (2xx != 200 to the failure branch is correct, Solcast
   only ships forecasts with 200). Re-scoped to the real gap (201/1xx/3xx fall through
   to data["forecasts"]), Status -> Ideas, Priority -> P3. Title/body rewritten.
3. U-6 (Todo, P0): Open-Meteo main fetch fixed by PR #950; three sessions still
   without timeout at v0.18.6. Body note, Priority -> P2. Offered to HFZR2005 in #935.
4. AM-7 (Todo): still valid, re-verified at v0.18.6. Body note. Offered to HFZR2005.
5. REL-1 (Candidates): partly covered by tests/test_defaults_smoke.py. Body note.
6. DISC-823 (In Progress): zero comments since 2026-04-28 -> Done / Wont Do.
7. DISC-824 (In Progress): no activity since 2026-08-01, call never happened -> Ideas.
8. New drafts: FLEXD-1 (issue #1 review findings), DISC-1157 (federated RFC + dry_run),
   DISC-1150 (per-inverter / multi-battery phase 2, EV requirements).
9. EPIC-EVCC: status note 2026-10-16.
"""

from lib import (
    add_content_to_project,
    add_draft_to_project,
    append_to_body_idempotent,
    find_item,
    load_items,
    save_items,
    set_field,
    update_draft_title_body,
)

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
MARK = "## Re-check 2026-10-16"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]


def set_status(card: dict, field: str, value: str) -> None:
    set_field(PROJECT_ID, card["item_id"], field_ids[field], option_ids[field][value])
    card[field] = value


def note(card: dict, text: str) -> None:
    changed, body = append_to_body_idempotent(card["draft_id"], MARK, f"\n\n{MARK}\n{text}")
    card["body"] = body
    print(f"  {card['id']}: body {'appended' if changed else 'unchanged (marker present)'}")


def insert_after(anchor_id: str, entry: dict) -> None:
    idx = next(i for i, it in enumerate(data["items"]) if it["id"] == anchor_id)
    data["items"].insert(idx + 1, entry)


# 1) ISSUE-807-U-2 -> Done, PR-1107 link card ------------------------------------
issue = find_item(data, "ISSUE-807-U-2")
set_status(issue, "Status", "Done / Wont Do")
print("ISSUE-807-U-2 -> Done / Wont Do (closed 2026-09-07 by PR #1107)")

PR_NODE_ID = "PR_kwDOGC8VbM8AAAABCHjLjg"
PR_FIELDS = {
    "Status": "Done / Wont Do",
    "Category": "A: Code-Lifecycle",
    "Phase": "Phase 2",
    "Priority": "P1",
    "Effort": "M",
    "Scope": "Upstream",
}
try:
    find_item(data, "PR-1107")
    print("PR-1107 already present")
except KeyError:
    pr_item_id = add_content_to_project(PROJECT_ID, PR_NODE_ID)
    for k, v in PR_FIELDS.items():
        set_field(PROJECT_ID, pr_item_id, field_ids[k], option_ids[k][v])
    insert_after(
        "ISSUE-807-U-2",
        {
            "id": "PR-1107",
            "title": "feat: SOC-dependent charge power ceiling",
            "type": "link",
            "content_id": PR_NODE_ID,
            **PR_FIELDS,
            "item_id": pr_item_id,
            "content_url": "https://github.com/davidusb-geek/emhass/pull/1107",
            "repository": "davidusb-geek/emhass",
            "number": 1107,
        },
    )
    print("PR-1107 link card added -> Done / Wont Do")

# 2) U-3 re-scoped ----------------------------------------------------------------
u3 = find_item(data, "U-3")
U3_TITLE = "U-3: forecast.py Solcast status handling not exhaustive (201/1xx/3xx reach data['forecasts'])"
U3_BODY = """Re-scoped 2026-10-16 after re-reading `_get_weather_solcast` at v0.18.6 (`src/emhass/forecast.py:743-756`).

The original premise ("2xx-other-than-200 goes to the failure branch, confirmed bug") was wrong: Solcast returns `forecasts` only with 200, so returning False for 202-299 is the safe outcome. Only the log message ("check API key and rooftop ID") is misleading for a 2xx.

The real gap is the opposite direction: statuses outside {200, 402, 429, >=400, 202-299}, i.e. 201, 1xx and 3xx, match no branch and fall through to `data["forecasts"]`. First roof: `UnboundLocalError`. Later roofs (multi-roof loop from PR #1091): the previous roof's `data` is silently reused. aiohttp follows redirects by default, so 3xx is rare; practical risk is low.

Suggested fix: make the status handling exhaustive (`if status != 200: ...`) and add a test with status 201/204 next to the existing 429/500 Solcast tests in `tests/test_forecast.py`.

Priority dropped P0 -> P3. Not offered to contributors; only worth doing when someone is in that function anyway.

Original card text (superseded): `forecast.py:441` `... or (202 <= int(response.status) <= 299)` puts every 2xx-other-than-200 into the failure branch. Confirmed bug. 1-line fix. File issue then PR."""
update_draft_title_body(u3["draft_id"], U3_TITLE, U3_BODY)
u3["title"] = U3_TITLE
u3["body"] = U3_BODY
set_status(u3, "Status", "Ideas")
set_status(u3, "Priority", "P3")
print("U-3 rewritten -> Ideas / P3")

# 3) U-6 -------------------------------------------------------------------------
u6 = find_item(data, "U-6")
note(
    u6,
    "Partly fixed. The Open-Meteo main fetch got `aiohttp.ClientTimeout(total=open_meteo_request_timeout)` (12 s) in PR #950 (merged 2026-06-08, in 0.17.8). "
    "At v0.18.6 three `aiohttp.ClientSession()` calls in `src/emhass/forecast.py` still have no timeout: Solcast (:739), Forecast.Solar (:841), Open-Meteo covariates (:1190, new code). "
    "\"Blocks indefinitely\" was overstated: aiohttp's default total timeout is 300 s, which the Solcast multi-roof loop multiplies. "
    "Note for the PR: Solcast quota is reserved before the request, so a timeout burns quota without data. "
    "Offered to HFZR2005 in davidusb-geek/emhass#935 on 2026-10-16. Priority P0 -> P2.",
)
set_status(u6, "Priority", "P2")

# 4) AM-7 ------------------------------------------------------------------------
note(
    find_item(data, "AM-7"),
    "Still valid at v0.18.6: 124 shared keys, 77 shared scalar keys compared, 0 drift today. "
    "`tests/test_schema_contract.py:146-211` checks key presence and Python type only; `tests/test_openapi.py`, `tests/test_runtime_params.py` and the prek hooks never compare values. "
    "New since the card: `ignore_pv_feedback_during_curtailment` exists only in param_definitions.json (reverse direction), so the guard must decide how to treat keys present in one file only. "
    "Natural home: next to `test_config_defaults_keys_match_param_definitions`. Offered to HFZR2005 in davidusb-geek/emhass#935 on 2026-10-16.",
)

# 5) REL-1 -----------------------------------------------------------------------
note(
    find_item(data, "REL-1"),
    "Partly covered. CI already runs the full pytest suite on three OS (`python-test.yml`), so no separate job is needed. "
    "`tests/test_defaults_smoke.py` (added 2026-05-22, extended by #934) runs a real optimization on defaults and pins the #875 hybrid-infeasible regression (`test_hybrid_inverter_feasible_on_default_ac_output_max`). "
    "Missing: a parametrized matrix (hybrid x battery x PV x deferrable x 30/60 min step) with output bounds (SOC range, grid power within inverter limits, power balance); the two default-config tests assert only \"does not raise\". "
    "Re-scoped as \"extend test_defaults_smoke.py into a matrix\", issue-first for scope and CI time. Mentioned to HFZR2005 in #935 as the larger option.",
)

# 6) DISC-823 -> Done / Wont Do ----------------------------------------------------
d823 = find_item(data, "DISC-823")
note(d823, "Zero comments since the opening post (2026-04-28). Crowdsourcing did not take; closed on the board. A `good_practices.md` would have to be written from our own data, which is DOC-cookbook territory.")
set_status(d823, "Status", "Done / Wont Do")
print("DISC-823 -> Done / Wont Do")

# 7) DISC-824 -> Ideas (parked) ----------------------------------------------------
d824 = find_item(data, "DISC-824")
note(
    d824,
    "Parked. Last activity 2026-08-01; the proposed call with LesIT1 and scruysberghs never happened. "
    "Upstream now has `docs/cookbook/ev_evcc_executor.md` (HA/Jinja variant of EMHASS-plans/evcc-executes); our angle is the NR/MQTT variant (EV-9). "
    "Multi-battery phase 2 (V2G, intermittent connection) is the EV core thread and lives in LesIT1's programme (#610, #1150); see DISC-1150.",
)
set_status(d824, "Status", "Ideas")
print("DISC-824 -> Ideas (parked)")

# 8) New draft cards ----------------------------------------------------------------
NEW_CARDS = [
    {
        "id": "FLEXD-1",
        "after": "EPIC-EVCC",
        "title": "FLEXD-1: flexd review findings (OptimalNothing90/emhass-contributions#1, LesIT1)",
        "body": """LesIT1's adversarial review of `prototypes/flexd/` (2026-07-11): 3 HIGHs, 12 Mediums, a tail of Lows. Full write-up with repros: https://github.com/OptimalNothing90/emhass-contributions/issues/1

Status 2026-10-16: the three HIGHs are fixed on main (e487a5a Infinity/NaN + sanity bounds, f7f8aa5 refresh never shortens + re-trigger keyed on deadline, 380512b overlap x P/nominal accrual, also closes Medium 6). Suite 150 -> 173 tests. Reply posted in the issue; LesIT1's shadow run against his production setup can start.

Open: Mediums 1-5, 7-12 and the Lows. Mediums 4 and 5 (upstream `hours=0` gate semantics, fractional hours on a semi-continuous grid) need a check against the pinned EMHASS (now v0.18.6) before deciding. Mediums 2 (standing manager lock + ledger `.bak`), 3 (`not_before` across midnight) and 12 (full registry rewrite per refresh) are confirmed in code.

Member of EPIC-EVCC (RFC 0001 sidecar, Discussion #931).""",
        "fields": {"Status": "In Progress", "Category": "Infra", "Phase": "Phase 4", "Priority": "P1", "Effort": "M", "Scope": "Local"},
    },
    {
        "id": "DISC-1157",
        "after": "FLEXD-1",
        "title": "DISC-1157: Discussion #1157 federated backend RFC + dry_run (positioning of flexd)",
        "body": """ameetdesh's RFC (2026-10-01) with draft PR #1158: an opt-in Dantzig-Wolfe backend that plans each device as its own subproblem, coordinates at the meter by prices, splits savings, plus a `dry_run` runtime parameter (solve without persisting, plan in the HTTP response). Same motivation as flexd (several optimisers colliding, evcc), one layer deeper (inside the solver).

Maintainer line so far: open to the direction, no external compiled dependency (merged the native DP solver #1191 instead), opt-in features need a zero-regression argument. LesIT1 and MMicieli want `dry_run` split into its own PR; MMicieli linked it to the what-if/context idea from #931.

Our position (decided 2026-10-16): flexd is the demand-lifecycle layer in front of a stateless core (registration, persistence, ownership), not a competing coordinator. `dry_run` is the core primitive flexd needs for context/what-if. Actions: +1 the `dry_run` split with a concrete flexd use case; sharpen RFC 0001 in #931 accordingly (after the HIGH fixes). Watch #1158 for the split.

Source: https://github.com/davidusb-geek/emhass/discussions/1157""",
        "fields": {"Status": "Ideas", "Category": "Infra", "Phase": "Phase 4", "Priority": "P1", "Effort": "S", "Scope": "Discussion-Only"},
    },
    {
        "id": "DISC-1150",
        "after": "DISC-1157",
        "title": "DISC-1150: multi-battery phase 3 (per-inverter) and phase 2 (V2G / intermittent EV) - EV requirements input",
        "body": """LesIT1's multi-battery programme from #610: phase 1 (N stationary batteries) shipped in 0.18.0 (#1032); phase 3 (per-inverter modelling) is in design in #1150 and waiting for David's go; phase 2 (V2G, intermittently connected battery = the EV) is "not scheduled" as of 2026-09-30.

Phase 2 is what our former N2 item (EV SoC model in core) wanted. Decision 2026-10-16: N2 is no longer a core item of ours. Our contribution is requirements from the evcc side when LesIT1 opens the phase 2 round: plug-in/departure windows, target SOC at departure, availability as a per-step mask, interaction with evcc as executor (Topology A). Watch #1150 and #610.

Sources: https://github.com/davidusb-geek/emhass/discussions/1150 , https://github.com/davidusb-geek/emhass/discussions/610""",
        "fields": {"Status": "Ideas", "Category": "A: Code-Lifecycle", "Phase": "Phase 4", "Priority": "P2", "Effort": "S", "Scope": "Discussion-Only"},
    },
]

for card in NEW_CARDS:
    try:
        find_item(data, card["id"])
        print(f"{card['id']} already present, skipped")
        continue
    except KeyError:
        pass
    item_id, draft_id = add_draft_to_project(PROJECT_ID, card["title"], card["body"])
    for k, v in card["fields"].items():
        set_field(PROJECT_ID, item_id, field_ids[k], option_ids[k][v])
    insert_after(
        card["after"],
        {
            "id": card["id"],
            "title": card["title"],
            "type": "draft",
            "body": card["body"],
            **card["fields"],
            "item_id": item_id,
            "draft_id": draft_id,
        },
    )
    print(f"{card['id']} created -> {card['fields']['Status']}")

# 9) EPIC-EVCC status note ----------------------------------------------------------
note(
    find_item(data, "EPIC-EVCC"),
    "flexd MVP (prototypes/flexd/) merged 2026-07-06; LesIT1's review in OptimalNothing90/emhass-contributions#1, its three HIGHs fixed on main 2026-10-16 (see FLEXD-1), shadow run pending. "
    "Adjacent upstream work: Discussion #1157 (federated backend + dry_run, see DISC-1157) and multi-battery phase 2 (V2G, see DISC-1150). "
    "Repositioned: flexd = demand-lifecycle layer in front of a stateless core; dry_run = core primitive for what-if; EV SoC model is phase 2 of LesIT1's programme, our part is requirements input.",
)

save_items(data)
print("items.json saved")
