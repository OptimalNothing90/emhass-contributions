---
name: emhass-next-item-picker
description: Use when the user wants to identify the next emhass board item to work on. Triggers on phrases like "was kommt als nächstes", "what's next", "what should I work on", "quick wins", "schnelle Sachen", "strategic next", "großes Item next", "show me the board", "zeig was offen ist", or as the chained tail of `emhass-cross-repo-flow` after PR merge bookkeeping. Does NOT fire when the user has already named a concrete item; in that case route to `emhass-cross-repo-flow` directly.
---

# EMHASS Next-Item Picker

Surfaces ranked candidate board items for the next contribution. Wraps `board/next.py`
(deterministic filter + rank, stdlib only, no GitHub API). This skill is the
conversational presentation layer; all selection logic lives in the script and is
covered by `tests/test_board_next.py`.

## Self-test (one-shot, at first use after this skill was authored)

**STATUS: DONE — baseline executed 2026-05-07 against live `board/items.json`.**

Outcome: picker produced ranked Quick-Win + Strategic lists. Two consecutive runs
yielded identical output (idempotent). JSON output parsed cleanly. No bug-label
leakage (live items.json has no `labels` field populated; filter is dormant by
design until fetch.py is extended).

On first use after authoring, run:

```bash
python board/next.py --limit 3
python board/next.py --limit 3 --format json
python board/next.py --limit 3   # second run, must produce identical output (modulo date header)
```

Pass criteria:
- Both Markdown outputs identical except for the `# Next emhass items — YYYY-MM-DD` header line
- JSON output validates as JSON (`python -c "import json,sys; json.load(sys.stdin)"`)
- No bug-labelled link item appears in the default-mode output (verify by reading `board/items.json` for any link item with `labels: ["bug", ...]` — there are none today, so this is a no-op proof; once such an item exists, the proof becomes meaningful)

After STATUS: DONE, this section is audit trail only. Do not re-run.

## When to fire

Fires on:
- "Was kommt als nächstes?" / "what's next" / "what should I work on?"
- "Quick wins?" / "schnelle Sachen?"
- "Strategic next" / "großes Item next"
- "Show me the board" / "zeig was offen ist"
- Halbautomatic chained call from `emhass-cross-repo-flow` end ("pick next item? (j/n)")

Does NOT fire on:
- User already named a concrete item — go straight to `emhass-cross-repo-flow`
- "Liste mir alle bugs" — picker default-filters bugs; user wants the live `gh issue list` instead

## Pre-flight (always, in order)

1. **Working directory** — must be at repo root (`C:/Users/MauricioSchäpers/claude-code/emhass-contributions`). Verify with `git rev-parse --show-toplevel`.
2. **No auth needed** — picker is read-only stdlib, never touches `gh`. Skip `gh auth status`.
3. **items.json freshness check** — optional but recommended once per session: `cd board && python fetch.py --dry-run`. If drift > 0, ask user whether to run `python fetch.py` for real before picking. Stale items.json can hide just-merged items as still `Review`.

## Invocation pattern

Default — show both lists, top 5 each:

```bash
python board/next.py --limit 5
```

User intent shorthand mapping:

| User says | Flags |
|---|---|
| "Quick wins?" | `--mode quickwin --limit 5` |
| "Strategic" / "großes Item" | `--mode strategic --limit 5` |
| "include bugs" / "auch goodwill bugs" | `--include-bugs` (after explicit user opt-in per `feedback_no_auto_bugfix`) |
| "local items auch" | `--scope both` |
| "json please" | `--format json` |

## Goal-fit annotation

The script already tags each row with goal-fit (`LLM-ready`, `EV-EVCC`, or empty). Do NOT
re-annotate or LLM-paraphrase. Show the script output verbatim.

Per `project_strategic_goals.md`, the two strategic threads are LLM-ready and EV-EVCC.
Items with empty goal-fit are infra/hygiene — surface them but mention "non-goal" so the
user can deprioritise fast.

## Bug-label discipline

Per `feedback_no_auto_bugfix`: bug-labelled upstream issues are default-skipped. Surface
them only when the user explicitly says "auch bugs", "goodwill bug", or names a specific
bug as personally relevant (e.g. "I have a battery, fix #343"). If user asks "any quick
wins?" without bug-context, do NOT pre-emptively offer bug-labelled items.

## Hand-off to `emhass-cross-repo-flow`

After presenting picker output, ask: "Item picken? (ID nennen) oder abbrechen?"

When the user names an item:
- If item has `Scope: Upstream` → invoke `emhass-cross-repo-flow` skill with the item id
- If item has `Scope: Local` → out of scope for cross-repo-flow (Type 2/3); ask user
  whether to drop into ad-hoc planning instead
- If user says "abbrechen" / "stop" → exit, no state change

## What this skill does NOT do

- Implementation, planning, brainstorming — those are `emhass-cross-repo-flow`'s job
- Item content reasoning — picker output is the only signal; do not LLM-summarise items
- GitHub API calls — script is offline; freshness via `fetch.py`, not live queries
- Mutation of `items.json` — read-only

## Common mistakes

| Mistake | Reality |
|---|---|
| Skipping picker, asking LLM "what should I do next?" | `board/next.py` is the source of truth; LLM ranking drifts and double-counts |
| Re-paraphrasing the picker table | Loses determinism; use script output verbatim |
| Suggesting bug-labelled items by default | Violates `feedback_no_auto_bugfix`; require explicit user opt-in |
| Inventing item IDs | If user types an ID not in `items.json`, ask `find_item` to confirm before routing |
