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
