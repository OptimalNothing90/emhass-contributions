---
name: emhass-config-validate
description: Use when an EMHASS user asks to check, validate, lint or review their config.json / config.yaml / runtimeparams before saving, pushing or deploying; when EMHASS logs "unknown parameter", padded arrays, "not a fraction", infeasible right after a config change; or before answering "is my EMHASS config correct". Stack-agnostic, works on any EMHASS v0.18.x install.
---

# EMHASS config validation

Run the bundled validator instead of eyeballing the file. It checks every key
against EMHASS's own `param_definitions.json`, `runtime_params.json`,
`config_defaults.json` and `associations.csv` (v0.18.6 copies ship with the skill).

## Run

```bash
python ${CLAUDE_SKILL_DIR}/scripts/validate_config.py <config.json|config.yaml> [--runtime runtimeparams.json] [--schema-dir <dir>] [--quiet]
```

- `config` = the file EMHASS reads: `config.json` (add-on / web UI save) or a legacy
  sectioned `config_emhass.yaml` (auto-flattened, legacy names mapped).
- `--runtime` = the JSON body you POST to `/action/<name>` (prediction_horizon,
  soc_init, forecasts, per-load overrides).
- `--schema-dir` = only for another EMHASS version. Export the four files from the
  installed package (`src/emhass/static/data/param_definitions.json`,
  `runtime_params.json`, `src/emhass/data/config_defaults.json`, `associations.csv`)
  into one directory and point here.

Stdlib Python 3.10+. PyYAML is optional (a minimal built-in YAML reader is used otherwise).

## Read the output

One finding per line: `SEVERITY key: message`, sorted ERROR, WARN, INFO. Last line
`OK:`/`FAIL:` with counts. Exit 1 on any ERROR, 2 when a file cannot be read.

| Severity | Meaning | What to do |
|---|---|---|
| ERROR | EMHASS will reject the value or produce a wrong/infeasible plan | Fix before running |
| WARN | EMHASS silently pads, clamps, ignores or rounds | Confirm intent, usually fix |
| INFO | Harmless (null falls back to default, legacy runtime alias) | Mention only if asked |

Checks performed: unknown / misspelled / legacy keys (with closest match), type per
`input` kind, `select_options`, per-load array length vs `number_of_deferrable_loads`,
per-battery list length vs `number_of_batteries` (scalars broadcast), SOC fractions in
[0, 1] and min ≤ target ≤ max, hybrid inverter with `inverter_ac_output_max` /
`inverter_ac_input_max` = 0 (issue #875 trap: everything pinned to 0 W), semi-continuous
loads whose `operating_hours` are not whole timesteps, operating hours longer than the
horizon, end timestep before start, `optimization_time_step` not dividing an hour,
runtime forecasts with NaN/null, `prediction_horizon` < 5.

## Workflow

1. Run the validator on the file the user named. If they only pasted JSON, write it to a
   temp file first (any scratch location; the script only reads it).
2. Findings are sorted by severity, then alphabetically by key, not by importance. Start
   from the ERROR that matches the user's symptom, then the rest. Report each key once:
   a WARN on the same key as an ERROR (e.g. target SOC "outside [20, 0.9]" after a
   percent-instead-of-fraction ERROR) is a consequence, not a second problem.
3. Then WARNs on other keys that change behaviour.
4. Do not restate INFO lines unless the user asks why a value "does nothing".
5. If `unknown key` fires on a key the user insists exists: ask which EMHASS version runs,
   then re-run with `--schema-dir` pointing at that version's files. Never edit the
   bundled schema.
6. The validator does not know the user's sensors, tariff or hardware. "No errors" means
   the file is schema-valid, not that the plant model is right.

## Not covered

Secrets (`secrets_emhass.yaml`, add-on `options.json`), Home Assistant entity existence,
Solcast quota, solver availability. For runtime failures use `emhass-anomaly`; for
"why is the plan like this" use `emhass-plan-explain`.
