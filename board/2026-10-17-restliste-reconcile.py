"""Board bookkeeping: rest-of-board reconcile after the candidates audit against v0.18.6 (2026-10-17).

Run from board/ as OptimalNothing90 after `python fetch.py` showed 0 drift. Idempotent
(absolute field sets, marker-guarded body notes).

Audit: .tmp/audit_candidates_0186.md (gitignored). Verdicts:
- U-1 still valid, already upstream as issue #1106; flexd works around it -> Ideas, note.
- U-4, U-5 (superseded by #729), U-7, U-8 (fixed by #1227) -> Done / Wont Do.
- AC-2b shipped as PR #915 (runtime_params.json) -> Done; AC-2 umbrella -> Done (AC-2a #850, AC-2b #915).
- AC-2c, AM-1b: issue-first drafts ready -> stay Candidates, note.
- AC-5, EV-9: PR branches ready in the fork -> In Progress, note.
- AG-2, AG-3, AG-4, AG-pr-readiness, AG-B1: shipped under skills/ (merged to main) -> Done.
- AM-5 overtaken (upstream has pyproject, uv.lock and prek since 0.17.x) -> Done / Wont Do.
"""

from lib import append_to_body_idempotent, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
MARK = "## Reconcile 2026-10-17"

data = load_items()
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]


def status(card_id: str, value: str) -> None:
    card = find_item(data, card_id)
    set_field(
        PROJECT_ID, card["item_id"], field_ids["Status"], option_ids["Status"][value]
    )
    card["Status"] = value
    print(f"{card_id} -> {value}")


def note(card_id: str, text: str) -> None:
    card = find_item(data, card_id)
    changed, body = append_to_body_idempotent(
        card["draft_id"], MARK, f"\n\n{MARK}\n{text}"
    )
    card["body"] = body
    print(f"  {card_id}: body {'appended' if changed else 'unchanged'}")


note(
    "U-1",
    "Audit against v0.18.6: still present (optimization.py:7079, the hours zeroing when the timesteps list is "
    "passed), already filed upstream as issue #1106 (open, no fix PR). The card's proposed `== 0` inversion is a "
    "no-op; the actual fix is a three-line removal. flexd no longer sends operating_timesteps and is not affected. "
    "Not a generic bug: it is the deferrable-window contract. Plan: comment on #1106 with the analysis and hand "
    "the PR to a contributor. Parked in Ideas until the comment is posted.",
)
status("U-1", "Ideas")

note(
    "U-4",
    "Audit against v0.18.6 (utils.py:106): still present in letter, premise weak (one production call site, "
    "handler removed on normal exit). Not on the LLM-ready, EV or battery path. Closed as won't-do.",
)
status("U-4", "Done / Wont Do")
note(
    "U-5",
    "Audit against v0.18.6: superseded by PR #729 (RetrieveHass.close, persistent session). Residual is CLI "
    "exit hygiene only. Closed as won't-do.",
)
status("U-5", "Done / Wont Do")
note(
    "U-7",
    "Audit against v0.18.6 (optimization.py:8212): still present, but the card's fix does not work with pytz; "
    "backtest mode only, two days a year. Closed as won't-do; note for a future DST theme.",
)
status("U-7", "Done / Wont Do")
note(
    "U-8",
    "Audit against v0.18.6: superseded by PR #1227 (fixes #1225) for the card's example; the window sentinel is "
    "now documented. Closed.",
)
status("U-8", "Done / Wont Do")

note(
    "AC-2",
    "AC-2a shipped as PR #850 (unit field), AC-2b shipped as PR #915 (runtime_params.json as a sibling file "
    "instead of a Runtime category). Umbrella closed; AC-2c continues as its own card.",
)
status("AC-2", "Done / Wont Do")
note(
    "AC-2c",
    "Audit against v0.18.6: not covered. 15 custom_*_id keys plus publish_prefix and entity_save exist only in "
    "code and prose; continual_publish is already a config key. Issue-first draft with three options ready "
    "(.tmp/issue-draft-AC-2c.md), posting pending.",
)
note(
    "AM-1b",
    "Audit against v0.18.6: /action/{action_name} body is still additionalProperties: true, generator reads "
    "only param_definitions.json; passing_data.md:186 names the gap. Issue-first draft with three options ready "
    "(.tmp/issue-draft-AM-1b.md), posting pending.",
)

note(
    "AC-5",
    "Branch docs/ac-5-llms-full-manifest in the fork (794df0b4, off upstream/master at v0.18.6): "
    "sphinx-llms-txt already emits llms-full.txt, so the branch curates llms.txt's summary and inlines AGENTS.md, "
    "param_definitions.json, runtime_params.json and openapi.json into llms-full.txt. Docs build clean against the "
    "22-warning baseline. PR body ready; opening pending (after EV-9 lands, one PR at a time).",
)
status("AC-5", "In Progress")
note(
    "EV-9",
    "Branch docs/ev-9-nodered-mqtt-evcc-recipe in the fork (0a74c9d9, f3bb61f9): cookbook recipe "
    "ev_evcc_nodered_mqtt.md (286 lines) plus index entry, EV as deferrable with def_current_state from evcc, "
    "MQTT setpoints, evcc REST mode/mincurrent, fail-safes, SOC staleness. Built clean. PR body ready; opening pending.",
)
status("EV-9", "In Progress")

for card_id, text in (
    (
        "AG-2",
        "Shipped: skills/emhass-config-validate (stdlib validator against param_definitions.json, "
        "runtime_params.json, config_defaults.json; pytest fixtures), merged to main 2026-10-17.",
    ),
    (
        "AG-3",
        "Shipped: skills/emhass-plan-explain (explain_plan.py over /api/v1/plan and /api/v1/last-run), merged "
        "to main 2026-10-17.",
    ),
    (
        "AG-4",
        "Shipped: skills/emhass-anomaly (scan_logs.py classifying v0.18.6 log signatures), merged to main "
        "2026-10-17.",
    ),
    (
        "AG-pr-readiness",
        "Shipped: skills/emhass-pr-readiness (checklist SKILL.md plus pr_readiness.sh for a fork "
        "checkout), merged to main 2026-10-17.",
    ),
    (
        "AG-B1",
        "Shipped: plugin manifest and install guide under skills/ (107 pytest cases, both manifests validate). "
        "AG-1 troubleshoot stays private; the four public skills are the distribution. Marketplace listing "
        "is a later step.",
    ),
):
    note(card_id, text)
    status(card_id, "Done / Wont Do")

note(
    "AM-5",
    "Overtaken upstream: pyproject.toml, uv lock and prek hooks are in place since 0.17.x. Closed as won't-do.",
)
status("AM-5", "Done / Wont Do")

note(
    "EPIC-LLM",
    "2026-10-17: AC-2 umbrella closed (#850, #915), AG-2/3/4/pr-readiness/B1 shipped under skills/, AC-5 "
    "branch ready, AC-2c and AM-1b issue drafts ready. Remaining: AC-2c, AM-1b (issue-first), AC-5 PR, AM-7 "
    "(offered to HFZR2005), REL-2 (gated).",
)

save_items(data)
print("items.json saved")
