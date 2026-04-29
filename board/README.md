# board/

Source-of-truth for the [EMHASS AI agents project](https://github.com/users/davidusb-geek/projects/2).

## Files

- `design.md` — project board structure spec (status pipeline, custom fields, views)
- `items.json` — every card with all field values (the canonical state)
- `migrate.py` — bulk-add 41 items (initial migration; idempotent via `--start N`)
- `update.py` — body updates with verified source-state for AC-1/AC-2/AC-3/etc.
- `extend.py` — add new cards (AG-onboarding, AG-pr-readiness, AG-B1)
- `fix-leaks.py` — scrub private-repo / personal-account references from card bodies

## Workflow

The board on github.com is the live state. `items.json` is the offline source-of-truth. They should match. When David, sokorn, or someone moves a card on the website, the JSON falls behind — that's expected. Periodically pull live state into JSON via a fetch script (TODO).

To make changes:

1. Edit `items.json` (or write a new mutation script).
2. Run the script, which calls `gh api graphql` to apply.
3. Commit the JSON change with the same commit as the script.

## GitHub project ID

Pinned to `PVT_kwHOAfZrVs4BV1jU` (davidusb-geek/projects/2). Field IDs and option IDs in `_meta` of `items.json`.

## Account requirement

Project mutations require gh user `OptimalNothing90` (invited as collaborator). Run `gh auth switch --user OptimalNothing90` before any script.
