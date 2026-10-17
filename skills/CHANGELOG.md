# Changelog — emhass-skills plugin

All notable changes to the `skills/` plugin. Versioning follows the plugin's
`version` in `.claude-plugin/plugin.json`, independent of the EMHASS release the
bundled schema files come from.

## 0.1.0 — 2026-10-17

First public release. All scripts are stdlib Python 3.10+ and work against a vanilla
EMHASS v0.18.6 install through its public surfaces only (`GET /api/v1/plan`,
`GET /api/v1/last-run`, `GET /healthz`, `action_logs.txt`, the schema files under
`src/emhass/static/data` and `src/emhass/data`).

- `emhass-config-validate`: `validate_config.py` checks config.json / config.yaml and
  runtime params against `param_definitions.json`, `runtime_params.json`,
  `config_defaults.json`, `associations.csv` (v0.18.6 copies bundled). Unknown and legacy
  keys, input types, select options, per-load and per-battery array lengths, SOC
  fractions, hybrid-inverter zero AC max (#875), semi-continuous operating hours, window
  sanity, runtime forecasts with NaN, `prediction_horizon` minimum.
- `emhass-plan-explain`: `explain_plan.py` summarises `/api/v1/plan` (+ `/api/v1/last-run`,
  config.json) per deferrable load and battery, with cheapest-hours reasoning and window
  clamping.
- `emhass-anomaly`: `scan_logs.py` classifies the v0.18.6 failure signatures in
  `action_logs.txt` / `logger_emhass.log` with counts, first/last position and a hint.
- `emhass-pr-readiness`: checklist quoting upstream `AGENTS.md`, plus `pr_readiness.sh`
  and `check_param_definitions.py` for the mechanical pre-PR checks in a fork checkout.
- Plugin manifest (`skills/.claude-plugin/plugin.json`) and repo-root marketplace
  (`.claude-plugin/marketplace.json`); 106 pytest cases under `skills/tests/`.
