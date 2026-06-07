"""Board bookkeeping: PRs #921 + #925 merged upstream 2026-06-06.

#921 (Case A): AM-1 draft umbrella (openapi.json) -> Done; add PR-921 link card.
#925 (Case B): no umbrella (HTTP 200 fix on the JSON API endpoints) -> add PR-925 link card.

#933/#934/#938 already moved to Done by David (synced via fetch.py in the prior commit).
"""

from lib import add_content_to_project, find_item, load_items, save_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
DONE = "Done / Wont Do"

# Case A: AM-1 umbrella + PR-921 sibling (fields mirror AM-1)
PR921_NODE = "PR_kwDOGC8VbM7hb-Ci"
PR921_URL = "https://github.com/davidusb-geek/emhass/pull/921"
PR921_TITLE = "feat: add openapi.json + auto-generation and drift check"
PR921_FIELDS = {
    "Status": DONE,
    "Category": "Infra",
    "Phase": "Phase 3",
    "Priority": "P1",
    "Effort": "S",
    "Scope": "Upstream",
}

# Case B: PR-925 standalone (HTTP 200 fix, JSON API)
PR925_NODE = "PR_kwDOGC8VbM7hkrn2"
PR925_URL = "https://github.com/davidusb-geek/emhass/pull/925"
PR925_TITLE = "fix: return HTTP 200 (not 201) from JSON API endpoints"
PR925_FIELDS = {
    "Status": DONE,
    "Category": "A: Code-Lifecycle",
    "Phase": "Phase 3",
    "Priority": "P1",
    "Effort": "XS",
    "Scope": "Upstream",
}


def add_link(
    data, field_ids, option_ids, pr_id, node, url, title, number, fields, anchor
):
    if pr_id in {i["id"] for i in data["items"]}:
        print(f"{pr_id}: already carded — skip add")
        return
    item_id = add_content_to_project(PROJECT_ID, node)
    for k, v in fields.items():
        set_field(PROJECT_ID, item_id, field_ids[k], option_ids[k][v])
    idx = next(i for i, it in enumerate(data["items"]) if it["id"] == anchor)
    data["items"].insert(
        idx + 1,
        {
            "id": pr_id,
            "title": title,
            "type": "link",
            "content_id": node,
            **fields,
            "item_id": item_id,
            "content_url": url,
            "repository": "davidusb-geek/emhass",
            "number": number,
        },
    )
    print(f"{pr_id}: added (item={item_id}) -> {fields['Status']}")


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    # Case A: AM-1 umbrella -> Done
    am1 = find_item(data, "AM-1")
    if am1["Status"] != DONE:
        set_field(
            PROJECT_ID, am1["item_id"], field_ids["Status"], option_ids["Status"][DONE]
        )
        am1["Status"] = DONE
        print(f"AM-1: Review -> {DONE}")
    else:
        print("AM-1: already Done — skip")

    add_link(
        data,
        field_ids,
        option_ids,
        "PR-921",
        PR921_NODE,
        PR921_URL,
        PR921_TITLE,
        921,
        PR921_FIELDS,
        anchor="AM-1",
    )
    add_link(
        data,
        field_ids,
        option_ids,
        "PR-925",
        PR925_NODE,
        PR925_URL,
        PR925_TITLE,
        925,
        PR925_FIELDS,
        anchor="PR-921" if "PR-921" in {i["id"] for i in data["items"]} else "AM-1",
    )

    save_items(data)
    print("=== Done ===")


if __name__ == "__main__":
    main()
