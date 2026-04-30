# board/

Source-of-truth for the [EMHASS AI agents project](https://github.com/users/davidusb-geek/projects/2).

## Files

- `design.md` — project board structure spec (status pipeline, custom fields, views)
- `items.json` — every card with all field values (the canonical state)
- `lib.py` — shared helpers: gh wrapper, items.json IO, idempotent body-append, field setter
- `fetch.py` — pull live state into `items.json` and report drift (run before any mutation)
- `migrate.py` — bulk-add 41 items (initial migration; idempotent via `--start N`)
- `update.py` — body updates with verified source-state for AC-1/AC-2/AC-3/etc.
- `extend.py` — add new cards (AG-onboarding, AG-pr-readiness, AG-B1)
- `fix-leaks.py` — scrub private-repo / personal-account references from card bodies

## Workflow

The board on github.com is the live state. `items.json` is the offline source-of-truth. They drift whenever David, sokorn, or anyone moves a card on the website — and any mutation script that reads stale `items.json` and writes back will silently overwrite those edits.

Hard rule: **always `python fetch.py` first**, inspect the drift report, commit the JSON refresh, then run mutation scripts.

```bash
gh auth switch --user OptimalNothing90
python fetch.py             # refresh items.json from live, print drift
git diff board/items.json   # review
git commit -m "chore(board): sync items.json with live"
python <mutation-script>.py
```

For body edits to existing draft cards, use `lib.append_to_body_idempotent(draft_id, marker, suffix)` — it fetches the live body first and only appends if `marker` is not already present. This avoids both the stale-body overwrite *and* the double-append on re-run.

`item_id` (PVTI_*) and `draft_id` (DI_*) are stored on every entry after `fetch.py` runs, so new mutation scripts can look them up instead of hardcoding.

## GitHub project ID

Pinned to `PVT_kwHOAfZrVs4BV1jU` (davidusb-geek/projects/2). Field IDs and option IDs in `_meta` of `items.json`.

## Account requirement

Project mutations require gh user `OptimalNothing90` (invited as collaborator). Run `gh auth switch --user OptimalNothing90` before any script.
