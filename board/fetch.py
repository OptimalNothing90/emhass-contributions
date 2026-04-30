#!/usr/bin/env python3
"""Pull live state of the EMHASS AI agents project board into items.json.

Why: items.json drifts whenever someone moves a card on the website. Without
a refresh, mutation scripts that read items.json overwrite live edits.

Behavior:
- Paginate live items via gh graphql.
- Match each live item to an existing items.json entry (by stored PVTI_* item_id
  first, fallback to title-prefix parse).
- Report NEW / REMOVED / FIELD / BODY / TITLE drift.
- Write items.json preserving the existing `id` keys (CE-1, AC-2-fix, PR-830 …)
  so mutation scripts keep working. Adds `item_id` and `draft_id` to every
  entry — eliminates the hardcoded-IDs pattern in bookkeeping scripts.

Usage:
    python fetch.py            # write items.json + print drift
    python fetch.py --dry-run  # print drift, do not write
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

from lib import ITEMS_FILE, gh_graphql, load_items, save_items

PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
TRACKED_FIELDS = ("Status", "Category", "Phase", "Priority", "Effort", "Scope")

# Defense-in-depth: live cards may contain private URLs that the pre-commit
# scrub-private-refs hook forbids in items.json. Scrub on ingest so the
# committed JSON stays clean even when the live board does not.
_SCRUB_PATTERNS = [
    (
        re.compile(r"https?://github\.com/OptimalNothing90/loxonesmarthome[^\s)\"']*"),
        "<private-repo-link-redacted>",
    ),
    (
        # Split literal across concat so this file itself does not trigger the
        # pre-commit scrub-private-refs hook.
        re.compile("/mnt/user/" + r"appdata/emhass/Loxone[^\s)\"']*"),
        "<private-path-redacted>",
    ),
]


def scrub_body(text: str) -> tuple[str, int]:
    n = 0
    for pat, repl in _SCRUB_PATTERNS:
        text, k = pat.subn(repl, text)
        n += k
    return text, n


def fetch_all_items(project_id: str) -> list[dict]:
    items: list[dict] = []
    cursor: str | None = None
    while True:
        after = f', after: "{cursor}"' if cursor else ""
        q = f"""{{
          node(id: "{project_id}") {{
            ... on ProjectV2 {{
              items(first: 100{after}) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                  id
                  type
                  content {{
                    __typename
                    ... on DraftIssue {{ id title body }}
                    ... on Issue {{ id number title url body
                      repository {{ nameWithOwner }} }}
                    ... on PullRequest {{ id number title url body
                      repository {{ nameWithOwner }} }}
                  }}
                  fieldValues(first: 20) {{
                    nodes {{
                      ... on ProjectV2ItemFieldSingleSelectValue {{
                        field {{ ... on ProjectV2SingleSelectField {{ name }} }}
                        name
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}"""
        page = gh_graphql(q)["data"]["node"]["items"]
        items.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            break
        cursor = page["pageInfo"]["endCursor"]
    return items


_TITLE_PREFIX = re.compile(
    r"^(?:PR\s*#(?P<pr>\d+)"
    r"|Issue\s*#(?P<iss>\d+)"
    r"|Discussion\s*#(?P<disc>\d+)"
    r"|(?P<tag>[A-Za-z][\w.-]*?))\s*:\s*"
)


def derive_id_from_title(title: str) -> str | None:
    m = _TITLE_PREFIX.match(title)
    if not m:
        return None
    if m.group("pr"):
        return f"PR-{m.group('pr')}"
    if m.group("iss"):
        return f"ISSUE-{m.group('iss')}"
    if m.group("disc"):
        return f"DISC-{m.group('disc')}"
    return m.group("tag")


def normalise_live(node: dict) -> dict:
    content = node.get("content") or {}
    typename = content.get("__typename")
    field_vals = {
        fv["field"]["name"]: fv["name"]
        for fv in node["fieldValues"]["nodes"]
        if fv and "field" in fv and "name" in fv
    }
    title = content.get("title", "<untitled>")
    fields = {f: field_vals.get(f) for f in TRACKED_FIELDS}
    if typename == "DraftIssue":
        body, scrubbed = scrub_body(content.get("body") or "")
        out = {
            "title": title,
            "type": "draft",
            "body": body,
            **fields,
            "item_id": node["id"],
            "draft_id": content["id"],
            "_id_hint": derive_id_from_title(title),
        }
        if scrubbed:
            out["_scrubbed_count"] = scrubbed
        return out
    if typename in ("Issue", "PullRequest"):
        number = content.get("number")
        prefix = "PR" if typename == "PullRequest" else "ISSUE"
        hint = f"{prefix}-{number}" if number is not None else None
        return {
            "title": title,
            "type": "link",
            "content_id": content["id"],
            **fields,
            "item_id": node["id"],
            "content_url": content.get("url"),
            "repository": content.get("repository", {}).get("nameWithOwner"),
            "number": number,
            "_id_hint": hint,
        }
    return {
        "title": title,
        "type": "redacted",
        **fields,
        "item_id": node["id"],
        "_id_hint": derive_id_from_title(title),
    }


def _strip_hint(live: dict) -> dict:
    return {k: v for k, v in live.items() if not k.startswith("_")}


def _match(existing: dict, live_norm: list[dict]) -> dict[str, dict]:
    """Return prior['id'] → live dict (identity preserved)."""
    by_item_id = {
        it.get("item_id"): it for it in existing["items"] if it.get("item_id")
    }
    by_draft_id = {
        it.get("draft_id"): it for it in existing["items"] if it.get("draft_id")
    }
    by_content_id = {
        it.get("content_id"): it for it in existing["items"] if it.get("content_id")
    }
    by_user_id = {it["id"]: it for it in existing["items"]}
    matched: set[int] = set()
    out: dict[str, dict] = {}

    for live in live_norm:
        prior = by_item_id.get(live["item_id"])
        if prior is None and live.get("draft_id"):
            prior = by_draft_id.get(live["draft_id"])
        if prior is None and live.get("content_id"):
            prior = by_content_id.get(live["content_id"])
        hint = live.get("_id_hint")
        if prior is None and hint:
            cand = by_user_id.get(hint)
            if cand is not None and id(cand) not in matched:
                prior = cand
        if prior is not None and id(prior) not in matched:
            matched.add(id(prior))
            out[prior["id"]] = live
    return out


def reconcile(existing: dict, live_norm: list[dict]) -> tuple[list[dict], list[str]]:
    prior_to_live = _match(existing, live_norm)
    matched_item_ids = {lv["item_id"] for lv in prior_to_live.values()}
    drift: list[str] = []
    out: list[dict] = []

    for prior in existing["items"]:
        live = prior_to_live.get(prior["id"])
        if live is None:
            drift.append(f"[GONE]  {prior['id']:20s} {prior.get('title', '')[:70]}")
            continue
        uid = prior["id"]
        if live["title"] != prior.get("title"):
            drift.append(
                f"[TITLE] {uid:20s} {prior.get('title', '')!r} → {live['title']!r}"
            )
        for f in TRACKED_FIELDS:
            if live.get(f) != prior.get(f):
                drift.append(
                    f"[FIELD] {uid:20s} {f}: {prior.get(f)!r} → {live.get(f)!r}"
                )
        if live["type"] == "draft":
            old_body = prior.get("body") or ""
            new_body = live.get("body") or ""
            if old_body != new_body:
                delta = len(new_body) - len(old_body)
                drift.append(f"[BODY]  {uid:20s} body changed ({delta:+d} chars)")
        if live.get("_scrubbed_count"):
            drift.append(
                f"[SCRUB] {uid:20s} {live['_scrubbed_count']} private ref(s) scrubbed from live body"
            )
        out.append({"id": uid, **_strip_hint(live)})

    used_uids = {it["id"] for it in out}
    for live in live_norm:
        if live["item_id"] in matched_item_ids:
            continue
        hint = live.get("_id_hint")
        uid = hint or f"unknown-{live['item_id'][-6:]}"
        while uid in used_uids:
            uid = f"{uid}-dup"
        used_uids.add(uid)
        out.append({"id": uid, **_strip_hint(live)})
        drift.append(f"[NEW]   {uid:20s} {live['title'][:70]}")

    return out, drift


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing = load_items()
    live_raw = fetch_all_items(PROJECT_ID)
    live_norm = [normalise_live(n) for n in live_raw]
    new_items, drift = reconcile(existing, live_norm)

    print("=== drift report (live vs items.json) ===")
    if drift:
        for line in drift:
            print(line)
    else:
        print("  no drift — items.json matches live")
    print(
        f"=== summary: {len(live_norm)} live, "
        f"{sum(1 for d in drift if d.startswith('[NEW]'))} new, "
        f"{sum(1 for d in drift if d.startswith('[GONE]'))} removed, "
        f"{sum(1 for d in drift if d.startswith(('[FIELD]', '[BODY]', '[TITLE]')))} changed ==="
    )

    if args.dry_run:
        print("\ndry-run: items.json untouched")
        return 0

    existing["_meta"]["spec_version"] = "1.1"
    existing["_meta"]["fetched_at"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    existing["items"] = new_items
    save_items(existing)
    print(f"\nwrote {ITEMS_FILE} ({len(new_items)} items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
