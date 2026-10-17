---
name: emhass-plan-explain
description: Use when an EMHASS user asks why the plan looks the way it does - "why does my dishwasher / heat pump / EV not run tonight", "why is the battery charging from the grid", "why is the load split in two blocks", "did the optimizer pick the cheapest hours", "what did the last run decide", or when /api/v1/plan, opt_res_latest.csv, P_deferrable, SOC_opt, optim_status show up in the question. Works on any EMHASS v0.18.x install, no home-automation stack needed.
---

# EMHASS plan explanation

Translate the optimizer's schedule into plain language before guessing at causes.
The bundled script reads the public read API and prints per-load / per-battery facts.

## Get the inputs

| Input | Where | Required |
|---|---|---|
| plan | `GET http://<emhass-host>:5000/api/v1/plan` (save to `plan.json`) or pass the URL | yes |
| last run | `GET /api/v1/last-run` (status, action, duration, stage_times, error_message) | optional |
| config | the `config.json` EMHASS ran with (window + operating hours comparison) | optional, recommended |

`/api/v1/plan` returns `status: "no-run"` until an optimization has completed. Both
endpoints are read-only and need no token when reached on the EMHASS port.

## Run

```bash
python ${CLAUDE_SKILL_DIR}/scripts/explain_plan.py plan.json [--last-run last_run.json] [--config config.json] [--tz Europe/Berlin] [--json]
```

File paths or `http(s)://` URLs both work for `plan` and `--last-run`. Exit 0 when the
plan is Optimal (incl. `Optimal_Inaccurate`, `Optimal (Relaxed)`), 1 otherwise, 2 when an
input cannot be read. `--json` gives the same facts as a machine-readable object.

## Read the output

1. **STATUS line first.** `Infeasible` / `Failure` / `Unbounded` means the rest is a
   fallback, not a plan. Stop and run `emhass-anomaly` on `action_logs.txt`.
   `Optimal (Relaxed)` means the MILP was infeasible and EMHASS re-solved without the
   semi-continuous / single-constant constraints: loads may run at partial power or in
   many pieces. Tell the user that, then look for the constraint that broke.
2. **Deferrable load k** = `P_deferrable{k}` column, 0-based, same order as
   `nominal_power_of_deferrable_loads`. The paragraph gives steps on, blocks, start/end
   time (UTC unless `--tz`), energy, and with `--config` the window plus the expected
   steps (constant-nominal loads) or expected energy (modulating loads,
   `treat_deferrable_load_as_semi_cont: false`). Equal-priced steps count as cheapest.
   - "never runs": window outside horizon, operating hours 0, `def_current_state`
     already done, or the horizon ends before the window opens (MPC with short
     `prediction_horizon`).
   - "NOT in the cheapest steps": lists cheaper unused steps. Cross-check start/end
     window, `def_minimum_on_time`, `set_deferrable_max_startups`, PV self-consumption
     (`costfun`), battery priority, `treat_deferrable_load_as_semi_cont`.
   - fewer steps than configured: the horizon is too short for the operating hours or
     the window clamps them. Which knob depends on the action in `--last-run`:
     `naive-mpc-optim` → raise `prediction_horizon` in the runtime payload (the horizon
     is `prediction_horizon` steps; the next MPC cycle re-plans the rest using
     `def_current_state` / `def_current_operating_timesteps` if the caller passes them);
     `dayahead-optim` / `perfect-optim` → the horizon is `delta_forecast_daily` days, so
     shorten the operating hours or widen `end_timesteps_of_each_deferrable_load`.
3. **Battery k**: SOC path (fractions), charge/discharge energy and steps, and whether it
   charges from the grid (PV below charge power while importing). Grid charging is
   legal unless `set_nocharge_from_grid` is true; it usually means cheap night prices.
4. **Grid** totals and peak import give the cost picture; compare with
   `maximum_power_from_grid`.

Answer the user's question in their words ("the dishwasher runs 01:00-02:30 because
those are the two cheapest half-hours; it cannot start earlier because
start_timesteps is 2"). Quote numbers from the script, do not recompute by hand.

## Sign conventions (v0.18.6)

`P_batt` > 0 discharge, < 0 charge. `P_grid_pos` import, `P_grid_neg` export (≤ 0).
SOC columns are fractions 0..1 (Home Assistant shows percent). Timestamps are UTC
instants; the first step is the start of the horizon.

## Not covered

Why the forecast is what it is (use the forecast sensors / `emhass-anomaly`), thermal
loads (`predicted_temp_heater{k}` is printed only in `--json`), and config validity
(`emhass-config-validate`).
