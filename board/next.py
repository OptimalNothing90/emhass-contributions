"""Pick next emhass board items for upstream PR work.

Reads board/items.json (or a passed path), applies filters per design
spec §8, and emits two ranked candidate lists (Quick-Win + Strategic).

Pure stdlib. No GitHub API calls. No side effects beyond writing to
stdout. Skill wrappers (emhass-next-item-picker, emhass-cross-repo-flow)
are responsible for conversational presentation and live-API behavior.
"""

from __future__ import annotations

import argparse  # noqa: F401
import json
import re
import sys  # noqa: F401
from pathlib import Path

DEFAULT_ITEMS = Path(__file__).parent / "items.json"

BLOCKED_RE = re.compile(r"^\s*Blocked-by:\s*([A-Za-z0-9_-]+)", re.MULTILINE)


def load_items(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def _scope_matches(item: dict, scope: str) -> bool:
    if scope == "both":
        return True
    item_scope = (item.get("Scope") or "").lower()
    return item_scope == scope


def _has_sibling_in_review(item: dict, all_items: list[dict]) -> bool:
    return any(
        sib.get("type") == "link"
        and sib.get("linked_to") == item["id"]
        and sib.get("Status") == "Review"
        for sib in all_items
    )


def _is_blocked(item: dict, all_items: list[dict]) -> bool:
    body = item.get("body") or ""
    m = BLOCKED_RE.search(body)
    if not m:
        return False
    blocker_id = m.group(1)
    blocker = next((b for b in all_items if b.get("id") == blocker_id), None)
    if blocker is None:
        return False
    return blocker.get("Status") != "Done / Wont Do"


def _has_bug_label(item: dict) -> bool:
    return "bug" in (item.get("labels") or [])


def filter_candidates(
    items: list[dict],
    *,
    scope: str = "upstream",
    include_bugs: bool = False,
) -> list[dict]:
    """Apply all filter rules from spec §8.

    Returns items where: Status=Todo, Scope matches, no sibling PR in
    Review, no unresolved Blocked-by marker, no bug label (unless flag).
    """
    out = []
    for it in items:
        if it.get("Status") != "Todo":
            continue
        if not _scope_matches(it, scope):
            continue
        if _has_sibling_in_review(it, items):
            continue
        if _is_blocked(it, items):
            continue
        if not include_bugs and _has_bug_label(it):
            continue
        out.append(it)
    return out


if __name__ == "__main__":
    raise SystemExit("CLI not yet wired; later task adds argparse + render.")
