"""Bookkeeping 2026-06-16:
- AM-1c (openapi auto-regen) SHIPPED: PR #951 merged 2026-06-08. AM-1c draft -> Done;
  add PR-951 link card (Done). Case A (draft umbrella + PR sibling).
- #936 (set_nodischarge_to_grid over-constraint, our Cause-4) now has a fix in flight:
  PR #981 (LesIT1), OPEN. Add PR-981 link card (Review). ISSUE-936 stays Candidates until
  #981 merges (then it auto-closes -> future bookkeeping).
"""

from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
DONE = "Done / Wont Do"

PR951_NODE = "PR_kwDOGC8VbM7jsYwy"
PR951_FIELDS = {
    "Status": DONE,
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P1",
    "Effort": "S",
    "Scope": "Upstream",
}

PR981_NODE = "PR_kwDOGC8VbM7mQXJb"
PR981_FIELDS = {
    "Status": "Review",
    "Category": "A: Code-Lifecycle",
    "Phase": "Phase 2",
    "Priority": "P1",
    "Effort": "S",
    "Scope": "Upstream",
}


def add_link(data, field_ids, option_ids, pr_id, node, fields):
    if pr_id in {i["id"] for i in data["items"]}:
        print(f"{pr_id}: already carded — skip")
        return
    item_id = add_content_to_project(PROJECT_ID, node)
    for k, v in fields.items():
        set_field(PROJECT_ID, item_id, field_ids[k], option_ids[k][v])
    print(f"{pr_id}: added (item={item_id}) -> {fields['Status']}")


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    # AM-1c draft -> Done (shipped via #951)
    am1c = find_item(data, "AM-1c")
    if am1c["Status"] != DONE:
        set_field(
            PROJECT_ID, am1c["item_id"], field_ids["Status"], option_ids["Status"][DONE]
        )
        am1c["Status"] = DONE
        print(f"AM-1c: {am1c.get('Status')} -> Done (shipped via #951)")
    else:
        print("AM-1c: already Done — skip")

    add_link(data, field_ids, option_ids, "PR-951", PR951_NODE, PR951_FIELDS)
    add_link(data, field_ids, option_ids, "PR-981", PR981_NODE, PR981_FIELDS)

    save_items(data)
    print("=== Done — run fetch.py to ingest link cards ===")


if __name__ == "__main__":
    main()
