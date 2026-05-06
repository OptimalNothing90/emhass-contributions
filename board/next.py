"""Pick next emhass board items for upstream PR work.

Reads board/items.json (or a passed path), applies filters per design
spec §8, and emits two ranked candidate lists (Quick-Win + Strategic).

Pure stdlib. No GitHub API calls. No side effects beyond writing to
stdout. Skill wrappers (emhass-next-item-picker, emhass-cross-repo-flow)
are responsible for conversational presentation and live-API behavior.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_ITEMS = Path(__file__).parent / "items.json"

BLOCKED_RE = re.compile(r"^\s*Blocked-by:\s*([A-Za-z0-9_-]+)", re.MULTILINE)
LINKED_RE = re.compile(r"linked\s+#(\d+)", re.IGNORECASE)
EMPTY_PLACEHOLDER = "_(no items match these criteria)_"


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


def why_quick(item: dict) -> str:
    body = item.get("body") or ""
    m = LINKED_RE.search(body)
    effort = item.get("Effort", "")
    if m:
        return f"linked #{m.group(1)}, {effort} effort"
    g = goal_fit(item)
    if g:
        return f"{g}, {effort} effort"
    return f"{effort} effort, {item.get('Phase', '')}"


def why_strategic(item: dict) -> str:
    g = goal_fit(item)
    phase = item.get("Phase", "")
    if g:
        return f"goal-fit: {g}, {phase}"
    return f"{phase} / {item.get('Priority', '')}"


def _row(item: dict, why: str) -> str:
    return (
        f"| {item.get('id', '')} | {goal_fit(item)} | {item.get('title', '')} | "
        f"{item.get('Phase', '')} | {item.get('Priority', '')} | "
        f"{item.get('Effort', '')} | {why} |"
    )


def render_markdown(
    quickwins: list[dict],
    strategics: list[dict],
    *,
    today: str,
) -> str:
    parts = [f"# Next emhass items — {today}", ""]

    parts.append("## Quick wins (Effort XS/S, Todo, no block)")
    parts.append("")
    parts.append("| ID | Goal-fit | Title | Phase | Pri | Effort | Why quick |")
    parts.append("|----|----------|-------|-------|-----|--------|-----------|")
    if quickwins:
        for it in quickwins:
            parts.append(_row(it, why_quick(it)))
    else:
        parts.append(EMPTY_PLACEHOLDER)
    parts.append("")

    parts.append("## Strategic next (P0/P1, lowest Phase)")
    parts.append("")
    parts.append("| ID | Goal-fit | Title | Phase | Pri | Effort | Why strategic |")
    parts.append("|----|----------|-------|-------|-----|--------|---------------|")
    if strategics:
        for it in strategics:
            parts.append(_row(it, why_strategic(it)))
    else:
        parts.append(EMPTY_PLACEHOLDER)

    return "\n".join(parts)


def _json_entry(item: dict, why: str) -> dict:
    return {
        "id": item.get("id", ""),
        "title": item.get("title", ""),
        "phase": item.get("Phase", ""),
        "priority": item.get("Priority", ""),
        "effort": item.get("Effort", ""),
        "scope": item.get("Scope", ""),
        "goal_fit": goal_fit(item),
        "why": why,
    }


def render_json(
    quickwins: list[dict],
    strategics: list[dict],
    *,
    today: str,
) -> str:
    payload = {
        "date": today,
        "quickwins": [_json_entry(it, why_quick(it)) for it in quickwins],
        "strategics": [_json_entry(it, why_strategic(it)) for it in strategics],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    import datetime as _dt

    p = argparse.ArgumentParser(
        prog="board/next.py",
        description="Pick next emhass board items (Quick-Win + Strategic).",
    )
    p.add_argument("--mode", choices=("quickwin", "strategic", "both"), default="both")
    p.add_argument("--include-bugs", action="store_true")
    p.add_argument("--scope", choices=("upstream", "local", "both"), default="upstream")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--format", choices=("md", "json"), default="md")
    p.add_argument(
        "--items",
        type=Path,
        default=DEFAULT_ITEMS,
        help="Path to items.json (default: board/items.json)",
    )
    p.add_argument(
        "--today",
        default=None,
        help="Override date string (YYYY-MM-DD); default: today.",
    )
    args = p.parse_args(argv)

    today = args.today or _dt.date.today().isoformat()
    data = load_items(args.items)
    items = data["items"]
    cands = filter_candidates(
        items,
        scope=args.scope,
        include_bugs=args.include_bugs,
    )

    qw = rank_quickwin(cands)[: args.limit] if args.mode in ("quickwin", "both") else []
    st = (
        rank_strategic(cands)[: args.limit]
        if args.mode in ("strategic", "both")
        else []
    )

    # Edge case: everything in flight (no Todo items at all matched filters)
    if args.format == "md" and not qw and not st:
        msg = (
            f"# Next emhass items — {today}\n\n"
            "_Picker empty — everything in flight, wait for merges._\n"
        )
        sys.stdout.write(msg)
        return 0

    if args.format == "json":
        sys.stdout.write(render_json(qw, st, today=today) + "\n")
    else:
        sys.stdout.write(render_markdown(qw, st, today=today) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
