"""Card two merged PRs (2026-06-07), strategically relevant, were not previously tracked.

#928 (LesIT1): intermediate battery SoC target (soc_target) — EPIC-REL battery pillar +
operator runs a battery. Phase 2 (battery/SoC cluster), Category A.
#948 (BrettLynch123): per-deferrable command-state sensors (intent labels + schedule attr)
— overlaps the #931 shared-plan-registry / executor concept. Phase 4 (EVCC Integration),
Category B.

Both MERGED → Status Done / Wont Do. Create-only: fetch.py ingests; keys as PR-<n>.
"""

from lib import add_content_to_project, load_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
DONE = "Done / Wont Do"

TARGETS = [
    (
        "PR-928",
        "PR_kwDOGC8VbM7hoELc",
        {
            "Status": DONE,
            "Category": "A: Code-Lifecycle",
            "Phase": "Phase 2",
            "Priority": "P1",
            "Effort": "M",
            "Scope": "Upstream",
        },
    ),
    (
        "PR-948",
        "PR_kwDOGC8VbM7jivLO",
        {
            "Status": DONE,
            "Category": "B: End-User-Ops",
            "Phase": "Phase 4",
            "Priority": "P1",
            "Effort": "M",
            "Scope": "Upstream",
        },
    ),
]


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]
    existing = {i["id"] for i in data["items"]}

    for pr_id, node, fields in TARGETS:
        if pr_id in existing:
            print(f"{pr_id}: already carded — skip")
            continue
        item_id = add_content_to_project(PROJECT_ID, node)
        for k, v in fields.items():
            set_field(PROJECT_ID, item_id, field_ids[k], option_ids[k][v])
        print(f"{pr_id}: added (item={item_id}) -> {fields}")

    print("=== Done — run fetch.py to ingest ===")


if __name__ == "__main__":
    main()
