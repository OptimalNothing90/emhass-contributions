"""De-reference the killed AM-2 from dependent board card bodies (EPIC-LLM, AG-8).

AM-2 -> Wont Do (2026-06-17). EPIC-LLM listed it as a member and AG-8's body referenced
it as feeding config.md docs. Remove those dangling references (Codex stop-gate catch).
"""

import re

from lib import fetch_live_draft, find_item, load_items, save_items, update_draft_body

EDITS = {
    "EPIC-LLM": [
        (r"AM-2 \(config\.md docs\),\s*", ""),
        (r"config\.md auto-generated\s*\+\s*", ""),
    ],
    "AG-8": [
        (
            r"feeds AM-2 \(config\.md docs\) and the",
            "feeds the openapi generator and the",
        ),
        (
            r"Depends on AC-2b \(runtime params in schema\),\s*AM-2, and",
            "Depends on AC-2b (runtime params in schema) and",
        ),
    ],
}


def main() -> None:
    data = load_items()
    for board_id, subs in EDITS.items():
        item = find_item(data, board_id)
        live = fetch_live_draft(item["draft_id"])
        body = live.get("body") or ""
        new = body
        for pat, repl in subs:
            new = re.sub(pat, repl, new)
        if new == body:
            print(f"{board_id}: no change (already de-referenced?)")
            continue
        if "AM-2" in new:
            print(f"WARN {board_id}: 'AM-2' still present after edit — inspect")
        update_draft_body(item["draft_id"], new)
        item["body"] = new
        print(f"{board_id}: de-referenced AM-2 ({len(body)} -> {len(new)} chars)")
    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
