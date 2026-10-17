# emhass-skills — Claude Code plugin for EMHASS

Public, stack-agnostic skills for anyone running [EMHASS](https://github.com/davidusb-geek/emhass)
(v0.18.x) or contributing to it. No Home Assistant integration, no vendor API and no
personal tooling is required: every helper reads EMHASS's own files and read-only JSON
endpoints.

| Skill | Ask Claude when… | Helper |
|---|---|---|
| `emhass-config-validate` | "is my config.json / runtimeparams correct?" before saving or deploying | `validate_config.py` |
| `emhass-plan-explain` | "why does my dishwasher not run tonight?", "why is the battery charging from the grid?" | `explain_plan.py` |
| `emhass-anomaly` | a run failed: Infeasible, relaxed, NaN forecast, sensor not found, Solcast 402/429, 400 on runtimeparams, websocket, cache misses | `scan_logs.py` |
| `emhass-pr-readiness` | before `gh pr create` against `davidusb-geek/emhass` | `pr_readiness.sh`, `check_param_definitions.py` |

Each skill is a folder with a `SKILL.md` (when to use it, how to read the output) and
`scripts/` (stdlib Python 3.10+, no pip installs; PyYAML only if you validate YAML configs).

## Install

From a Claude Code session:

```
/plugin marketplace add OptimalNothing90/emhass-contributions
/plugin install emhass-skills@emhass-contributions
```

Or from the shell:

```bash
claude plugin marketplace add OptimalNothing90/emhass-contributions
claude plugin install emhass-skills@emhass-contributions --scope user
```

Pin a revision with `OptimalNothing90/emhass-contributions#<tag-or-sha>`. The marketplace
file lives at the repo root (`.claude-plugin/marketplace.json`); the plugin root is this
`skills/` folder (`skills/.claude-plugin/plugin.json`).

### Try it without installing

```bash
git clone https://github.com/OptimalNothing90/emhass-contributions
cd emhass-contributions
claude --plugin-dir ./skills
```

The skills then show up as `/emhass-skills:<skill-name>`. After editing a SKILL.md run
`/reload-plugins`.

### Use the scripts without Claude

They are plain CLIs:

```bash
python skills/emhass-config-validate/scripts/validate_config.py config.json --runtime runtimeparams.json
python skills/emhass-plan-explain/scripts/explain_plan.py http://emhass-host:5000/api/v1/plan --config config.json
python skills/emhass-anomaly/scripts/scan_logs.py /path/to/action_logs.txt
bash   skills/emhass-pr-readiness/scripts/pr_readiness.sh   # inside an EMHASS fork checkout
```

## EMHASS version

The bundled schema copies and the log signatures are taken from EMHASS **v0.18.6**
(`src/emhass/static/data/param_definitions.json`, `runtime_params.json`,
`src/emhass/data/config_defaults.json`, `associations.csv`). For another version pass
`--schema-dir` to the validator with that version's files; newer log messages show up
as `unclassified_error` in the scanner.

## Development

```bash
python -m venv skills/.venv
skills/.venv/Scripts/python.exe -m pip install pytest pyyaml ruff   # Windows; use bin/python elsewhere
skills/.venv/Scripts/python.exe -m pytest skills/tests -q
```

CI: `.github/workflows/skills-tests.yml`. Scripts are linted with the repo's ruff
pre-commit hook. Never commit private hosts, tokens or home-automation specifics;
`scripts/scrub-private-refs.py` runs on every commit.

Changes: [`CHANGELOG.md`](CHANGELOG.md).

## Licence

GPL-3.0, like this repository and EMHASS itself. The bundled schema files under
`emhass-config-validate/schema/` are verbatim copies from EMHASS and keep their upstream
licence and copyright.
