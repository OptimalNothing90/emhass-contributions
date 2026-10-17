# Quickstart

About 10 minutes from a clean checkout to a running system with one demand scheduled.

## 1. Prerequisites

- Docker and the `docker compose` plugin (Docker Desktop on Windows/macOS, or `docker-ce` +
  `docker-compose-plugin` on Linux).
- Nothing else — the bundle below brings its own EMHASS and (optionally) its own MQTT broker.

## 2. Get the config

```bash
git clone https://github.com/OptimalNothing90/emhass-contributions.git
cd emhass-contributions/prototypes/flexd
cp flexd.yaml.example flexd.yaml
```

Open `flexd.yaml` and work through it top to bottom:

- `emhass_url` — where flexd reaches EMHASS. The compose bundle below sets this via
  `FLEXD_EMHASS_URL`, so leave the file's value as-is unless you're running flexd outside compose.
- `timestep_min` — **must equal** the `optimization_time_step` in your EMHASS config. flexd
  builds its runtimeparams around this value; a mismatch does not raise an error, it just makes
  the plan wrong. Check `emhass/config_emhass.yaml` (or your EMHASS `config.json`) for the value
  currently in use and copy it here.
- `horizon_steps` — how many timesteps ahead flexd asks EMHASS to plan. 48 steps at a 30-minute
  timestep is a 24 h horizon; adjust together with your EMHASS `optimization_time_step` if you
  change either.
- `timezone` — an IANA name (e.g. `Europe/Berlin`). Used to interpret standing-demand windows
  and trigger-template deadline rules in local time; everything else in flexd is UTC internally.
- `data_dir` — leave as `/data` inside the container; it's where `demands.json`,
  `standing_ledger.json`, `adopted_plan.json` and `last_cycle.json` live
  (see step 7).
- `ts_round` — must match `method_ts_round` in the EMHASS config (default `nearest` in both).
  flexd anchors its timestep grid on the same rounding rule EMHASS applies to the first
  optimization step, so start and end slots line up with the plan EMHASS returns.
- `stale_after_cycles` / `default_ttl_s` — safe to leave at their defaults for a first run.
- `max_demands` (default 32) — registering a new id beyond this many active demands returns
  `409`, so one misbehaving client cannot grow the registry and the optimization without limit.
  `expires_at` is also capped at one year from now on registration.
- `save_debounce_s` (default 5) — refreshes inside this window are written to `demands.json`
  once, together, instead of rewriting the file on every refresh (SD-card hosts). Registrations
  and withdrawals are written immediately.
- `mqtt:` block — only needed if you plan to use MQTT (Home Assistant, ioBroker). Set
  `enabled: true` and point `host`/`port` at your broker, or leave the bundled Mosquitto profile
  (step 4) running and keep `host: mosquitto`. Loxone and plain REST/agent use don't need this.
- `extra_runtime_params` — advanced escape hatch merged into every EMHASS optim call (e.g.
  `soc_init`). Leave commented out to start.
- `standing_demands:` / `templates:` — both optional and commented out by default. They cover
  recurring daily loads (water heater) and event-triggered appliances (dishwasher) respectively.
  Skip these for the first run; see the [Home Assistant guide](clients/home-assistant.md) for a
  worked `templates:` example once you're past this quickstart.

## 3. EMHASS's own minimum configuration

flexd calls EMHASS's existing `naive-mpc-optim` action — it does not configure EMHASS for you.
For full setup, follow the
[official EMHASS documentation](https://emhass.readthedocs.io/en/latest/). At minimum, EMHASS
itself needs:

- a cost function (`costfun`, e.g. `profit`)
- sensor entity IDs for power/PV/load (or EMHASS's built-in test/mock data, if you just want to
  see the pipeline work end to end before wiring real sensors)
- your location's latitude, longitude, and timezone (for solar forecasting)
- `optimization_time_step` — the value you copied into `flexd.yaml` in step 2

If EMHASS can already produce a plan on its own (check its web UI or `/action/naive-mpc-optim`
directly), you're ready for step 4.

## 4. Start the bundle

```bash
docker compose up -d
```

This starts `flexd` and `emhass`. If you need MQTT (Home Assistant, ioBroker), add the profile:

```bash
docker compose --profile mqtt up -d
```

That brings up a bundled Mosquitto broker too, using `mosquitto/mosquitto.conf`.

Verify flexd is up:

```bash
curl localhost:8321/healthz
# {"status":"ok","emhass":"ok"}
```

`emhass: "ok"` means flexd can reach EMHASS and EMHASS reports healthy. It says `"down"`
while EMHASS is still starting up (give it a minute), when `emhass_url` is wrong, and on a fresh
EMHASS that has not completed a single optimization yet: EMHASS answers `/healthz` with
`503 degraded` until its first run, so expect `"down"` to turn into `"ok"` after the first
cycle in step 5.

## 5. Register your first demand and read it back

Using the Simple-API (the same call the Loxone guide uses), register a 2000 W load that needs
1000 Wh within the next 4 hours:

```bash
curl -X POST "http://localhost:8321/simple/demands/register?source=e2e&id=e2e-load&power_w=2000&energy_wh=1000&deadline_in_h=4"
```

Register parameters worth knowing beyond `power_w`, `energy_wh` and `deadline_in_h`:

- `modulating` (default `false`): set to `true` only for devices that can run at any power
  between zero and `power_w` (a modulating heat pump, a variable-speed pump). flexd then
  asks EMHASS for a continuous slot and fractional hours. For everything else (the default)
  the device runs at `power_w` or not at all: flexd asks for a semi-continuous slot and
  rounds the remaining energy UP to whole timesteps, so a 1200 Wh / 2000 W dishwasher on a
  30-minute grid is planned as two slots (1000 Wh would be unreachable). Expect
  over-delivery of less than one timestep per run.

flexd runs its solve cycle on a timer, but for a quick check you can trigger one immediately:

```bash
curl -X POST http://localhost:8321/api/v1/cycle
```

Then read the per-demand plan:

```bash
curl http://localhost:8321/api/v1/plan/demands/e2e-load
# {"setpoint_w": ..., "on": ..., "clamped": false, "truncated": false,
#  "unschedulable": false, "state": "ok", "pending": false}
```

Or the plain-value poll a Loxone Virtual Input would use:

```bash
curl http://localhost:8321/simple/demands/e2e-load/setpoint
```

## 6. Bring your own EMHASS

Already run EMHASS? Start flexd on its own and point it at your instance instead of the bundled
one:

```bash
docker compose up -d flexd
```

with `FLEXD_EMHASS_URL=http://<your-emhass-host>:5000` set in the environment (or in
`flexd.yaml`'s `emhass_url`). The `emhass` service in `docker-compose.yml` is only there for
convenience — nothing in flexd requires it specifically.

## 7. Where flexd keeps its state

Everything flexd persists lives under `/data` (the `flexd-data` volume in the compose bundle):

| File | Contents |
|---|---|
| `demands.json` | the active demand registry, plus the ids whose retained MQTT topics still need clearing (written in the same snapshot as the withdrawal, so a crash between a withdraw and the next cycle cannot lose the clear) |
| `standing_ledger.json` | per-day accounting for standing (recurring) demands |
| `adopted_plan.json` | the last plan flexd accepted from EMHASS |
| `last_cycle.json` | a debug crumb written every cycle: timestamp, payload hash, result |

If something looks wrong — a setpoint that doesn't match expectations, a demand that seems
stuck — **`last_cycle.json` is the first thing to check**: it tells you whether the last cycle
ran, skipped, or failed, and why.
