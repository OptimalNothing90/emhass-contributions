"""Shared helpers for board mutation scripts.

Centralises gh-graphql wrapper, items.json IO, idempotent body-append,
and field setter. Bookkeeping scripts should import from here instead of
hardcoding draft/item IDs and re-implementing the gh wrapper.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ITEMS_FILE = Path(__file__).parent / "items.json"


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


_force_utf8_stdout()


def gh(args: list[str], *, stdin: str | None = None) -> str:
    r = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        input=stdin,
    )
    if r.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {r.stderr}")
    return r.stdout


def gh_graphql(query: str, *, variables: dict[str, str] | None = None) -> dict:
    args = ["api", "graphql", "-f", f"query={query}"]
    for k, v in (variables or {}).items():
        args.extend(["-f", f"{k}={v}"])
    out = gh(args)
    parsed = json.loads(out)
    if "errors" in parsed:
        raise RuntimeError(f"graphql errors: {parsed['errors']}")
    return parsed


def load_items(path: Path = ITEMS_FILE) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_items(data: dict, path: Path = ITEMS_FILE) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def find_item(data: dict, item_id: str) -> dict:
    for it in data["items"]:
        if it["id"] == item_id:
            return it
    raise KeyError(f"items.json has no entry with id={item_id!r}")


def fetch_live_draft(draft_id: str) -> dict:
    q = f'{{ node(id: "{draft_id}") {{ ... on DraftIssue {{ id title body }} }} }}'
    return gh_graphql(q)["data"]["node"]


def update_draft_body(draft_id: str, body: str) -> str:
    q = """mutation($body: String!, $id: ID!) {
      updateProjectV2DraftIssue(input: { draftIssueId: $id, body: $body }) {
        draftIssue { id title }
      }
    }"""
    out = gh_graphql(q, variables={"body": body, "id": draft_id})
    return out["data"]["updateProjectV2DraftIssue"]["draftIssue"]["title"]


def append_to_body_idempotent(
    draft_id: str, marker: str, suffix: str
) -> tuple[bool, str]:
    """Append `suffix` to live draft body iff `marker` not already present.

    Reads live state first (avoids overwriting external edits), then writes.
    Returns (changed, final_body). `changed=False` means marker was already
    present; body untouched on remote.
    """
    live = fetch_live_draft(draft_id)
    body = live.get("body") or ""
    if marker in body:
        return False, body
    new_body = body.rstrip() + suffix
    update_draft_body(draft_id, new_body)
    return True, new_body


def set_field(project_id: str, item_id: str, field_id: str, option_id: str) -> None:
    q = f"""mutation {{
      updateProjectV2ItemFieldValue(input: {{
        projectId: "{project_id}"
        itemId: "{item_id}"
        fieldId: "{field_id}"
        value: {{ singleSelectOptionId: "{option_id}" }}
      }}) {{ projectV2Item {{ id }} }}
    }}"""
    gh_graphql(q)


def add_content_to_project(project_id: str, content_node_id: str) -> str:
    q = f"""mutation {{
      addProjectV2ItemById(input: {{
        projectId: "{project_id}"
        contentId: "{content_node_id}"
      }}) {{ item {{ id }} }}
    }}"""
    out = gh_graphql(q)
    return out["data"]["addProjectV2ItemById"]["item"]["id"]


def add_draft_to_project(project_id: str, title: str, body: str) -> tuple[str, str]:
    """Returns (project_item_id, draft_issue_id)."""
    q = """mutation($pid: ID!, $title: String!, $body: String!) {
      addProjectV2DraftIssue(input: { projectId: $pid, title: $title, body: $body }) {
        projectItem { id content { ... on DraftIssue { id } } }
      }
    }"""
    out = gh_graphql(q, variables={"pid": project_id, "title": title, "body": body})
    pi = out["data"]["addProjectV2DraftIssue"]["projectItem"]
    return pi["id"], pi["content"]["id"]
