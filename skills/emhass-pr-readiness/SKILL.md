---
name: emhass-pr-readiness
description: Use before opening, pushing or asking for review on a pull request to davidusb-geek/emhass (or a fork of it) - "is my EMHASS PR ready", "pre-PR check", "what do I need before gh pr create", or when a change touches param_definitions.json, config_defaults.json, associations.csv, openapi.json, optimization.py, forecast.py, command_line.py, action_logs format or CHANGELOG.md. Also when ruff or the openapi drift test fails in upstream CI.
---

# EMHASS pull-request readiness

Upstream CI runs `ruff check`, `ruff format --check`, pytest on three OSes, Sourcery
and CodeQL. The maintainer additionally reviews against `AGENTS.md` and `docs/develop.md`.
Run the mechanical part with the bundled script, then walk the judgement checklist.

## 1. Mechanical checks (script)

Run inside the fork checkout, on the branch you want to push:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/pr_readiness.sh [--base origin/master] [--full-tests | --no-tests]
```

It prints `[OK] / [WARN] / [FAIL]` lines and exits 1 on any FAIL:

- branch name prefix `fix/`, `feat/`, `docs/`, `chore/` (maintainer commit convention)
- `ruff check .` and `ruff format --check .` with the repo's own `pyproject.toml`
- `param_definitions.json` additive only: no key removed, no `input` kind changed
  (AGENTS.md don't-touch rule 4); when a key is added, `config_defaults.json` and
  `associations.csv` must change in the same diff
- `openapi.json` regenerated when `param_definitions.json`, `runtime_params.json`,
  `docs/api/*.schema.json` or `scripts/generate_openapi.py` changed
  (`tests/test_openapi.py` fails on drift)
- `CHANGELOG.md` not touched (the maintainer generates it at release time with
  `scripts/generate_changelog.py`)
- privacy lint on the diff: private IPs, long-lived tokens, `Bearer` strings, personal
  hostnames, home-automation-specific paths
- tests: `tests/test_<module>.py` for every changed `src/emhass/<module>.py`
  (`--full-tests` runs everything, `--no-tests` skips)
- behaviour change in `optimization.py`, `forecast.py`, `retrieve_hass.py` beyond ~3
  lines without a test file in the diff → WARN (issue-first per AGENTS.md § 5)

## 2. Judgement checklist (you)

Quote from upstream `AGENTS.md` at v0.18.6, section 5, verbatim:

> **Add parameter:** four-step workflow in `docs/develop.md` (`associations.csv` +
> `config_defaults.json` + `param_definitions.json` + cache-key check, optional
> `check_def_loads`). Structural `plant_conf`/`optim_conf` keys are already covered by
> `plant_conf_hash`/`optim_conf_structural_hash` (minus the runtime-keys exclusions); add
> an explicit `OptimizationCacheKey` field only when they are not — test that a value
> change changes the key. Skip step → breaks something.

> **Change default value (existing param):** `src/emhass/static/data/param_definitions.json`
> first — source of truth. Align `src/emhass/data/config_defaults.json` to match.

- [ ] **Issue first?** Visible behaviour change, magic constant, sign convention, or
      >3 lines in `optimization.py` / `retrieve_hass.py` / `forecast.py` → open an issue
      before the PR (AGENTS.md § 5). Link it in the PR body.
- [ ] **Four-step parameter workflow** done when a param was added (above); for a
      structural param add a test that changing its value changes the cache key.
- [ ] **`action_logs.txt` line format unchanged** (`<LEVEL> - <logger> - <message>`;
      web_server splits on the first space and compares to `ERROR`).
- [ ] **Opt-result columns and units unchanged**; new columns only additive.
- [ ] **Zero-config default still works**: `docker compose up` + config page loads, a
      `dayahead-optim` on defaults returns Optimal.
- [ ] **Scope corridors**: no Home Assistant / Node-RED / EVCC / OCPP specific code in
      core (#789), no new filesystem/shell/DB endpoints without maintainer sign-off (#808),
      no new dependency without an issue.
- [ ] **Test reproducer** present for every behaviour-change PR; smoke-tested the web UI
      when `web_server.py` or a schema file changed.
- [ ] **Docs** updated where the behaviour is documented (`docs/*.md`, `passing_data.md`
      for runtime keys); no restating of the forecast contract, link to it.
- [ ] **Commit prefix** `fix` / `feat` / `docs` / `chore`; one topic per PR.
- [ ] **Draft first**: open with `gh pr create --draft`, let CI run, then mark ready.
      Never enable auto-merge; never edit `CHANGELOG.md`.
- [ ] **Account**: `gh auth status` shows the account that owns the fork before `git push`.

## 3. PR body

Title `<prefix>: <imperative summary>`. Body: what changed, why (link issue), how tested
(command + result), schema / docs touched, anything the maintainer must decide.
Keep it under ~300 words; the diff is the detail.

## Not covered

Code review quality itself (use a reviewer), mypy / type coverage (not enforced
upstream), SonarCloud (fails on fork PRs regardless, ignore).
