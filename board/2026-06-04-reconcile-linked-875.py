"""Reconcile adds (2026-06-04): add the #875 regression-cluster PRs/issues as linked
project content + set triage fields. Per spec §B3.

#933/#934/#938 are PRs; #935/#936 are issues. addProjectV2ItemById is idempotent per
(project, content) so re-running is safe. items.json catches up on next fetch.py;
fetch keys these as PR-<n> / ISSUE-<n> automatically.
"""

from lib import add_content_to_project, gh, load_items, set_field

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
REPO = "davidusb-geek/emhass"

# number, kind ('pr'|'issue'), board status
TARGETS = [
    (933, "pr", "In Progress"),
    (934, "pr", "In Progress"),
    (938, "pr", "In Progress"),
    (935, "issue", "Candidates"),
    (936, "issue", "Candidates"),
]
COMMON = {"Phase": "Phase 2", "Scope": "Upstream"}


def node_id(number: int, kind: str) -> str:
    sub = "pr" if kind == "pr" else "issue"
    out = gh([sub, "view", str(number), "--repo", REPO, "--json", "id", "-q", ".id"])
    return out.strip()


def main() -> None:
    data = load_items()
    field_ids = data["_meta"]["field_ids"]
    option_ids = data["_meta"]["option_ids"]

    for number, kind, status in TARGETS:
        cid = node_id(number, kind)
        item_id = add_content_to_project(PROJECT_ID, cid)
        print(f"#{number} ({kind}): content={cid} item={item_id}")
        fields = {**COMMON, "Status": status}
        for fname, val in fields.items():
            set_field(PROJECT_ID, item_id, field_ids[fname], option_ids[fname][val])
        print(f"  fields: {fields}")

    print("=== Done — run fetch.py to ingest ===")


if __name__ == "__main__":
    main()
