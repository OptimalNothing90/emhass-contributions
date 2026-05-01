# emhass-contributions Repo Implementation Plan

> **Status (2026-05-01):** Phase 0 complete. Tasks 1–11 deployed — repo, upstream submodule pinned to v0.17.2, Docker prototype-flags layer, board migration (49+ items at `davidusb-geek/projects/2`), pre-commit hooks. Tasks 12–15 (Unraid cut-over to the custom image) **deferred** until the first prototype is ready for production testing; vanilla upstream EMHASS stays on Unraid in the meantime. This file is kept as historical record of how the repo came up.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `OptimalNothing90/emhass-contributions` public repo with submodule-pinned upstream EMHASS, custom Docker build with feature-flag-gated prototypes, migrate audit/spec/board files out of loxonesmarthome, and cut production EMHASS on Unraid over to the new image with all flags off.

**Architecture:** Public repo siblings the existing fork. `upstream/` is git submodule pinned to upstream release tag (initial v0.17.2). Custom Dockerfile layers `prototypes/` Python module on top of upstream's official image. `prototypes/flags.py` reads `data/contrib-flags.yaml` (mounted from Unraid appdata) at request time with 5s TTL cache + mtime invalidation. Production runs the new image with all flags off — byte-equivalent to vanilla EMHASS until prototypes are explicitly enabled.

**Tech Stack:** GitHub (public repo, GPL-3.0), git submodule, Docker (multi-stage build via two `docker build` invocations), Python 3.11+ (Quart Web framework via upstream EMHASS), PyYAML, pytest (for prototypes module tests). Build runs natively on Unraid (no registry, no save/load). Pre-commit hook with ruff + token-scrub regex.

**Spec:** [`docs/superpowers/specs/2026-04-28-emhass-contributions-repo-design.md`](../specs/2026-04-28-emhass-contributions-repo-design.md)

---

## File Structure

```
emhass-contributions/                   # NEW REPO
├── README.md                           # Task 2
├── AGENTS.md                           # Task 2
├── LICENSE                             # auto from gh repo create --license GPL-3.0
├── .gitignore                          # Task 2
├── .gitattributes                      # Task 2
├── .gitmodules                         # auto from git submodule add (Task 3)
├── .pre-commit-config.yaml             # Task 11
├── upstream/                           # submodule (Task 3)
├── docker/
│   ├── Dockerfile.prototypes           # Task 5
│   ├── compose-prod.yml                # Task 7
│   ├── compose-dev.yml                 # Task 7
│   ├── entrypoint.sh                   # Task 5
│   └── README.md                       # Task 5
├── prototypes/
│   ├── __init__.py                     # Task 9
│   ├── flags.py                        # Task 8 (TDD)
│   ├── README.md                       # Task 9
│   └── tests/
│       ├── __init__.py                 # Task 8
│       └── test_flags.py               # Task 8 (TDD)
├── audits/
│   ├── 2026-04-28-param-definitions.md # Task 4 (migrated)
│   ├── 2026-04-28-plan-output.md       # Task 4 (migrated)
│   ├── reproducer.py                   # Task 4 (migrated)
│   └── README.md                       # Task 4
├── board/
│   ├── design.md                       # Task 4 (migrated)
│   ├── items.json                      # Task 4 (migrated)
│   ├── migrate.py                      # Task 4 (migrated)
│   ├── update.py                       # Task 4 (migrated)
│   ├── extend.py                       # Task 4 (migrated)
│   ├── fix-leaks.py                    # Task 4 (migrated)
│   └── README.md                       # Task 4
├── rfcs/
│   └── README.md                       # Task 6
├── skills/
│   └── README.md                       # Task 6
└── docs/
    └── ai-coders.md                    # Task 6 (placeholder for AG-onboarding)
```

**Local workdir:** `C:/Users/MauricioSchäpers/claude-code/emhass-contributions/` (sibling to `claude-code/loxonesmarthome/` and `claude-code/emhass/`).

**Account hygiene:** all `gh` and `git push` operations under `OptimalNothing90`. Switch back to `mschaepers` after Phase 6.

**Source spec sections:** §1 Goal, §2 Repo Structure, §3 Docker, §4 Deployment, §5 Risks, §7 Decisions.

---

## Phase 1 — Repo Foundation

### Task 1: Create GitHub repo + local clone

**Files:**
- Create (remote): `OptimalNothing90/emhass-contributions` on github.com
- Create (local): `C:/Users/MauricioSchäpers/claude-code/emhass-contributions/`

- [ ] **Step 1: Verify gh user**

```bash
gh auth status
```

Expected: `OptimalNothing90 (keyring)` shown. If not active:

```bash
gh auth switch --user OptimalNothing90
```

- [ ] **Step 2: Create the repo on GitHub**

```bash
gh repo create OptimalNothing90/emhass-contributions \
  --public \
  --license GPL-3.0 \
  --description "EMHASS contribution workspace: audits, RFCs, board source-of-truth, Docker build for production deployment. Complements upstream docs/develop.md." \
  --disable-issues=false \
  --disable-wiki=true
```

Expected output: `https://github.com/OptimalNothing90/emhass-contributions`. The repo has just `LICENSE` (GPL-3.0).

- [ ] **Step 3: Clone locally**

```bash
cd C:/Users/MauricioSchäpers/claude-code
gh repo clone OptimalNothing90/emhass-contributions
cd emhass-contributions
```

Expected: directory created, `git status` shows clean tree on `main` branch.

- [ ] **Step 4: Verify state**

```bash
ls -la
git status
git remote -v
```

Expected: `LICENSE` present, branch `main`, remote `origin` = `https://github.com/OptimalNothing90/emhass-contributions.git`.

- [ ] **Step 5: Commit nothing (state is checkpoint)**

No commit yet — initial skeleton in Task 2 will be the first non-LICENSE commit.

---

### Task 2: Initial skeleton — README, AGENTS.md, .gitignore, .gitattributes

**Files:**
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `.gitignore`
- Create: `.gitattributes`

- [ ] **Step 1: Write README.md**

Content:

````markdown
# emhass-contributions

EMHASS contribution workspace: audits, design RFCs, board source-of-truth, and the production Docker build for the original contributor's smarthome deployment.

> **Important:** This is **not** an alternative EMHASS distribution. The canonical project is [`davidusb-geek/emhass`](https://github.com/davidusb-geek/emhass). For general EMHASS development see [`upstream/docs/develop.md`](upstream/docs/develop.md). This repo complements upstream — it doesn't replace or fork it.

## What's here

- **`audits/`** — schema and plan-output audits with reproducer scripts. Each audit is pinned to a specific upstream commit (recorded via the submodule).
- **`board/`** — source-of-truth for the [EMHASS AI agents project](https://github.com/users/davidusb-geek/projects/2): design spec, item JSON, mutation scripts.
- **`rfcs/`** — design proposals for upstream features (e.g. `/api/last-run`, `/healthz`, openapi.json generation). Pre-PR thinking.
- **`prototypes/`** — feature-flagged Python additions running alongside vanilla EMHASS. Off by default. Used to validate proposed features in production before opening upstream PRs.
- **`docker/`** — Dockerfile and Docker Compose files that build/run the production image.
- **`skills/`** — public Claude Code skill plugins (anonymized variants of personal tooling). Initial home for the AG-B1 board item.
- **`docs/`** — staging area for documentation that may eventually land upstream (e.g. AI-coder contributor onboarding).
- **`upstream/`** — git submodule pinned to a specific upstream release tag (currently `v0.17.2`). The canonical EMHASS source we build against.

## How this relates to other repos

| Repo | Purpose | Link |
|------|---------|------|
| `davidusb-geek/emhass` | Canonical upstream EMHASS | https://github.com/davidusb-geek/emhass |
| `OptimalNothing90/emhass` | Personal fork — branches for upstream PRs | https://github.com/OptimalNothing90/emhass |
| `OptimalNothing90/emhass-contributions` | This repo — audits, RFCs, prototypes, Docker build | (you are here) |

PRs to upstream go through the personal fork, not from this repo. The submodule here is pinned to upstream tags — never to a fork branch — to keep production builds tied to merged code only.

## Local development

See [`AGENTS.md`](AGENTS.md) for AI-tool rules and [`upstream/docs/develop.md`](upstream/docs/develop.md) for the canonical EMHASS dev guide. Quick start:

```bash
git submodule update --init --recursive
docker build -t emhass-base:$(cd upstream && git describe --tags) -f upstream/Dockerfile upstream/
docker build -t emhass-contrib/prod:dev -f docker/Dockerfile.prototypes \
  --build-arg BASE_IMAGE=emhass-base:$(cd upstream && git describe --tags) .
docker compose -f docker/compose-dev.yml up
```

Then visit `http://localhost:5050`.

## Submodule update workflow

```bash
cd upstream
git fetch --tags
git checkout <new-tag>
cd ..
git add upstream
git commit -m "chore(upstream): bump submodule to <new-tag>"
# build + dev-validate before push
git push
```

## License

GPL-3.0 (matches upstream EMHASS). See [`LICENSE`](LICENSE).
````

Write the file with that content.

- [ ] **Step 2: Write AGENTS.md**

Content:

````markdown
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
````

Write the file with that content.

- [ ] **Step 3: Write .gitignore**

Content:

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
venv/

# Editor
.vscode/
.idea/
*.swp
.DS_Store

# Repomix output (on-demand only, never committed)
repomix-output.*

# Build / Docker artefacts
*.tar
*.tar.gz
.docker/

# Local-only test data
data/
contrib-flags.yaml         # only the example lives in repo; actual config lives in container volume
```

Write the file with that content.

- [ ] **Step 4: Write .gitattributes**

Content:

```
# Default: text, normalize line endings to LF on commit
* text=auto eol=lf

# Binary files — never normalize
*.png binary
*.jpg binary
*.ico binary
*.tar binary
*.tar.gz binary

# Submodule directory — don't normalize anything inside
upstream/** -text
```

Write the file with that content.

- [ ] **Step 5: Commit + push**

```bash
git add README.md AGENTS.md .gitignore .gitattributes
git commit -m "chore: initial skeleton (README, AGENTS, gitignore, gitattributes)"
git push origin main
```

Expected: push succeeds, GitHub repo now shows README on landing page.

---

### Task 3: Add upstream EMHASS submodule

**Files:**
- Create: `upstream/` (git submodule)
- Auto-create: `.gitmodules`

- [ ] **Step 1: Add the submodule**

```bash
git submodule add https://github.com/davidusb-geek/emhass.git upstream
```

Expected: `upstream/` directory populated with EMHASS source at default branch (master), `.gitmodules` created.

- [ ] **Step 2: Pin to v0.17.2**

```bash
cd upstream
git fetch --tags
git checkout v0.17.2
cd ..
```

Expected: `cd upstream && git describe --tags` returns `v0.17.2`.

- [ ] **Step 3: Verify submodule integrity**

```bash
ls upstream/src/emhass/static/data/param_definitions.json
ls upstream/Dockerfile
ls upstream/docs/develop.md
```

Expected: all three files exist (sanity-check we have the right ref).

- [ ] **Step 4: Commit + push**

```bash
git add .gitmodules upstream
git commit -m "feat(upstream): add submodule pinned to v0.17.2

Submodule URL points at davidusb-geek/emhass (upstream), not the fork.
Pin tracks release tags only per spec section 2.2."
git push origin main
```

Expected: push succeeds. GitHub repo page shows `upstream @ v0.17.2` link.

---

## Phase 2 — Migration

### Task 4: Migrate audits, board, scripts from loxonesmarthome

**Files (8 migrated + 6 README files):**
- Migrate: `loxonesmarthome/docs/superpowers/specs/2026-04-28-emhass-ai-agents-board-design.md` → `board/design.md`
- Migrate: `loxonesmarthome/docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json` → `board/items.json`
- Migrate: `loxonesmarthome/docs/superpowers/specs/2026-04-28-param-definitions-audit.md` → `audits/2026-04-28-param-definitions.md`
- Migrate: `loxonesmarthome/docs/superpowers/specs/2026-04-28-plan-output-audit.md` → `audits/2026-04-28-plan-output.md`
- Migrate: `loxonesmarthome/docs/superpowers/specs/migrate-emhass-board.py` → `board/migrate.py`
- Migrate: `loxonesmarthome/docs/superpowers/specs/update-emhass-board.py` → `board/update.py`
- Migrate: `loxonesmarthome/docs/superpowers/specs/extend-board-ai-contributor.py` → `board/extend.py`
- Migrate: `loxonesmarthome/docs/superpowers/specs/fix-private-repo-leaks.py` → `board/fix-leaks.py`
- Create: `audits/README.md`
- Create: `board/README.md`
- Create: `rfcs/README.md`
- Create: `skills/README.md`
- Create: `docs/ai-coders.md` (placeholder pointing at AG-onboarding card)
- Create: `prototypes/README.md` (initial placeholder; flag table goes here in Task 9)

- [ ] **Step 1: Capture original commit SHAs for traceability**

```bash
cd C:/Users/MauricioSchäpers/claude-code/loxonesmarthome
for f in docs/superpowers/specs/2026-04-28-emhass-ai-agents-board-design.md \
         docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json \
         docs/superpowers/specs/2026-04-28-param-definitions-audit.md \
         docs/superpowers/specs/2026-04-28-plan-output-audit.md \
         docs/superpowers/specs/migrate-emhass-board.py \
         docs/superpowers/specs/update-emhass-board.py \
         docs/superpowers/specs/extend-board-ai-contributor.py \
         docs/superpowers/specs/fix-private-repo-leaks.py; do
  echo "$f: $(git log -1 --format='%H' -- "$f")"
done > /tmp/original-shas.txt
cat /tmp/original-shas.txt
```

Save these SHAs — needed in the migration commit message in Step 6.

- [ ] **Step 2: Make target directories**

```bash
cd C:/Users/MauricioSchäpers/claude-code/emhass-contributions
mkdir -p audits board rfcs skills prototypes/tests docs docker
```

Expected: empty directories present.

- [ ] **Step 3: Copy files with renames**

```bash
SRC=C:/Users/MauricioSchäpers/claude-code/loxonesmarthome/docs/superpowers/specs
DST=C:/Users/MauricioSchäpers/claude-code/emhass-contributions

cp "$SRC/2026-04-28-emhass-ai-agents-board-design.md"    "$DST/board/design.md"
cp "$SRC/2026-04-28-emhass-board-migration-items.json"   "$DST/board/items.json"
cp "$SRC/migrate-emhass-board.py"                          "$DST/board/migrate.py"
cp "$SRC/update-emhass-board.py"                           "$DST/board/update.py"
cp "$SRC/extend-board-ai-contributor.py"                   "$DST/board/extend.py"
cp "$SRC/fix-private-repo-leaks.py"                        "$DST/board/fix-leaks.py"

cp "$SRC/2026-04-28-param-definitions-audit.md"          "$DST/audits/2026-04-28-param-definitions.md"
cp "$SRC/2026-04-28-plan-output-audit.md"                "$DST/audits/2026-04-28-plan-output.md"
```

Expected: 8 files copied to new locations.

- [ ] **Step 4: Write audits/README.md**

```bash
cd C:/Users/MauricioSchäpers/claude-code/emhass-contributions
```

Content for `audits/README.md`:

```markdown
# audits/

Schema and plan-output audits against the upstream EMHASS source pinned in `../upstream/`.

## Files

- `2026-04-28-param-definitions.md` — input-side schema audit (param_definitions.json vs config_defaults.json vs utils.treat_runtimeparams). Source for board cards AC-2, AC-2a, AC-2b, AC-2-fix.
- `2026-04-28-plan-output.md` — output-side schema audit (the 5 _publish_* helpers in command_line.py). Source for board card AC-1.
- `reproducer.py` — re-runs both audits against the current submodule pin. (Pending — TODO Task: port from loxonesmarthome session output.)

## Reproducing an audit

```bash
cd ..
git submodule update --init --recursive
python audits/reproducer.py
```

The reproducer reads from `upstream/` so the pin determines what's audited. Each audit file documents the upstream commit it reflects.

## Adding a new audit

1. Re-run the reproducer to refresh outputs.
2. Save with a date-prefixed filename (e.g. `2026-06-15-param-definitions.md`).
3. Old files stay for history — never overwrite past audits.
```

Write the file.

- [ ] **Step 5: Write board/README.md**

Content:

```markdown
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
```

Write the file.

- [ ] **Step 6: Write rfcs/README.md**

Content:

```markdown
# rfcs/

Design proposals for upstream EMHASS features. Each RFC is a markdown document arguing for a specific change before any code is written.

## Naming

`NNNN-short-slug.md`, where `NNNN` is the next free 4-digit number. Slugs are lowercase, hyphenated, max ~5 words.

## Lifecycle

- **Draft** — RFC committed here, but no upstream issue yet
- **Issue-filed** — corresponding issue opened on `davidusb-geek/emhass`, link added in RFC header
- **Approved** — maintainer green-lit (issue comment), prototype work can start
- **Shipped** — feature merged upstream → next submodule bump pulls it → corresponding prototype removed

## Template

```markdown
# RFC NNNN: <Title>

**Status:** Draft | Issue-filed | Approved | Shipped
**Issue:** <link>
**Board card:** <link>
**Author:** OptimalNothing90
**Date:** YYYY-MM-DD

## Motivation
Why does this matter? What problem does it solve?

## Proposed change
What exactly changes in EMHASS?

## API / contract
If endpoints / schemas / file formats change, what do they look like?

## Threat model
Per #808 maintainer comment: code-injection focus. Confirm: no FS/DB writes, no shell-out, no user-controlled deserialization, no path-traversal vector.

## Backward compatibility
Default-config still works? Existing consumers unaffected?

## Open questions
What hasn't been decided yet?
```

## Current RFCs

(none yet — RFC 0001 will be /api/last-run when the corresponding prototype is staged)
```

Write the file.

- [ ] **Step 7: Write skills/README.md**

Content:

```markdown
# skills/

Public Claude Code skill plugins distributed via this repo. Anonymized variants of personal tooling — no Loxone, no Tibber, no EVCC specifics.

## Status

Empty for now. First skill arrives when board card AG-B1 (Public skill plugin distribution) is shipped.

## Planned

- `emhass-troubleshoot/` — anonymized variant of the personal AG-1 skill (reads action_logs.txt + last-run banner + InfluxDB solver data, produces structured triage report)
- `emhass-config-validate/` — depends on AC-2a (unit field) and AC-2b (runtime params) being merged upstream
- `emhass-plan-explain/` — depends on AC-1 (plan output schema doc)

## Distribution

Each skill follows the Claude Code plugin manifest format. Installation will be `claude code plugin install OptimalNothing90/emhass-contributions/skills/<name>` once Plugin Marketplace supports per-folder plugins.
```

Write the file.

- [ ] **Step 8: Write docs/ai-coders.md placeholder**

Content:

```markdown
# AI-Coder Contributor Guide — Draft Staging

This is the staging area for the AG-onboarding board item. Once written and reviewed, the final version PRs upstream to `davidusb-geek/emhass:docs/contributing/ai-coders.md` (or as a section in `CONTRIBUTING.md`).

## Status

**Empty** — draft work pending. See [board card AG-onboarding](https://github.com/users/davidusb-geek/projects/2) for scope.

## Important framing

This doc **complements upstream `docs/develop.md`** — it does not duplicate. develop.md teaches "how to develop EMHASS" generally; this doc teaches "how to develop EMHASS with AI tooling" specifically.

Opening line of the final doc: *"This complements `docs/develop.md`. Read that first if new to EMHASS."*
```

Write the file.

- [ ] **Step 9: Write prototypes/README.md placeholder**

Content for `prototypes/README.md`:

```markdown
# prototypes/

Feature-flagged Python additions running alongside vanilla EMHASS in production. Off by default. Used to validate proposed features in real conditions before opening upstream PRs.

## Status

Initial scaffold — `flags.py` (config reader) lives here. Concrete feature modules (e.g. `api_last_run.py`, `api_healthz.py`) arrive when corresponding RFCs are approved.

## Flag file

Production reads flags from `/app/data/contrib-flags.yaml` (mounted from host). Schema:

```yaml
prototypes:
  <feature_name>:
    enabled: false       # default off — always
    # feature-specific settings here
```

Missing file → all flags off. Parse error → all flags off + log warning.

## Per-flag overview

(populated as features land; initial table empty)

| Flag | Status | Default | Description |
|------|--------|---------|-------------|
| (none yet) | | | |

## Adding a new prototype

See `../AGENTS.md` § "Adding a new prototype". Brief:

1. Read the RFC in `../rfcs/`.
2. Create `<feature_name>.py` here.
3. Add the flag entry to the example schema above.
4. Test with `compose-dev.yml` (all flags on by default in dev).
```

Write the file.

- [ ] **Step 10: Verify all migrated files are present**

```bash
cd C:/Users/MauricioSchäpers/claude-code/emhass-contributions
ls -la audits/ board/ rfcs/ skills/ prototypes/ docs/ docker/
```

Expected:
- `audits/`: 2 audit md files + README
- `board/`: 4 .py + design.md + items.json + README
- `rfcs/`: README only
- `skills/`: README only
- `prototypes/`: README only (no `__init__.py`, `flags.py`, or tests yet — those are Task 8/9)
- `docs/`: ai-coders.md only
- `docker/`: empty (Task 5/7 fills it)

- [ ] **Step 11: Commit + push migration**

```bash
git add audits/ board/ rfcs/ skills/ prototypes/ docs/
git commit -m "feat: import audits, board, and contrib-doc scaffolding from loxonesmarthome

Files migrated (with their original commit SHAs from loxonesmarthome master):
  $(cat /tmp/original-shas.txt)

Subsequent renames per spec section 4.2:
- 2026-04-28-emhass-ai-agents-board-design.md → board/design.md
- 2026-04-28-emhass-board-migration-items.json → board/items.json
- 2026-04-28-param-definitions-audit.md → audits/2026-04-28-param-definitions.md
- 2026-04-28-plan-output-audit.md → audits/2026-04-28-plan-output.md
- migrate/update/extend/fix-leaks-emhass-board.py → board/{migrate,update,extend,fix-leaks}.py

The board scripts retain their original logic. The audit reproducer port (audits/reproducer.py) is a separate task."
git push origin main
```

Expected: push succeeds. Repo now has all 8 migrated files plus 6 README files.

---

## Phase 3 — Docker + Prototypes

### Task 5: Docker entrypoint script + Dockerfile.prototypes

**Files:**
- Create: `docker/entrypoint.sh`
- Create: `docker/Dockerfile.prototypes`
- Create: `docker/README.md`

- [ ] **Step 1: Write docker/entrypoint.sh**

Content:

```bash
#!/bin/sh
# emhass-contributions production entrypoint
# Wraps upstream EMHASS to ensure prototypes/ is on PYTHONPATH and importable.
# Actual feature gating happens via prototypes/flags.py reading contrib-flags.yaml,
# not via env vars or this script.

set -e

# Ensure prototypes/ is importable
export PYTHONPATH="/opt/emhass-contrib:${PYTHONPATH:-}"

# Eager-import prototypes module so any registration code runs
# before EMHASS starts serving traffic. Errors here should NOT crash
# the container — log and continue with vanilla EMHASS.
python -c "
import logging, sys, traceback
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s: %(message)s')
try:
    import prototypes
    print('[contrib-entrypoint] prototypes module imported')
except Exception:
    print('[contrib-entrypoint] WARNING: prototypes import failed; running vanilla EMHASS', file=sys.stderr)
    traceback.print_exc()
" || true

# Hand off to upstream's entrypoint or the EMHASS web server
exec python -m emhass.web_server "$@"
```

Write the file.

- [ ] **Step 2: Make entrypoint executable**

```bash
chmod +x docker/entrypoint.sh
```

Expected: `ls -l docker/entrypoint.sh` shows `x` permission.

- [ ] **Step 3: Write docker/Dockerfile.prototypes**

Content:

```dockerfile
# syntax=docker/dockerfile:1
# emhass-contrib production image
# Layers prototypes/ on top of upstream EMHASS image (built separately from upstream/Dockerfile).

ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Copy prototypes/ alongside upstream EMHASS source.
# /opt/emhass-contrib/ is added to PYTHONPATH by the entrypoint.
COPY prototypes/ /opt/emhass-contrib/prototypes/

# Install minimal extra deps for prototypes/. EMHASS already has Flask/Quart, etc.
# pyyaml is the only dependency for prototypes/flags.py.
RUN python -m pip install --no-cache-dir pyyaml

# Wrapper entrypoint that ensures prototypes/ is importable and surfaces
# import errors as warnings, not crashes.
COPY docker/entrypoint.sh /usr/local/bin/contrib-entrypoint.sh
RUN chmod +x /usr/local/bin/contrib-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/contrib-entrypoint.sh"]

# Labels for traceability (filled at build time via --label)
LABEL com.emhass.contrib.repo="OptimalNothing90/emhass-contributions"
```

Write the file.

- [ ] **Step 4: Write docker/README.md**

Content:

````markdown
# docker/

Production and dev Docker artifacts for emhass-contributions.

## Files

- `Dockerfile.prototypes` — layers our prototypes onto upstream EMHASS image
- `compose-prod.yml` — production deploy on Unraid
- `compose-dev.yml` — local dev / repro on a developer machine
- `entrypoint.sh` — wraps upstream entrypoint to import prototypes/

## Build chain

Two-stage build:

```bash
# Stage 1: build vanilla upstream EMHASS from submodule
PIN=$(cd ../upstream && git describe --tags)
docker build -t emhass-base:${PIN} -f ../upstream/Dockerfile ../upstream/

# Stage 2: layer our prototypes
docker build -t emhass-contrib/prod:${PIN}-c1 \
  -f Dockerfile.prototypes \
  --build-arg BASE_IMAGE=emhass-base:${PIN} \
  ..
```

(Note `..` for build context — the parent directory of `docker/` so the Dockerfile can `COPY prototypes/`.)

## Image tag scheme

`emhass-contrib/prod:<UPSTREAM_TAG>-c<CONTRIB_REV>`

- `<UPSTREAM_TAG>` = current submodule pin (e.g. `v0.17.2`)
- `<CONTRIB_REV>` = our iteration counter, bumped on every prod-bound change (e.g. `c1`, `c2`)

When we bump the submodule, we typically reset rev to `c1` (e.g. `v0.17.3-c1`).

## Running prod

```bash
docker compose -f compose-prod.yml up -d
```

Designed for Unraid. Mounts `/mnt/user/appdata/emhass/` as the data volume; same path as the legacy upstream container.

## Running dev

```bash
docker compose -f compose-dev.yml up
```

Runs on `:5050`, separate data path. Flags can be enabled via `compose-dev.yml`'s mounted `contrib-flags.yaml` for full prototype testing.
````

Write the file.

- [ ] **Step 5: Verify file structure**

```bash
ls -la docker/
```

Expected: `Dockerfile.prototypes`, `entrypoint.sh` (executable), `README.md`. No compose files yet (Task 7).

- [ ] **Step 6: Commit (no push yet — push after Task 7 lands compose files)**

```bash
git add docker/Dockerfile.prototypes docker/entrypoint.sh docker/README.md
git commit -m "feat(docker): Dockerfile.prototypes + entrypoint.sh

Two-stage build: upstream/Dockerfile produces emhass-base:<tag>, then
our Dockerfile.prototypes layers prototypes/ on top. Entrypoint wraps
upstream's launch with PYTHONPATH adjustment + non-fatal prototype
import."
```

---

### Task 6: Write README placeholders for unfilled directories

(Done in Task 4 Step 4-9 already. This task block reserved if additional READMEs are needed during scope expansion. Skip.)

---

### Task 7: Docker Compose files (prod + dev)

**Files:**
- Create: `docker/compose-prod.yml`
- Create: `docker/compose-dev.yml`

- [ ] **Step 1: Write docker/compose-prod.yml**

Content:

```yaml
# Production deployment on Unraid.
# - Same path / port / container name as the legacy upstream image
#   so Node-RED and Loxone reach the same address before and after cutover.
# - All prototype flags off by default — flag state is in
#   /mnt/user/appdata/emhass/contrib-flags.yaml (NOT in this file).

services:
  emhass:
    image: emhass-contrib/prod:v0.17.2-c1
    container_name: emhass
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - /mnt/user/appdata/emhass:/app/data
      - /mnt/user/appdata/emhass/options.json:/data/options.json:ro
    environment:
      # Upstream EMHASS env vars (HA URL/key etc.) — copy from existing container template
      URL: "${HA_URL}"
      KEY: "${HA_KEY}"
      TIME_ZONE: "${TIME_ZONE:-Europe/Berlin}"
      LAT: "${LAT}"
      LON: "${LON}"
      ALT: "${ALT}"
    labels:
      com.emhass.upstream-pin: "v0.17.2"
      com.emhass.contrib-rev: "c1"
```

Write the file.

- [ ] **Step 2: Write docker/compose-dev.yml**

Content:

```yaml
# Local dev / repro stack.
# - Separate data path (no production-data overwrite risk)
# - Port 5050 (parallel to prod 5000)
# - Mounts a dev contrib-flags.yaml with all prototype flags ON for full smoke test.

services:
  emhass:
    image: emhass-contrib/prod:dev
    build:
      context: ..
      dockerfile: docker/Dockerfile.prototypes
      args:
        BASE_IMAGE: ${BASE_IMAGE:-emhass-base:dev}
    container_name: emhass-contrib-dev
    ports:
      - "5050:5000"
    volumes:
      - ./dev-data:/app/data
      - ./contrib-flags.dev.yaml:/app/data/contrib-flags.yaml:ro
    environment:
      URL: "${HA_URL:-http://localhost}"
      KEY: "${HA_KEY:-dev-key}"
      TIME_ZONE: "${TIME_ZONE:-Europe/Berlin}"
      LAT: "${LAT:-50.0}"
      LON: "${LON:-10.0}"
      ALT: "${ALT:-100}"
```

Write the file.

- [ ] **Step 3: Write docker/contrib-flags.dev.yaml (dev-only flag config)**

Content:

```yaml
# Dev-only flag config — all prototypes ON for full smoke testing.
# Production flags live at /mnt/user/appdata/emhass/contrib-flags.yaml on Unraid
# and start with everything OFF.
prototypes:
  api_last_run:
    enabled: true
    cache_seconds: 30
  api_healthz:
    enabled: true
  openapi_gen:
    enabled: true

logging:
  level: DEBUG
```

Write the file.

- [ ] **Step 4: Verify**

```bash
ls -la docker/
docker compose -f docker/compose-prod.yml config 2>&1 | head -20
docker compose -f docker/compose-dev.yml config 2>&1 | head -20
```

Expected: 5 files in `docker/` (`Dockerfile.prototypes`, `compose-prod.yml`, `compose-dev.yml`, `entrypoint.sh`, `contrib-flags.dev.yaml`, `README.md`). `compose config` parses without error (warnings about missing env vars in prod compose are OK — those resolve at deploy time).

- [ ] **Step 5: Commit + push (Task 5 + 7 together)**

```bash
git add docker/compose-prod.yml docker/compose-dev.yml docker/contrib-flags.dev.yaml
git commit -m "feat(docker): compose-prod and compose-dev with all-flags-on dev profile

Prod compose mirrors the legacy upstream container (same name, port, path)
so cutover doesn't require Node-RED or Loxone re-config.

Dev compose builds the image locally (parallel build to upstream image)
and mounts a dev flag-file with all prototypes enabled for smoke test."
git push origin main
```

Expected: push succeeds. Combined commit history now shows the docker/ folder fully populated.

---

### Task 8: Implement prototypes/flags.py with TDD

**Files:**
- Create: `prototypes/__init__.py` (just imports flags so it's discoverable)
- Create: `prototypes/flags.py`
- Create: `prototypes/tests/__init__.py`
- Create: `prototypes/tests/test_flags.py`

The module reads `data/contrib-flags.yaml`, caches with TTL + mtime invalidation, returns `False` on any error path. We TDD this — tests first, minimal implementation, refactor.

- [ ] **Step 1: Set up Python test environment**

```bash
cd C:/Users/MauricioSchäpers/claude-code/emhass-contributions
python -m pip install --user pytest pyyaml
```

Expected: pytest + pyyaml installed (or already present — that's fine).

- [ ] **Step 2: Create __init__.py files (empty placeholders)**

```bash
echo '' > prototypes/__init__.py
echo '' > prototypes/tests/__init__.py
```

Write empty files (one blank line each is fine).

- [ ] **Step 3: Write the first failing test (missing file → all False)**

Create `prototypes/tests/test_flags.py` with content:

```python
"""Tests for prototypes/flags.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from prototypes import flags


def test_missing_file_returns_false(tmp_path: Path):
    """A non-existent flags file means all features are off."""
    nonexistent = tmp_path / "no-such-file.yaml"

    flags._cache.clear()                         # avoid cross-test cache contamination
    flags._cache.update({"mtime": 0.0, "expires": 0.0, "data": {}})

    assert flags.is_enabled("api_last_run", path=nonexistent) is False
    assert flags.is_enabled("api_healthz", path=nonexistent) is False
    assert flags.is_enabled("anything_else", path=nonexistent) is False
```

Write the file with that content.

- [ ] **Step 4: Run the test — confirm it fails (no module)**

```bash
cd C:/Users/MauricioSchäpers/claude-code/emhass-contributions
python -m pytest prototypes/tests/test_flags.py -v
```

Expected: `ModuleNotFoundError: No module named 'prototypes.flags'` or import error. **The test should fail loudly because flags.py doesn't exist yet.**

- [ ] **Step 5: Write minimal flags.py to make test 1 pass**

Create `prototypes/flags.py` with content:

```python
"""Feature-flag reader for emhass-contrib prototypes.

Reads a YAML config file (default: /app/data/contrib-flags.yaml).
File-based config so flags can be toggled without container restart.

Behavior on errors:
- Missing file -> all flags False (treat-missing-as-off).
- Parse error -> all flags False, log warning.

Caching: 5-second TTL with mtime invalidation to keep request-time
overhead minimal.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import yaml

DEFAULT_FLAGS_PATH = Path(
    os.environ.get("EMHASS_CONTRIB_FLAGS_PATH", "/app/data/contrib-flags.yaml")
)
CACHE_TTL_SECONDS = 5

_logger = logging.getLogger("emhass.contrib.flags")
_cache: dict[str, Any] = {"mtime": 0.0, "expires": 0.0, "data": {}}


def _read_flags(path: Path) -> dict[str, Any]:
    """Read flags YAML. Returns empty dict on any error."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                _logger.warning("flags file is not a dict: %s", path)
                return {}
            return data
    except FileNotFoundError:
        return {}
    except (yaml.YAMLError, OSError) as e:
        _logger.warning("flags file unreadable (%s): %s", e, path)
        return {}


def _get_cached(path: Path) -> dict[str, Any]:
    """Return cached flags. Invalidate if file mtime changed or TTL expired."""
    now = time.monotonic()
    try:
        mtime = path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        mtime = 0.0

    if now > _cache["expires"] or mtime != _cache["mtime"]:
        _cache["data"] = _read_flags(path)
        _cache["mtime"] = mtime
        _cache["expires"] = now + CACHE_TTL_SECONDS
    return _cache["data"]


def is_enabled(feature: str, *, path: Path | None = None) -> bool:
    """Return True if the named prototype feature is enabled in the flags file."""
    flags_dict = _get_cached(path or DEFAULT_FLAGS_PATH)
    return bool(
        flags_dict.get("prototypes", {}).get(feature, {}).get("enabled", False)
    )


def get_setting(
    feature: str, key: str, default: Any = None, *, path: Path | None = None
) -> Any:
    """Return a feature-specific setting (e.g. cache_seconds for api_last_run)."""
    flags_dict = _get_cached(path or DEFAULT_FLAGS_PATH)
    return flags_dict.get("prototypes", {}).get(feature, {}).get(key, default)
```

Write the file with that content.

- [ ] **Step 6: Run test 1 — should pass now**

```bash
python -m pytest prototypes/tests/test_flags.py::test_missing_file_returns_false -v
```

Expected: `PASSED`. The function exists, missing file → False.

- [ ] **Step 7: Add test 2 — empty file behavior**

Append to `prototypes/tests/test_flags.py`:

```python


def test_empty_file_returns_false(tmp_path: Path):
    """An empty YAML file should result in all features off."""
    empty = tmp_path / "empty.yaml"
    empty.write_text("")

    flags._cache.clear()
    flags._cache.update({"mtime": 0.0, "expires": 0.0, "data": {}})

    assert flags.is_enabled("api_last_run", path=empty) is False
```

- [ ] **Step 8: Run test 2 — should pass without code changes**

```bash
python -m pytest prototypes/tests/test_flags.py::test_empty_file_returns_false -v
```

Expected: `PASSED`. (Empty file → `yaml.safe_load` returns `None` → `isinstance(None, dict)` is False → return `{}`.)

- [ ] **Step 9: Add test 3 — feature explicitly enabled**

Append to `test_flags.py`:

```python


def test_feature_enabled_returns_true(tmp_path: Path):
    """A flag explicitly set enabled: true should return True."""
    cfg = tmp_path / "enabled.yaml"
    cfg.write_text(
        """
prototypes:
  api_last_run:
    enabled: true
"""
    )

    flags._cache.clear()
    flags._cache.update({"mtime": 0.0, "expires": 0.0, "data": {}})

    assert flags.is_enabled("api_last_run", path=cfg) is True
    assert flags.is_enabled("api_healthz", path=cfg) is False  # other feature still off
```

- [ ] **Step 10: Run test 3 — should pass**

```bash
python -m pytest prototypes/tests/test_flags.py::test_feature_enabled_returns_true -v
```

Expected: `PASSED`.

- [ ] **Step 11: Add test 4 — invalid YAML returns False without crash**

Append to `test_flags.py`:

```python


def test_invalid_yaml_returns_false_with_log(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    """Malformed YAML should not crash; should log warning + return all-off."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(":\n  - not really yaml [\n")        # malformed

    flags._cache.clear()
    flags._cache.update({"mtime": 0.0, "expires": 0.0, "data": {}})

    with caplog.at_level("WARNING", logger="emhass.contrib.flags"):
        result = flags.is_enabled("api_last_run", path=bad)

    assert result is False
    # at least one warning was logged
    assert any("unreadable" in rec.message or "not a dict" in rec.message
               for rec in caplog.records)
```

- [ ] **Step 12: Run test 4 — should pass**

```bash
python -m pytest prototypes/tests/test_flags.py::test_invalid_yaml_returns_false_with_log -v
```

Expected: `PASSED`.

- [ ] **Step 13: Add test 5 — get_setting returns feature-specific value**

Append to `test_flags.py`:

```python


def test_get_setting_returns_feature_specific_value(tmp_path: Path):
    """get_setting should return per-feature settings, with default fallback."""
    cfg = tmp_path / "settings.yaml"
    cfg.write_text(
        """
prototypes:
  api_last_run:
    enabled: true
    cache_seconds: 60
"""
    )

    flags._cache.clear()
    flags._cache.update({"mtime": 0.0, "expires": 0.0, "data": {}})

    assert flags.get_setting("api_last_run", "cache_seconds", path=cfg) == 60
    assert flags.get_setting("api_last_run", "missing_key", default="x", path=cfg) == "x"
    assert flags.get_setting("nonexistent_feature", "anything", default=None, path=cfg) is None
```

- [ ] **Step 14: Run test 5 — should pass**

```bash
python -m pytest prototypes/tests/test_flags.py::test_get_setting_returns_feature_specific_value -v
```

Expected: `PASSED`.

- [ ] **Step 15: Add test 6 — cache invalidation on mtime change**

Append to `test_flags.py`:

```python


def test_cache_invalidates_on_mtime_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Editing the file should invalidate cache before TTL expires."""
    cfg = tmp_path / "live.yaml"
    cfg.write_text(
        """
prototypes:
  api_last_run:
    enabled: false
"""
    )

    flags._cache.clear()
    flags._cache.update({"mtime": 0.0, "expires": 0.0, "data": {}})

    # First read: disabled
    assert flags.is_enabled("api_last_run", path=cfg) is False

    # Edit the file with a newer mtime (force, since some FSs round mtime)
    cfg.write_text(
        """
prototypes:
  api_last_run:
    enabled: true
"""
    )
    new_mtime = cfg.stat().st_mtime + 10
    os.utime(cfg, (new_mtime, new_mtime))

    # Second read: should reflect the change despite no TTL expiry
    assert flags.is_enabled("api_last_run", path=cfg) is True
```

- [ ] **Step 16: Run test 6 — should pass**

```bash
python -m pytest prototypes/tests/test_flags.py::test_cache_invalidates_on_mtime_change -v
```

Expected: `PASSED`.

- [ ] **Step 17: Run all tests one more time**

```bash
python -m pytest prototypes/tests/test_flags.py -v
```

Expected: 6 PASSED, 0 failed.

- [ ] **Step 18: Commit**

```bash
git add prototypes/__init__.py prototypes/flags.py prototypes/tests/__init__.py prototypes/tests/test_flags.py
git commit -m "feat(prototypes): flags.py with TDD test suite

Reads /app/data/contrib-flags.yaml. Returns False on missing file,
empty file, malformed YAML, or any read error. Caches 5s with mtime
invalidation. 6 unit tests covering all error paths."
```

(Push deferred until Task 9.)

---

### Task 9: prototypes/__init__.py minimal content + flag-table populate

**Files:**
- Modify: `prototypes/__init__.py`

- [ ] **Step 1: Write prototypes/__init__.py**

Replace empty content with:

```python
"""emhass-contrib prototypes — feature-flagged additions to upstream EMHASS.

Each module here registers extra Quart routes (or other extensions)
on the upstream EMHASS app. Routes always register at import time;
each handler checks `flags.is_enabled(<feature>)` per-request and
returns 404 when the flag is off.

This package's import is triggered by docker/entrypoint.sh; if any
prototype module fails to import, the entrypoint logs the traceback
and continues with vanilla EMHASS (does NOT crash the container).

See AGENTS.md > "Adding a new prototype" for the contributor flow.
"""
from __future__ import annotations

# Re-export flags utilities so prototype modules can `from prototypes import flags`
from . import flags

__all__ = ["flags"]
```

Write the file.

- [ ] **Step 2: Verify import still works under pytest**

```bash
python -m pytest prototypes/tests/test_flags.py -v
```

Expected: 6 PASSED. (Re-export shouldn't break anything.)

- [ ] **Step 3: Commit + push (Task 8 + 9 together)**

```bash
git add prototypes/__init__.py
git commit -m "feat(prototypes): __init__ exports flags module"
git push origin main
```

Expected: push succeeds. Phase 3 complete.

---

## Phase 4 — Pre-commit + Local Validation

### Task 10: Pre-commit hook for token-scrub + basic hygiene

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Write .pre-commit-config.yaml**

Content:

```yaml
# Pre-commit hook config for emhass-contributions.
# Catches private-repo refs, personal account hardcoding, and basic
# hygiene issues before they hit GitHub.

repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
        # exclude dev compose mount target (which has placeholder ${VARS})
        exclude: '^docker/compose-(prod|dev)\.yml$'
      - id: check-json
      - id: check-added-large-files
        args: ['--maxkb=500']

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: ['--fix']
        files: \.py$
      - id: ruff-format
        files: \.py$

  - repo: local
    hooks:
      - id: scrub-private-refs
        name: Scrub private-repo / personal account refs
        entry: python scripts/scrub-private-refs.py
        language: system
        types: [text]
        # Excludes:
        # - upstream/                      : submodule content, not ours
        # - scripts/scrub-private-refs.py  : defines the patterns; self-match
        exclude: '^(upstream/|scripts/scrub-private-refs\.py$)'
```

> **Note (post-implementation):** The plan originally inlined the scrub regex set in this YAML via `python -c "..."`. That was rewritten during Task 11 to call a standalone `scripts/scrub-private-refs.py` so the patterns live in one place and the script can be excluded from itself. The pattern set covers: the private repo URL, the Unraid emhass appdata path, and two private env-var names — full literals are kept inside `scripts/scrub-private-refs.py` only, so neither this plan nor any other tracked file re-publishes them.

Write the file.

- [ ] **Step 2: Install pre-commit hooks**

```bash
python -m pip install --user pre-commit
pre-commit install
```

Expected: `pre-commit installed at .git/hooks/pre-commit`.

- [ ] **Step 3: Run pre-commit on all files (sanity check)**

```bash
pre-commit run --all-files
```

Expected: hooks run on all files. Some may fix things (whitespace, line endings) — that's fine. The custom `scrub-private-refs` hook should pass on a clean repo. If something fails:
- ruff/ruff-format may auto-fix Python files → re-stage and commit
- The scrub hook should NOT trigger on this repo (we already cleaned up)

- [ ] **Step 4: Commit any auto-fixes + the config file**

```bash
git add .pre-commit-config.yaml
# if pre-commit auto-fixed anything:
git add -u
git commit -m "chore: add pre-commit config (scrub + ruff + basic hygiene)"
git push origin main
```

Expected: commit + push succeed.

---

### Task 11: Local Docker build + dev validation

**Files:** none (validation step)

- [ ] **Step 1: Build upstream EMHASS image from submodule**

```bash
cd C:/Users/MauricioSchäpers/claude-code/emhass-contributions
PIN=$(cd upstream && git describe --tags)
echo "Upstream pin: $PIN"
docker build -t emhass-base:${PIN} -f upstream/Dockerfile upstream/
```

Expected: build succeeds (~5-10 min on first build). Final image tagged `emhass-base:v0.17.2`. If the build fails with TARGETARCH errors, see `upstream/docs/develop.md` § "Issue with TARGETARCH" — likely needs `--build-arg TARGETARCH=<your-arch>`.

- [ ] **Step 2: Build prototype image on top**

```bash
docker build -t emhass-contrib/prod:${PIN}-c1 \
  -f docker/Dockerfile.prototypes \
  --build-arg BASE_IMAGE=emhass-base:${PIN} \
  .
```

Expected: build succeeds (~30 sec — just adds prototypes/ + entrypoint.sh + pyyaml). Final image tagged `emhass-contrib/prod:v0.17.2-c1`.

- [ ] **Step 3: Smoke-test image starts**

```bash
docker run --rm -d --name emhass-contrib-test -p 5050:5000 \
  emhass-contrib/prod:${PIN}-c1
sleep 10
docker logs emhass-contrib-test 2>&1 | tail -30
```

Expected log includes:
- `[contrib-entrypoint] prototypes module imported` (our wrapper ran)
- Banner from PR #806 with EMHASS version + Python + CVXPY (upstream's startup banner)
- Quart server listening message
- No fatal errors (some warnings about missing config are OK in smoke mode)

- [ ] **Step 4: HTTP check**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5050/
```

Expected: `200` (EMHASS web UI responds). Or `404` if no static index — either confirms server is up.

- [ ] **Step 5: Stop test container**

```bash
docker stop emhass-contrib-test
```

Expected: container stopped + auto-removed (`--rm` flag).

- [ ] **Step 6: Run full dev compose**

```bash
docker compose -f docker/compose-dev.yml up -d
sleep 15
docker compose -f docker/compose-dev.yml logs --tail=30
```

Expected: container `emhass-contrib-dev` running on port 5050. Logs show entrypoint + EMHASS banner. No crash.

- [ ] **Step 7: Verify dev flag file is mounted**

```bash
docker exec emhass-contrib-dev cat /app/data/contrib-flags.yaml
```

Expected: shows the dev flag content from `docker/contrib-flags.dev.yaml` (all `enabled: true`).

- [ ] **Step 8: Tear down**

```bash
docker compose -f docker/compose-dev.yml down
```

Expected: dev container stopped + removed.

- [ ] **Step 9: No code changes in this task — record the result and move on**

This is a validation gate. If any of Steps 1–8 failed, fix before proceeding to Phase 5. Capture the build commands as a brief note in `docker/README.md` if anything was non-obvious.

---

## Phase 5 — Production Cutover on Unraid

### Task 12: Repo on Unraid + Production build

**Files:** none (Unraid-side operation)

- [ ] **Step 1: Clone the repo on Unraid**

Via Unraid web Terminal (Settings → Terminal) or `unraid` MCP skill:

```bash
mkdir -p /mnt/user/appdata/emhass-contrib-source
cd /mnt/user/appdata/emhass-contrib-source
git clone https://github.com/OptimalNothing90/emhass-contributions.git .
git submodule update --init --recursive
```

Expected: `/mnt/user/appdata/emhass-contrib-source/` contains the repo + populated `upstream/` submodule. **Note:** this path is for the **build source**, not the EMHASS data (which stays at `/mnt/user/appdata/emhass/`).

- [ ] **Step 2: Verify submodule is at expected pin**

```bash
cd /mnt/user/appdata/emhass-contrib-source/upstream
git describe --tags
```

Expected: `v0.17.2`.

- [ ] **Step 3: Build base image on Unraid**

```bash
cd /mnt/user/appdata/emhass-contrib-source
PIN=$(cd upstream && git describe --tags)
docker build -t emhass-base:${PIN} -f upstream/Dockerfile upstream/
```

Expected: build succeeds (~5-10 min). Image `emhass-base:v0.17.2` exists in local Unraid Docker.

- [ ] **Step 4: Build production image on Unraid**

```bash
docker build -t emhass-contrib/prod:${PIN}-c1 \
  -f docker/Dockerfile.prototypes \
  --build-arg BASE_IMAGE=emhass-base:${PIN} \
  .
```

Expected: build succeeds. Image `emhass-contrib/prod:v0.17.2-c1` exists locally.

- [ ] **Step 5: List images for verification**

```bash
docker images | grep -E "emhass-(base|contrib)"
```

Expected: both `emhass-base:v0.17.2` and `emhass-contrib/prod:v0.17.2-c1` listed.

---

### Task 13: Pre-cutover backup

**Files:** none (Unraid-side operation)

- [ ] **Step 1: Tag current production image as :rollback**

```bash
# Find the existing emhass image tag
EXISTING=$(docker inspect emhass --format '{{.Config.Image}}')
echo "Existing image: $EXISTING"
docker tag "$EXISTING" emhass:rollback
```

Expected: `docker images | grep emhass` shows `emhass:rollback` next to the existing tag.

- [ ] **Step 2: Backup data volume**

```bash
mkdir -p /mnt/user/backups
tar -czf /mnt/user/backups/emhass-pre-contrib-$(date +%Y%m%d).tar.gz \
  -C /mnt/user/appdata emhass/
```

Expected: backup file created at `/mnt/user/backups/emhass-pre-contrib-YYYYMMDD.tar.gz`. Size ~10-100 MB depending on history.

- [ ] **Step 3: Verify backup integrity**

```bash
ls -lh /mnt/user/backups/emhass-pre-contrib-*.tar.gz
tar -tzf /mnt/user/backups/emhass-pre-contrib-$(date +%Y%m%d).tar.gz | head -10
```

Expected: file exists, non-empty, listing shows files inside `emhass/`.

---

### Task 14: Cutover

**Files:** none (Unraid-side operation)

- [ ] **Step 1: Capture environment from existing container**

```bash
docker inspect emhass --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E "^(URL|KEY|TIME_ZONE|LAT|LON|ALT)=" \
  > /tmp/emhass.env
cat /tmp/emhass.env
```

Expected: lines like `URL=https://...`, `KEY=...`, `LAT=...`. Save these for the new compose `--env-file`.

- [ ] **Step 2: Stop + remove old container**

```bash
docker stop emhass
docker rm emhass
```

Expected: both succeed. `docker ps -a | grep emhass` no longer shows the running container (rollback tag still present as image).

- [ ] **Step 3: Start new container via compose**

```bash
cd /mnt/user/appdata/emhass-contrib-source
docker compose --env-file /tmp/emhass.env -f docker/compose-prod.yml up -d
```

Expected: new container `emhass` starts. `docker ps | grep emhass` shows it running on port 5000.

- [ ] **Step 4: Tail logs immediately**

```bash
docker logs emhass --tail 50 -f
```

Expected within ~30 seconds:
- Entrypoint banner: `[contrib-entrypoint] prototypes module imported`
- Upstream banner (PR #806): EMHASS version + Python + CVXPY + solver + platform
- Quart server listening on port 5000

Press Ctrl+C after the banner appears and the server starts listening.

- [ ] **Step 5: HTTP check**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5000/
```

Expected: `200` (or `401` if auth is on — that's also fine, server is up).

---

### Task 15: Validate (35 min watchdog window)

**Files:**
- Create (Unraid): `/mnt/user/appdata/emhass/contrib-flags.yaml`

- [ ] **Step 1: Create flags file with everything off**

On Unraid:

```bash
cat > /mnt/user/appdata/emhass/contrib-flags.yaml << 'YAML'
# Production flags — start everything OFF.
# Activate one at a time after >=7 days production-stable soak.
prototypes:
  api_last_run:
    enabled: false
  api_healthz:
    enabled: false
  openapi_gen:
    enabled: false

logging:
  level: INFO
YAML

cat /mnt/user/appdata/emhass/contrib-flags.yaml
```

Expected: file exists, all `enabled: false`.

- [ ] **Step 2: Verify EMHASS sees the file**

```bash
docker exec emhass cat /app/data/contrib-flags.yaml
```

Expected: same content as host file (volume mount works).

- [ ] **Step 3: Verify the flags module reads it without error**

```bash
docker exec emhass python -c "from prototypes import flags; print('api_last_run:', flags.is_enabled('api_last_run')); print('api_healthz:', flags.is_enabled('api_healthz'))"
```

Expected:
```
api_last_run: False
api_healthz: False
```

- [ ] **Step 4: Wait for next MPC cycle**

Node-RED triggers MPC every 15 min on the quarter-hour. After cutover, next cycle should run within 15 min.

```bash
# Watch for cycle_ok publish via mqtt or via NR debug — depends on your stack
# Or watch the action log:
docker exec emhass tail -f /app/data/action_logs.txt
```

Expected: within 15 min, banner appears at run start; at end, summary line shows total runtime + dominant stage. No error lines.

- [ ] **Step 5: Watchdog status check**

CE-3 watchdog publishes `emhass/watchdog/status` after each MPC cycle:
- `0` = OK
- `1` = WARN (>35min no cycle_ok)
- `2` = CRITICAL (>65min no cycle_ok)

After ≥1 successful MPC cycle post-cutover, watchdog status should be `0`. WARN within the first 35 min is expected (cycle hadn't completed yet) and is informational only — soak continues.

- [ ] **Step 6: Run /diagnose skill from Claude Code**

In a Claude Code session in loxonesmarthome:

```
/diagnose
```

Expected: green output (or only the same warnings as pre-cutover — anything new = investigate).

- [ ] **Step 7: 7-day soak with all flags off — DO NOTHING**

For at least 7 days, observe:
- Daily MPC cycles complete normally
- Watchdog stays at 0 (OK) most of the time (transient WARN at boundaries OK)
- Heating, battery, EV behavior all unchanged from pre-cutover

If any major regression: rollback via `docker stop emhass && docker rm emhass && docker run -d --name emhass --restart unless-stopped -p 5000:5000 -v /mnt/user/appdata/emhass:/app/data emhass:rollback`. Restore data from backup if data corruption suspected.

---

## Phase 6 — Cleanup & Cross-References

### Task 16: Update board card bodies with new repo URLs

**Files:**
- Modify: `loxonesmarthome/docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json` (sync)
- Mutation via gh graphql for affected board cards

Some board cards reference paths like `docs/superpowers/specs/...` (implicitly loxonesmarthome). After migration, those should point to `https://github.com/OptimalNothing90/emhass-contributions/...`.

- [ ] **Step 1: Switch to OptimalNothing90 + identify cards with stale paths**

```bash
cd C:/Users/MauricioSchäpers/claude-code/loxonesmarthome
gh auth switch --user OptimalNothing90
```

Then run a one-off scan of items.json:

```bash
python -c "
import json
with open('docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json', encoding='utf-8') as f:
    d = json.load(f)
for it in d['items']:
    body = it.get('body', '')
    if 'docs/superpowers/specs/' in body:
        print(it['id'], '— references docs/superpowers/specs/')
"
```

Expected output: list of IDs with stale references (likely AC-2, AC-2a, AG-7, AG-onboarding, others).

- [ ] **Step 2: Write update script**

Create `loxonesmarthome/docs/superpowers/specs/cross-ref-update.py`:

```python
#!/usr/bin/env python3
"""After migration, replace docs/superpowers/specs/ references in card bodies
with URLs pointing at the new public emhass-contributions repo."""
import json
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_FILE = Path(__file__).parent / "2026-04-28-emhass-board-migration-items.json"
NEW_REPO_BASE = "https://github.com/OptimalNothing90/emhass-contributions/blob/main"

# Map old paths to new ones (per spec section 4.2 migration table)
PATH_MAP = {
    "docs/superpowers/specs/2026-04-28-emhass-ai-agents-board-design.md": "board/design.md",
    "docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json": "board/items.json",
    "docs/superpowers/specs/2026-04-28-param-definitions-audit.md": "audits/2026-04-28-param-definitions.md",
    "docs/superpowers/specs/2026-04-28-plan-output-audit.md": "audits/2026-04-28-plan-output.md",
    "docs/superpowers/specs/migrate-emhass-board.py": "board/migrate.py",
    "docs/superpowers/specs/update-emhass-board.py": "board/update.py",
    "docs/superpowers/specs/extend-board-ai-contributor.py": "board/extend.py",
    "docs/superpowers/specs/fix-private-repo-leaks.py": "board/fix-leaks.py",
}


def fetch_draft_ids():
    q = '''{
      node(id: "PVT_kwHOAfZrVs4BV1jU") {
        ... on ProjectV2 { items(first: 100) {
          nodes { content { ... on DraftIssue { id title } } }
        } } } }'''
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}"],
                       capture_output=True, text=True, encoding="utf-8")
    return {n["content"]["title"]: n["content"]["id"]
            for n in json.loads(r.stdout)["data"]["node"]["items"]["nodes"]
            if n.get("content") and n["content"].get("title")}


def update_draft(draft_id, body):
    q = f'''mutation($body: String!) {{
      updateProjectV2DraftIssue(input: {{
        draftIssueId: "{draft_id}"
        body: $body
      }}) {{ draftIssue {{ title }} }}
    }}'''
    r = subprocess.run(["gh", "api", "graphql", "-f", f"query={q}", "-f", f"body={body}"],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return json.loads(r.stdout)["data"]["updateProjectV2DraftIssue"]["draftIssue"]["title"]


def main():
    with DATA_FILE.open(encoding="utf-8") as f:
        data = json.load(f)

    titles_to_ids = fetch_draft_ids()
    updates = []

    for item in data["items"]:
        if item.get("type") != "draft":
            continue
        body = item.get("body", "")
        new_body = body
        for old, new in PATH_MAP.items():
            new_body = new_body.replace(old, f"{NEW_REPO_BASE}/{new}")
        if new_body == body:
            continue

        draft_id = titles_to_ids.get(item["title"])
        if not draft_id:
            print(f"  skip {item['id']} — title not found on board")
            continue
        update_draft(draft_id, new_body)
        item["body"] = new_body
        updates.append(item["id"])
        print(f"  updated {item['id']}")

    if updates:
        with DATA_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"items.json synced ({len(updates)} cards updated)")
    else:
        print("No updates needed.")


if __name__ == "__main__":
    main()
```

Write the file.

- [ ] **Step 3: Dry-run check**

Add a `--dry-run` flag to inspect first:

```bash
python -c "
import json
with open('docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json', encoding='utf-8') as f:
    d = json.load(f)
PATH_MAP = {
    'docs/superpowers/specs/2026-04-28-emhass-ai-agents-board-design.md': 'board/design.md',
    'docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json': 'board/items.json',
    'docs/superpowers/specs/2026-04-28-param-definitions-audit.md': 'audits/2026-04-28-param-definitions.md',
    'docs/superpowers/specs/2026-04-28-plan-output-audit.md': 'audits/2026-04-28-plan-output.md',
    'docs/superpowers/specs/migrate-emhass-board.py': 'board/migrate.py',
    'docs/superpowers/specs/update-emhass-board.py': 'board/update.py',
    'docs/superpowers/specs/extend-board-ai-contributor.py': 'board/extend.py',
    'docs/superpowers/specs/fix-private-repo-leaks.py': 'board/fix-leaks.py',
}
for it in d['items']:
    body = it.get('body','')
    matches = [k for k in PATH_MAP if k in body]
    if matches:
        print(it['id'], 'will replace:', matches)
"
```

Expected: list of cards that would change. Review.

- [ ] **Step 4: Run the update**

```bash
python docs/superpowers/specs/cross-ref-update.py
```

Expected: list of updated cards. items.json synced.

- [ ] **Step 5: Commit + push the updated items.json + script**

```bash
git add docs/superpowers/specs/2026-04-28-emhass-board-migration-items.json \
        docs/superpowers/specs/cross-ref-update.py
git commit -m "chore(board): replace loxonesmarthome path refs with public repo URLs

Card bodies that referenced docs/superpowers/specs/<file> now point at
https://github.com/OptimalNothing90/emhass-contributions/blob/main/<new-path>.
Script for reproducibility."
git push origin master
```

Expected: push succeeds.

---

### Task 17: Memory + loxonesmarthome README updates

**Files:**
- Modify: `~/.claude/projects/.../memory/project_emhass_upstream.md`
- Modify: `loxonesmarthome/README.md` (or create if missing)

- [ ] **Step 1: Append a section to project_emhass_upstream.md memory**

```bash
cat >> "C:/Users/MauricioSchäpers/.claude/projects/C--Users-MauricioSch-pers-claude-code-loxonesmarthome/memory/project_emhass_upstream.md" << 'MD'

## emhass-contributions repo (NEW 2026-04-28)

Public repo `OptimalNothing90/emhass-contributions` is the new home for:
- audits + reproducer scripts
- board source-of-truth (design.md, items.json, mutation scripts)
- design RFCs for upstream features
- prototypes (feature-flagged Python additions, off by default)
- Docker build for the production EMHASS image running on Unraid

Submodule: `upstream/` → `https://github.com/davidusb-geek/emhass.git` pinned to release tags only.

Local workdir: `C:/Users/MauricioSchäpers/claude-code/emhass-contributions/`.

Workflow:
- Spec/RFC/audit work → emhass-contributions
- Source PRs → OptimalNothing90/emhass fork → davidusb-geek/emhass
- Loxone/NR/private setup → loxonesmarthome (this repo)

Production: `emhass` container on Unraid runs `emhass-contrib/prod:<upstream-tag>-c<rev>`. Flags toggled via `/mnt/user/appdata/emhass/contrib-flags.yaml`. Default all-off; rollback tag `emhass:rollback` ready in <2 min.

Spec: see `docs/superpowers/specs/2026-04-28-emhass-contributions-repo-design.md` (this repo) — also mirrored once migration completes.
MD
```

Expected: section appended at the end of the memory file.

- [ ] **Step 2: Update loxonesmarthome README.md**

Check if README.md exists:

```bash
ls C:/Users/MauricioSchäpers/claude-code/loxonesmarthome/README.md
```

If it exists, append the cross-reference section. If not, create a minimal one.

If creating new:

```bash
cat > C:/Users/MauricioSchäpers/claude-code/loxonesmarthome/README.md << 'MD'
# loxonesmarthome

Private smarthome configuration repository.

## Scope

This repo contains private smarthome setup:
- Loxone configuration (`loxone/Schäpers_Ottenhofen.Loxone`)
- Node-RED flows (`nodered/flows.json`)
- EMHASS personal config (`emhass/config.json`)
- Local Claude Code skills (`.claude/skills/`)

## Where EMHASS contribution work lives

EMHASS contribution work — audits, design RFCs, project board source-of-truth, the production Docker build — lives in **[OptimalNothing90/emhass-contributions](https://github.com/OptimalNothing90/emhass-contributions)** (public).

This repo (loxonesmarthome) is private and stays private. Anything that contributes back upstream goes through the public repo or directly through the fork at [OptimalNothing90/emhass](https://github.com/OptimalNothing90/emhass).
MD
```

If updating existing, append a section about emhass-contributions cross-reference.

- [ ] **Step 3: Commit + push**

```bash
cd C:/Users/MauricioSchäpers/claude-code/loxonesmarthome
git add README.md
git commit -m "docs: add cross-reference to emhass-contributions repo"
git push origin master
```

Expected: push succeeds.

(Memory file is not in git — it's auto-saved by Claude infrastructure.)

---

### Task 18: Delete migrated files from loxonesmarthome

**Files:**
- Delete: 8 files in `loxonesmarthome/docs/superpowers/specs/`

- [ ] **Step 1: Verify the files are mirrored in emhass-contributions on GitHub**

```bash
gh api /repos/OptimalNothing90/emhass-contributions/contents/board/items.json --jq '.size' 2>&1 | head -1
gh api /repos/OptimalNothing90/emhass-contributions/contents/board/design.md --jq '.size' 2>&1 | head -1
gh api /repos/OptimalNothing90/emhass-contributions/contents/audits/2026-04-28-param-definitions.md --jq '.size' 2>&1 | head -1
```

Expected: all three return non-zero sizes (files exist on the public repo).

- [ ] **Step 2: Delete the 8 files locally**

```bash
cd C:/Users/MauricioSchäpers/claude-code/loxonesmarthome/docs/superpowers/specs
rm 2026-04-28-emhass-ai-agents-board-design.md
rm 2026-04-28-emhass-board-migration-items.json
rm 2026-04-28-param-definitions-audit.md
rm 2026-04-28-plan-output-audit.md
rm migrate-emhass-board.py
rm update-emhass-board.py
rm extend-board-ai-contributor.py
rm fix-private-repo-leaks.py
```

Expected: 8 files removed from the directory. The `2026-04-28-emhass-contributions-repo-design.md` and other helper scripts (`update-board-developmd-insights.py`, `cross-ref-update.py`) **stay** — they belong in loxonesmarthome (this is where the design conversation lives, before the new repo existed).

- [ ] **Step 3: Verify the spec design files stay**

```bash
ls C:/Users/MauricioSchäpers/claude-code/loxonesmarthome/docs/superpowers/specs/
```

Expected: `2026-04-28-emhass-ai-agents-board-design.md` is gone (migrated as `board/design.md`). What remains:
- `2026-04-28-battery-capacity-runtimeparam-design.md` (older, unrelated)
- `2026-04-28-emhass-contributions-repo-design.md` (this design — stays)
- helper scripts that already produced their effect (`update-board-developmd-insights.py`, `extend-board-ai-contributor.py` was migrated to `board/`)

- [ ] **Step 4: Commit deletions + push**

```bash
cd C:/Users/MauricioSchäpers/claude-code/loxonesmarthome
git add -u docs/superpowers/specs/
git status --short
git commit -m "chore: remove files migrated to emhass-contributions repo

8 files moved to https://github.com/OptimalNothing90/emhass-contributions:
- 2026-04-28-emhass-ai-agents-board-design.md → board/design.md
- 2026-04-28-emhass-board-migration-items.json → board/items.json
- 2026-04-28-param-definitions-audit.md → audits/2026-04-28-param-definitions.md
- 2026-04-28-plan-output-audit.md → audits/2026-04-28-plan-output.md
- migrate-emhass-board.py → board/migrate.py
- update-emhass-board.py → board/update.py
- extend-board-ai-contributor.py → board/extend.py
- fix-private-repo-leaks.py → board/fix-leaks.py"
git push origin master
```

Expected: push succeeds. loxonesmarthome cleanup complete.

---

### Task 19: Final verification + account-hygiene

**Files:** none (verification only)

- [ ] **Step 1: Verify GitHub state of new repo**

```bash
gh repo view OptimalNothing90/emhass-contributions --web
```

Expected (in browser): repo shows README, AGENTS.md, all directories. Submodule shows `upstream @ v0.17.2`. License shown.

- [ ] **Step 2: Verify Unraid container running**

```bash
ssh-or-mcp unraid -> docker ps | grep emhass
ssh-or-mcp unraid -> docker logs emhass --tail 5
```

Expected: container running, recent log lines show normal MPC operation.

- [ ] **Step 3: Verify NR + Loxone reach EMHASS**

In Node-RED debug:
- Latest MPC POST to `http://<unraid-ip>:5000/action/naive-mpc-optim` returns 201
- Watchdog publishes cycle_ok within last 15 min

In Loxone:
- EMHASS-related virtual inputs receive normal updates

- [ ] **Step 4: Switch back to mschaepers**

```bash
gh auth switch --user mschaepers
gh auth status | head -8
```

Expected: `mschaepers` is active account.

- [ ] **Step 5: Final summary commit on loxonesmarthome (if anything still uncommitted)**

```bash
cd C:/Users/MauricioSchäpers/claude-code/loxonesmarthome
git status --short
```

Expected: only `M loxone/Schäpers_Ottenhofen.Loxone` and `?? evcc_state.json` (the usual session-touched files unrelated to this work). Nothing else uncommitted.

If any project-specific uncommitted changes remain, commit them with an appropriate message.

---

## Done state

After all 19 tasks:

- ✅ Public repo `OptimalNothing90/emhass-contributions` exists with full skeleton, submodule, migrated content, Docker build pipeline, prototypes/flags.py module with passing tests, pre-commit hook
- ✅ Production EMHASS on Unraid runs `emhass-contrib/prod:v0.17.2-c1` with all flags off — byte-equivalent to vanilla EMHASS
- ✅ Rollback tag `emhass:rollback` available; data backup stored
- ✅ Board cards reference public repo URLs
- ✅ Memory updated; loxonesmarthome README has cross-reference; 8 migrated files removed from loxonesmarthome
- ✅ Account back on `mschaepers`

Next steps (out of scope for this plan, future board cards):
- 7-day soak with all flags off
- Then: file an issue + RFC for `/api/last-run` (board card AC-3) → activate `api_last_run` flag in production → validate → upstream PR
- Same pattern for other prototypes
- Port `audits/reproducer.py` from earlier session output (separate plan if substantial)

---

## Self-review

**Spec coverage check:**
- §1 Goal & Constraints: Tasks 1-3 (repo creation), Task 5-7 (Docker), Task 11 (validation), Task 14 (cutover). ✅
- §2 Repo Structure + Submodule Policy: Task 2 (skeleton), Task 3 (submodule), Task 4 (migration directories). ✅
- §3 Docker Architecture + Feature Flags: Task 5-7 (Docker), Task 8-9 (flags.py module). ✅
- §4 Production Deployment + Migration: Task 4 (migration), Task 12-15 (Unraid build + cutover + validate). ✅
- §5 Risks + Cross-Repo Governance: addressed by Task 13 (backup), Task 14 (cutover with rollback path), Task 15 (watchdog soak), Task 19 (account hygiene). ✅
- §6 Apply Plan: this plan IS the detailed apply plan. ✅
- §7 Decisions Captured: HTTPS submodule (Task 3), GPL-3.0 (Task 1 via --license), build-on-Unraid (Task 12), immediate cutover (Task 14), pre-commit hook (Task 10), .gitattributes (Task 2). ✅

**Placeholder scan:** No "TBD" / "TODO" / vague "implement appropriate" — every step has actual content or commands. The audits/reproducer.py port is explicitly out of scope (called out in Task 4 Step 4 and Done State).

**Type / signature consistency:** `flags.is_enabled(feature)` is called consistently in Task 8 (tests), Task 9 (`__init__.py` re-export), Task 15 Step 3 (verification). `flags.get_setting(feature, key, default)` consistent in Task 8 Step 13.

**Identified follow-ups for separate plans:**
- `audits/reproducer.py` port — substantial work; separate plan when re-running audit becomes worth automating
- First prototype implementation (e.g. `api_last_run.py`) — separate plan with its own RFC + flag-on rollout
- Public skill plugin distribution (AG-B1) — separate plan when first skill is anonymized
