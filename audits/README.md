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
