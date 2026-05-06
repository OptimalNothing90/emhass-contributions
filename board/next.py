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


PHASE_ORDER = {
    "Phase 0": 0,
    "Phase 1": 1,
    "Phase 1.5": 2,
    "Phase 2": 3,
    "Phase 3": 4,
    "Phase 4": 5,
    "Phase 5": 6,
}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
EFFORT_ORDER = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4}


def _phase_rank(item: dict) -> int:
    return PHASE_ORDER.get(item.get("Phase", ""), 99)


def _priority_rank(item: dict) -> int:
    return PRIORITY_ORDER.get(item.get("Priority", ""), 99)


def _effort_rank(item: dict) -> int:
    return EFFORT_ORDER.get(item.get("Effort", ""), 99)


def rank_quickwin(items: list[dict]) -> list[dict]:
    pre = [it for it in items if it.get("Effort") in ("XS", "S")]
    return sorted(
        pre,
        key=lambda it: (
            _phase_rank(it),
            _priority_rank(it),
            _effort_rank(it),
            it.get("id", ""),
        ),
    )


def rank_strategic(items: list[dict]) -> list[dict]:
    pre = [it for it in items if it.get("Priority") in ("P0", "P1")]
    return sorted(
        pre,
        key=lambda it: (
            _priority_rank(it),
            _phase_rank(it),
            _effort_rank(it),
            it.get("id", ""),
        ),
    )


GOAL_PREFIX_MAP = {
    "AC": "LLM-ready",
    "EV": "EV-EVCC",
}


def goal_fit(item: dict) -> str:
    g = item.get("Goal")
    if g:
        return g
    item_id = item.get("id", "")
    prefix = item_id.split("-", 1)[0] if "-" in item_id else item_id
    return GOAL_PREFIX_MAP.get(prefix, "")


if __name__ == "__main__":
    raise SystemExit("CLI not yet wired; later task adds argparse + render.")
