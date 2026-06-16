"""AM-2 -> Done / Wont Do (2026-06-17).

Cut after a brainstorm value-check, confirmed by Claude + Codex cross-model review
(both verdict: KILL). AM-2 was "auto-generate config.md from param_definitions.json".
Rationale appended to the card body (idempotent).
"""

from lib import append_to_body_idempotent, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
DONE = "Done / Wont Do"

MARKER = "Won't Do (2026-06-17)"
RATIONALE = """

## Won't Do (2026-06-17)
Cut after a brainstorm value-check (Claude + Codex cross-review, both KILL).
param_definitions.json is already the machine-readable SoT; openapi.json (#921) +
runtime_params.json (#915) deliver the machine/LLM-ready surface, drift-guarded. A
generated facts table in config.md would be another human-facing surface that guards
nothing: machines read the JSON, humans read the prose (whose inline defaults stay
hand-maintained and would still drift). The only valuable version -- migrating the rich
prose descriptions/notes into param_definitions and fully generating config.md -- is
L/XL, touches the maintainer SoT, and has weak marginal payoff since config.md is
maintained fine by hand. Revisit only if config.md <-> param_def drift becomes recurring."""


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    item = find_item(data, "AM-2")
    if item["Status"] != DONE:
        set_field(
            PROJECT_ID, item["item_id"], field_ids["Status"], option_ids["Status"][DONE]
        )
        item["Status"] = DONE
        print(f"AM-2: {item.get('Status')} -> {DONE}")
    else:
        print("AM-2: already Done — skip status")

    changed, _ = append_to_body_idempotent(item["draft_id"], MARKER, RATIONALE)
    if changed:
        # mirror into items.json body so fetch --dry-run shows 0 drift
        live_body = (item.get("body") or "").rstrip() + RATIONALE
        item["body"] = live_body
        print("AM-2: rationale appended to body")
    else:
        print("AM-2: rationale already present — skip body")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
