# I869 — v0.17.3 config-page regression

**Filed:** 2026-05-20 06:17Z by RikBast against `davidusb-geek/emhass` v0.17.3 ([issue #869](https://github.com/davidusb-geek/emhass/issues/869)).
**Root-caused:** 2026-05-20 by OptimalNothing90.
**Audit pinned to:** upstream commit `ce58a0a` (tag `v0.17.3`, release 2026-05-19 22:48Z).

## Symptom report (RikBast)

> The EMHASS config page in v0.17.3 is messed up after updating:
> - Deferrable loads switch not available
> - Deferrable loads settings almost all gone
> - Battery settings not possible, only switch available
> - Button 'Yaml' not working
> - Save probably not working, I don't get the green confirmation mark

## Initial maintainer hypothesis (ruled out)

In [#867 thread comment 4495592264](https://github.com/davidusb-geek/emhass/pull/867#issuecomment-4495592264), davidusb-geek asked whether the currency-sweep PR (#867) might have caused the regression — it touched `param_definitions.json`.

Verified false: PR #867's only change is a single-line edit inside the `Description` string of `photovoltaic_production_sell_price` (`€/kWh` → `currency/kWh`). No key added or removed, no structural change, no `default_value` touched. The renderer cannot break from a description-text edit.

## Real root cause

The config page crashes inside `src/emhass/static/configuration_script.js` (function `buildParamElement`) at v0.17.3 line ~412. The switch over the `input` field has no case for two new input types introduced in v0.17.3:

- `"array.array.float"` — added by PR #861 (snauwaertc) on `cost_forecast_per_deferrable_load`
- `"object"` — added by PR #863 (snauwaertc) on `heat_topology`

Both new entries ship with `default_value: null` in `param_definitions.json` and corresponding null-shaped values in `config_defaults.json`:

```json
"cost_forecast_per_deferrable_load": [null, null],
"heat_topology": null,
"is_electric_load": [true, true]
```

(`is_electric_load` is also new but `array.boolean` *is* handled by the switch and the default `[true, true]` is a non-null array, so it does not crash.)

When the switch falls through, `type = ""` and `placeholder = ""`. The next line resolves `value` via `checkConfigParam(placeholder, config, name)`:

- For `heat_topology`: `config["heat_topology"]` exists, returns `null`.
- For `cost_forecast_per_deferrable_load`: returns `[null, null]`.

`typeof null === "object"` in JavaScript (the famous gotcha), and arrays are objects too, so both values enter the `else` branch at line ~484:

```js
if (typeof value !== "object") {
  // single-input render
} else {
  if (typeof Object.values(value)[0] === "object") {
    for (let param of Object.values(value)) {
      for (let items of Object.values(param)) {   // ← Object.values(null) throws here
        ...
      }
    }
  } else {
    for (let param of value) { ... }              // ← for-of on null also throws
  }
}
```

For `heat_topology` (value = `null`): `Object.values(null)` throws `TypeError: Cannot convert undefined or null to object` on the very first line of the `else` block.

For `cost_forecast_per_deferrable_load` (value = `[null, null]`): `Object.values([null, null])[0] === null`, `typeof null === "object"` → enters the nested-object branch → `Object.values(null)` throws on the second loop.

`cost_forecast_per_deferrable_load` is rendered first (file order, entry #4 in Deferrable Loads) so it is the actual crash site.

## Reproduction (Node replay)

`buildParamElement` was ported verbatim into a standalone Node script and run against the actual `param_definitions.json` and `config_defaults.json` from `v0.17.3`:

```
[1/13] OK   number_of_deferrable_loads (input=int)
[2/13] OK   nominal_power_of_deferrable_loads (input=array.float)
[3/13] OK   minimum_power_of_deferrable_loads (input=array.float)
[4/13] FAIL cost_forecast_per_deferrable_load (input=array.array.float)
        TypeError: Cannot convert undefined or null to object
```

Repro script: `.tmp/repro_869.js` (working-copy artifact, not committed).

## Crash blast radius

Section render order in `param_definitions.json` (file order = render order):

1. Local
2. System
3. Tariff
4. Solar System (PV)
5. **Deferrable Loads** ← crash at entry #4
6. **Battery** ← never reached

Once the section loop throws and is not caught, the following work never runs:

- Deferrable Loads entries 5–13 never render (10 entries lost: `heat_topology`, `is_electric_load`, `operating_hours_of_each_deferrable_load`, `treat_deferrable_load_as_semi_cont`, `set_deferrable_load_single_constant`, `set_deferrable_startup_penalty`, `set_deferrable_max_startups`, `start_timesteps_of_each_deferrable_load`, `end_timesteps_of_each_deferrable_load`).
- Battery section never builds (all 21 entries lost, only the static template header survives).
- The post-loop wiring of Yaml / Defaults / Save button event listeners never runs → buttons exist (from `configuration.html` template) but do nothing.

This maps 1-to-1 to RikBast's symptom list.

## Why review missed it

- PRs #861 / #863 modified Python optimization code and added entries to `param_definitions.json`. CI green: `pytest` covers backend logic.
- No automated check loads `/configuration` and verifies it renders without JS console errors.
- No static contract enforces that every distinct `input` value used in `param_definitions.json` has a matching `case` in `configuration_script.js`'s `buildParamElement` switch.
- Sourcery-AI review operates on diff statics, not on the cross-file rendering contract.
- Maintainer review focused on the algorithmic side; the JSON additions looked benign by themselves.
- `param_definitions.json` is implicitly a frontend-rendering contract but is not labeled or tested as such anywhere in the codebase.

## Files involved

| File | Role in regression |
|---|---|
| `src/emhass/static/configuration_script.js` | Crash site (`buildParamElement` switch + `else` branch on null) |
| `src/emhass/static/data/param_definitions.json` | New entries with unhandled `input` types |
| `src/emhass/data/config_defaults.json` | Ships null / null-array values for the new entries |
| `src/emhass/templates/configuration.html` | Unchanged; loads the broken script |

## Fix path

### Hotfix (immediate)

1. Null-guard the `else` branch of `buildParamElement`: if `value === null`, render a single empty input element of the appropriate `type` and return (no `Object.values` call).
2. Add `case "object":` and `case "array.array.float":` to the switch. For now they can fall back to a string-like placeholder representation; richer UI for nested arrays / object graphs is a separate feature concern.

Both changes are minimal and surgical. They restore the config page on v0.17.3 + the two new params render as (currently empty) controls instead of breaking the page.

### Prevention (follow-up RFC)

Two complementary guards:

1. **Static contract test**: parse `param_definitions.json`, collect the set of distinct `input` values, parse `configuration_script.js`, extract switch cases. Fail if the set difference is non-empty. Pytest-runnable, no browser needed.
2. **Headless smoke test**: spin up the Quart app in CI, load `/configuration` in a headless browser (Playwright), assert that the page emits no JS console errors and that the expected number of `.param-input` containers is rendered. This catches null-value regressions even when input types are formally handled.

Both should be added to the existing GitHub Actions matrix.

## References

- Issue: <https://github.com/davidusb-geek/emhass/issues/869>
- Maintainer ping: <https://github.com/davidusb-geek/emhass/pull/867#issuecomment-4495592264>
- Root-cause comment: <https://github.com/davidusb-geek/emhass/issues/869#issuecomment-4498519462>
- v0.17.3 compare: <https://github.com/davidusb-geek/emhass/compare/v0.17.2...v0.17.3>
- PR #861 (`cost_forecast_per_deferrable_load`): <https://github.com/davidusb-geek/emhass/pull/861>
- PR #863 (`heat_topology`): <https://github.com/davidusb-geek/emhass/pull/863>
- Memory entry: `project_v0173_release_and_i869.md`
