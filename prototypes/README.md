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
