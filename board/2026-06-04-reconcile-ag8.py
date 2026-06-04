"""Reconcile (2026-06-04): reframe AG-8 from CLI Setup-Wizard to schema-driven web-config.

Per spec §B7. Title prefix stays 'AG-8' so the board id does not re-key. Changes:
title, body, Phase 5->3, Priority P3->P2. Category (B), Scope (Upstream), Effort (L),
Status (Ideas) unchanged.
"""

from lib import find_item, load_items, save_items, set_field, update_draft_title_body

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"

NEW_TITLE = "AG-8: Schema-driven web-config form + validation"
NEW_BODY = """\
Generate the EMHASS config form + client/server validation from
`param_definitions.json` — the same SoT that feeds AM-2 (config.md docs) and the
runtime config-validation work. Replaces the flat config page; one schema drives
docs + validation + UI (LLM-ready: single schema -> many surfaces).

Member of the LLM-ready epic (EPIC-LLM). Depends on AC-2b (runtime params in schema),
AM-2, and the config-validation deliverable. Supersedes the original `emhass init`
CLI-wizard framing (a CLI wizard duplicated the existing web config page).
"""

REFIELD = {"Phase": "Phase 3", "Priority": "P2"}


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    ag8 = find_item(data, "AG-8")
    if ag8["Phase"] != "Phase 5":
        print(f"WARN AG-8 Phase is {ag8['Phase']!r}, expected 'Phase 5' — continuing")

    update_draft_title_body(ag8["draft_id"], NEW_TITLE, NEW_BODY)
    ag8["title"] = NEW_TITLE
    ag8["body"] = NEW_BODY
    print(f"AG-8 retitled -> {NEW_TITLE!r}")

    for fname, val in REFIELD.items():
        set_field(PROJECT_ID, ag8["item_id"], field_ids[fname], option_ids[fname][val])
        ag8[fname] = val
        print(f"  set {fname} = {val}")

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
