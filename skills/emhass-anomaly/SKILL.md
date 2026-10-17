---
name: emhass-anomaly
description: Use when an EMHASS run failed or looks wrong and the user shares or points at action_logs.txt / logger_emhass.log / the add-on log, or asks "why did EMHASS fail", "infeasible", "relaxed", "NaN in forecast", "sensor not found", "Solcast 402 / 429 / limit", "400 Bad Request on runtimeparams", "websocket keeps reconnecting", "cache miss". Also for a quick health check of a vanilla EMHASS v0.18.x install.
---

# EMHASS log anomaly scan

Classify before you read. The scanner matches the exact v0.18.6 logger strings and
tells you which failure class fired, how often, and where. Then read only the matched
lines.

## Get the log

| Install | Path |
|---|---|
| Docker / standalone | `<data_path>/action_logs.txt` (default `/app/data` in the container, or the mounted `data/` dir) |
| Home Assistant add-on | `/share/emhass/action_logs.txt`, or the add-on Log tab (copy to a file) |
| CLI runs | `<data_path>/logger_emhass.log` (has timestamps) |

`action_logs.txt` holds only the latest action (EMHASS truncates it per request) and has
no timestamps. Use `GET /api/v1/last-run` and `GET /healthz` for the run verdict and
freshness; use the scanner for the reason.

## Run

```bash
python ${CLAUDE_SKILL_DIR}/scripts/scan_logs.py action_logs.txt [--since 24h] [--json]
python ${CLAUDE_SKILL_DIR}/scripts/scan_logs.py --list     # signature catalogue
```

`--since` only filters logs with timestamps (`logger_emhass.log`); on `action_logs.txt`
it is ignored with a note. Exit 1 when an ERROR class fired, 0 otherwise, 2 unreadable.

## Classes and what to do

| Class | Sev | Fix direction |
|---|---|---|
| `infeasible` | ERROR | Constraint conflict. Run `emhass-config-validate`; compare SOC targets, operating hours vs window, hybrid inverter limits, grid limits. |
| `relaxed` | WARN | MILP failed, LP fallback published as `Optimal (Relaxed)`. Treat as infeasible; the published plan is a best effort and worthless when the cause is bad input (`nan_forecast`, `missing_sensor`). |
| `nan_forecast` | ERROR | Runtime forecast list has NaN/null/str or wrong length. Fix the producer (template, automation) not EMHASS. |
| `missing_sensor` | ERROR | Entity id wrong, no numeric history, bad token/URL. Check config.json sensors and HA history. |
| `solcast_quota` | ERROR | 402/429 or safety cap. Cache the forecast (`weather-forecast-cache` action + `weather_forecast_cache_only`), check key / rooftop id. |
| `runtime_400` | ERROR | Payload not valid JSON (`False` vs `false`), unknown action, or no params.pkl (save config once). |
| `websocket` | WARN | HA websocket dropped, REST fallback used. Persistent: `use_websocket: false` or fix proxy/token. |
| `cache_miss_storm` | WARN | Problem rebuilt every call (>3 MISS lines). A structural config value flips between calls. Needs `logging_level: DEBUG` to be visible. |
| `weather_cache` | WARN | Stale/corrupt weather cache. Run `weather-forecast-cache` once. |
| `mpc_horizon` | ERROR | `prediction_horizon` < 5 or changed between calls. |
| `deferrable_padding` | WARN | Per-load / per-battery array length mismatch. Validate config. |
| `unclassified_error` | ERROR | New failure. Quote the line, search EMHASS issues, do not guess. |

## Workflow

1. Run the scanner. Classes are printed ERROR before WARN, and within a severity in
   order of first appearance (`first_line`), so the first ERROR line is normally the root
   cause and the ones below it are consequences.
2. Report the first ERROR class with its count and the `e.g.:` line. Open the log at its
   `first_line` and read 10 lines before it: the cause is usually logged as INFO/WARNING
   just above the ERROR.
3. One root cause at a time. `infeasible` or `relaxed` appearing after `nan_forecast`,
   `missing_sensor` or `runtime_400` is a consequence, not a separate problem; say so and
   do not send the user chasing constraints.
4. Give the user the fix direction from the table and the exact config key to change.
5. "OK: no known failure signatures" plus a bad plan means a modelling problem, not a
   failure: switch to `emhass-plan-explain`.

## Not covered

Threshold / drift detection on solver results over time (needs a time-series store),
Home Assistant side errors, add-on supervisor logs. Signatures are from v0.18.6; on a
newer EMHASS an `unclassified_error` may be a renamed message, check upstream.
