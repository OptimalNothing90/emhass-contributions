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
