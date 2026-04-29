# AGENTS.md — emhass-contributions

This file documents rules for AI coding agents (Claude Code, Cursor, Aider, Copilot, Codex) working **on this repo**. Different from the AGENTS.md proposed for upstream EMHASS (board item AG-7) — that one targets agents working on EMHASS source.

## Repo identity

This repo is **contribution tooling** for `davidusb-geek/emhass`. It's not an alternative distribution. Treat the upstream project as authoritative for code-of-record. This repo holds:

- Audits + reproducers (read-only against `upstream/`)
- RFCs and design proposals
- Feature-flagged prototypes (run in production with flags off by default)
- The Docker build for the original contributor's smarthome
- Project board source-of-truth

## Don't-touch rules

- **`upstream/`** is a git submodule — do not edit files inside it. Changes to EMHASS source go through the personal fork (`OptimalNothing90/emhass`) → PR to `davidusb-geek/emhass`.
- **`board/items.json`** is the source-of-truth for the project board — edit via the helper scripts (`board/update.py` etc.), not by hand. Otherwise the board and the JSON drift.
- **Tokens, private URLs, Loxone-specific paths** — never commit. Pre-commit hook scrubs but is not infallible.

## Setup

For Python venv / Docker / DevContainer setup, see [`upstream/docs/develop.md`](upstream/docs/develop.md). It's the canonical EMHASS dev guide.

For this repo specifically:
```bash
git submodule update --init --recursive
pip install pytest pyyaml          # for prototypes/ tests
pre-commit install                  # if not already
```

## Adding a new RFC

1. Pick the next free number in `rfcs/` (e.g. `0004-...`).
2. Use the template in `rfcs/README.md`.
3. Open a board card under Phase 3 if not already there. Link from RFC.

## Adding a new prototype

1. Read the corresponding RFC in `rfcs/`.
2. Create `prototypes/<feature_name>.py`. Register routes via the existing pattern (see `prototypes/api_last_run.py` once it lands).
3. Add a default-disabled entry in the example `data/contrib-flags.yaml` schema.
4. Document in `prototypes/README.md`.
5. Test locally with `compose-dev.yml` and the flag enabled.

## Submodule policy

Pinned to **upstream release tags** (`v0.17.2`, etc.) — never to master HEAD or to a fork branch. Reasoning in [the design spec](https://github.com/OptimalNothing90/emhass-contributions/blob/main/board/design.md).

## Production safety

The image built from this repo runs in someone's actual home (heating, battery dispatch, EV charging). Treat changes accordingly:
- Default flag state is **always** off.
- Test with `compose-dev.yml` before deploying.
- 7-day soak on Unraid before activating any flag.
- Keep `:rollback` image tag available.

## Account hygiene

- All git push and gh operations under `OptimalNothing90`.
- Verify with `gh auth status` before push.
- mschaepers is for non-EMHASS work.

## Token / context limits

`upstream/src/emhass/optimization.py` and `command_line.py` are large (3000+ LOC each). For full-repo LLM context, use `npx repomix` (don't commit the output — regenerate on demand).

## Where to find more

- [Project board](https://github.com/users/davidusb-geek/projects/2) — coordination + status
- [Discussion #808](https://github.com/davidusb-geek/emhass/discussions/808) — workflow alignment with maintainer
- [Issue #789](https://github.com/davidusb-geek/emhass/issues/789) — scope corridor (no coupling code in core)
- [`upstream/docs/develop.md`](upstream/docs/develop.md) — canonical EMHASS dev guide
