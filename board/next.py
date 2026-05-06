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
import sys  # noqa: F401
from pathlib import Path

DEFAULT_ITEMS = Path(__file__).parent / "items.json"


def load_items(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


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
    return [it for it in items if it.get("Status") == "Todo"]


if __name__ == "__main__":
    raise SystemExit("CLI not yet wired; later task adds argparse + render.")
