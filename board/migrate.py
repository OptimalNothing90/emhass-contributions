#!/usr/bin/env python3
"""
Bulk-migrate EMHASS Meisterplan items into the GitHub Project v2 board.
Reads `2026-04-28-emhass-board-migration-items.json` and runs gh graphql mutations.

Usage:
    python migrate-emhass-board.py [--dry-run] [--start N]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

# Force UTF-8 stdout on Windows
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DATA_FILE = Path(__file__).parent / "2026-04-28-emhass-board-migration-items.json"
DRY_RUN = "--dry-run" in sys.argv
START_FROM = 1
if "--start" in sys.argv:
    START_FROM = int(sys.argv[sys.argv.index("--start") + 1])


def gh_graphql(query: str) -> dict:
    """Run gh api graphql, return parsed JSON."""
    if DRY_RUN:
        print(f"[dry-run] would run query (len={len(query)})")
        return {"data": {"_dry_run": True}}
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={query}"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh failed: {result.stderr}")
    out = json.loads(result.stdout)
    if "errors" in out:
        raise RuntimeError(f"graphql errors: {out['errors']}")
    return out


def add_draft(project_id: str, title: str, body: str) -> str:
    body_escaped = body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    title_escaped = title.replace("\\", "\\\\").replace('"', '\\"')
    q = f'''mutation {{
      addProjectV2DraftIssue(input: {{
        projectId: "{project_id}"
        title: "{title_escaped}"
        body: "{body_escaped}"
      }}) {{
        projectItem {{ id }}
      }}
    }}'''
    r = gh_graphql(q)
    return r["data"]["addProjectV2DraftIssue"]["projectItem"]["id"] if not DRY_RUN else "ITEM_ID_DRY"


def add_link(project_id: str, content_id: str) -> str:
    q = f'''mutation {{
      addProjectV2ItemById(input: {{
        projectId: "{project_id}"
        contentId: "{content_id}"
      }}) {{
        item {{ id }}
      }}
    }}'''
    r = gh_graphql(q)
    return r["data"]["addProjectV2ItemById"]["item"]["id"] if not DRY_RUN else "ITEM_ID_DRY"


def set_field(project_id: str, item_id: str, field_id: str, option_id: str) -> None:
    q = f'''mutation {{
      updateProjectV2ItemFieldValue(input: {{
        projectId: "{project_id}"
        itemId: "{item_id}"
        fieldId: "{field_id}"
        value: {{ singleSelectOptionId: "{option_id}" }}
      }}) {{
        projectV2Item {{ id }}
      }}
    }}'''
    gh_graphql(q)


def main():
    with DATA_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    meta = data["_meta"]
    project_id = meta["project_id"]
    field_ids = meta["field_ids"]
    option_ids = meta["option_ids"]
    items = data["items"]

    print(f"Migrating {len(items)} items to project {project_id}")
    print(f"Mode: {'DRY-RUN' if DRY_RUN else 'LIVE'}\n")

    failures = []
    for idx, item in enumerate(items, 1):
        if idx < START_FROM:
            continue
        prefix = f"[{idx}/{len(items)}] {item['id']}"
        try:
            if item["type"] == "draft":
                item_id = add_draft(project_id, item["title"], item.get("body", ""))
            elif item["type"] == "link":
                item_id = add_link(project_id, item["content_id"])
            else:
                raise ValueError(f"unknown type: {item['type']}")

            for field_name in ("Status", "Category", "Phase", "Priority", "Effort", "Scope"):
                if field_name in item:
                    set_field(
                        project_id,
                        item_id,
                        field_ids[field_name],
                        option_ids[field_name][item[field_name]],
                    )
            print(f"{prefix} [OK] {item['title'][:70]}")
        except Exception as e:
            print(f"{prefix} [FAIL] {e}")
            failures.append((item["id"], str(e)))
        time.sleep(0.1)  # gentle pacing

    print(f"\nDone. {len(items) - len(failures)}/{len(items)} succeeded.")
    if failures:
        print("\nFailures:")
        for fid, msg in failures:
            print(f"  - {fid}: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
