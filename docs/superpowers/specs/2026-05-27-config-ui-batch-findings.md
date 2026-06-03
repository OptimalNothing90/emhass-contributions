# Config-UI Batch: Findings & Grouping — 2026-05-27

Verified against `upstream/master` @ 3d5ea2e (branch `fix/i880-config-ui`).

---

## Issue #880 — Config page broken after v0.17.4/5

### Root cause (verified against reporter's `config.json`)

Reporter's config has:
- `number_of_deferrable_loads: 0`
- `nominal_power_of_deferrable_loads: [3000]` (1 element)
- `heat_topology: {"sources": []}` (object with empty sources list)

**Crash path:**

1. `window.onload` → `loadConfigurationListView` → `buildParamContainers("Deferrable Loads", ...)` builds the section, including `heat_topology`.
2. `buildParamElement` for `heat_topology` (input=`"object"`, value=`{"sources":[]}`) enters the nested-object path (`typeof Object.values(value)[0] === "object"` is true because `[]` is an object). Inner loop: `Object.values([]) = []` → 0 iterations → returns `"</br>"` (no `<input>` element).
3. `loadConfigurationListView` calls `headerElement(number_of_deferrable_loads_element, ...)`.
4. `headerElement` computes `difference = 0 − 1 = −1` → calls `minusElements(param.id)` once for each Deferrable Loads param.
5. `minusElements("heat_topology")` → `param_input_list.length == 0` (div has no inputs) → enters the error branch → **`ReferenceError: parameter_definition_name is not defined`** (undefined variable used instead of `param` at line 563).
6. Uncaught error propagates up the `async window.onload` promise → remaining onload code never executes → event listeners for battery toggle, json-toggle, save button are never attached → whole UI is dead.

### Bugs in `minusElements` (lines 551–587 of `configuration_script.js`)

| Line | Bug | Fix |
|------|-----|-----|
| 556 | `parameter_definition_name` (undefined) instead of `param` | rename |
| 563 | `parameter_definition_name` (undefined) instead of `param` | rename |
| 565 | No `return 1` after the length==0 log — falls through to `param_input_list[-1].parentNode` (TypeError) | add `return 1;` |

### Bug in `buildParamElement` — `"object"` type

For `"object"` input type, the existing nested-object rendering (`for...of Object.values(value)`) is designed for `load_peak_hour_periods`, not for free-form JSON objects like `heat_topology`. `{"sources": []}` produces no `<input>` elements. Fix: detect `input === "object"` before the nested-object path and render as a single JSON-stringified text input.

### Bonus: #880 also explains the battery-toggle and json-toggle being dead

Both event listeners are attached AFTER `loadConfigurationListView` returns. Once the crash aborts `window.onload`, they are never set up.

---

## Issue #904 — heat_topology saved as string "null"

### Root cause (verified)

1. `buildParamElement` case `"object"`: `placeholder = JSON.stringify(null)` → `"null"` (string).
2. When `heat_topology` is absent from the user's config, `checkConfigParam` returns `"null"` (the placeholder string).
3. `typeof "null" !== "object"` → non-object path → renders `<input type="text" value=null>` (browser: value="null").
4. `saveConfiguration`: `input.value = "null"` → `config["heat_topology"] = "null"` (string, not JSON null).
5. Backend `utils.py` line 1970: `elif heat_topology:` — string `"null"` is truthy → warning on every request.

`config_defaults.json` on master already has `"heat_topology": null` (JSON null). The string is introduced by the JS save path.

### Fix layer: JS only (build side + save side)

- **Build side**: `placeholder = default_value === null ? "" : JSON.stringify(default_value)` for `"object"` (and `"array.array.float"`) cases. Empty placeholder instead of `"null"`.
- **Save side**: in `saveConfiguration`, for params with `input === "object"`, try `JSON.parse(input.value)`; if empty or `"null"` → save as `null`.

---

## Issue #763 — KeyError set_deferrable_max_startups + GUI toggle dead

### Root cause (verified)

1. **KeyError (backend)**: Filed against v0.17.1. The `check_def_loads` call for `set_deferrable_max_startups` was added to `build_params` before `set_deferrable_max_startups` was added to `config_defaults.json`. Without the key present in the merged config, `result = parameter[parameter_name]` at `check_def_loads:3004` raised `KeyError`.
2. **Current master status**: `config_defaults.json` now has `"set_deferrable_max_startups": [0, 0]`. `build_params` merges defaults first (`config.update(user_config)`), so the key is always present. **KeyError NOT reproducible on master.**
3. **GUI toggle dead** (comment from "fuqu00"): same root cause as #880.

### Action (no code change needed)

Comment on #763 that the backend KeyError is resolved on master and the GUI toggle will be fixed by the #880 PR. Close #763 after PR merges. (Main session handles the comment.)

---

## PR Grouping Proposal

### Recommended: Single PR (PR A)

**One PR — `configuration_script.js` only — closes #880 + #904; enables close of #763**

All changes are in one file, one concern: JS config-UI correctness.

| Change | Lines | Target issue |
|--------|-------|--------------|
| `minusElements` variable name fix (lines 556, 563) | 2 | #880 crash |
| `minusElements` early return for 0-input case (line 565) | 1 | #880 crash |
| `buildParamElement` `"object"` type: render as JSON text input | ~5 | #880 UX + #904 display |
| `buildParamElement` null placeholder fix | 1 | #904 display |
| `saveConfiguration` object-type JSON.parse/null | ~8 | #904 save |

Total: ~17 lines, 1 file.

**No PR B needed.** The originally-proposed PR B (backend `utils.py` #763 KeyError hardening) is moot — the KeyError is already fixed on master via `config_defaults.json`. The GUI toggle complaint in #763 is resolved by PR A.

### Why not split PR A further?

The crash fix (minusElements) and the object-render fix are causally linked: the crash is triggered BY the broken object render that produces 0 inputs. Fixing only the crash without fixing the render would leave `heat_topology: {"sources": []}` displaying as an empty invisible field in the UI. The save-side fix is the natural completion of the render fix (build+save need to agree on format). All three are tightly coupled. Splitting into sub-PRs would create intermediate states that are individually harder to verify.

---

## Verification plan (post-implementation)

1. Node-replay or Docker: load `/configuration` with reporter's `config.json`. Confirm zero JS console errors.
2. Battery toggle ON/OFF reveals/hides battery params.
3. JSON toggle (brackets button) switches to textarea and back.
4. `heat_topology` field renders a JSON text box (not empty) when config has `{"sources": []}`.
5. Save with `heat_topology` blank → round-trip keeps it as JSON null (no string "null" warning from backend).
6. `pytest tests/` passes; `uvx ruff check .` clean.

---

---

## Cache-busting audit

**`configuration.html` line 10:**
```html
<link rel="stylesheet" href="static/style.css?version=2">   ← has version query
<script src="static/configuration_script.js"></script>       ← NO version query
```

**Server-side headers:**
- `Cache-Control: no-store` at `web_server.py:657` applies only to the `/api/v1/last-run` JSON endpoint, not to static files.
- Quart app init: `app = Quart(__name__)` — default static serving; no explicit `Cache-Control` on static assets. Browsers receive `Last-Modified` + `ETag` only and may heuristic-cache indefinitely when the URL is unchanged.

**This explains the OMVMMG/ThomasCZ cache story:**
- OMVMMG: clearing HA cookies + cache forced a fresh fetch → v0.17.4 hotfix landed → worked.
- ThomasCZ on v0.17.5 with incognito: the incognito session had no stale cache, so the real code bug manifested for his config (`heat_topology: {"sources": []}`) — confirmed that the crash is a genuine code bug, not a cache artifact.
- The inconsistency (CSS has `?version=2`, JS doesn't) means any JS change that ships without bumping the query param risks being silently ignored by users who already have the old file cached.

**Recommendation: fold into PR A (1-line change)**

Add `?version=1` to the `configuration_script.js` script tag in `configuration.html`, matching the existing `?version=2` pattern used for `style.css`. This is a 1-line change, no backend touched, and immediately forces a cache miss for all users on the patched release regardless of local cache state.

A proper long-term fix (e.g., dynamic version injection from the Quart template context, or `Cache-Control: no-cache` on the `/static/` route) is out of scope for this PR — note it as a follow-up issue in the PR description.

**Scope verdict:** fold `?version=1` query into PR A. The combined PR A still touches only `configuration.html` (1 line) + `configuration_script.js` (~17 lines). No new file, no backend change.

---

## Simplify Gate 0 log

Applied:
- `@pytest.fixture(scope="module")` for `js_src` in `test_schema_contract.py` — reads 1MB JS file once instead of 4× across the new tests.
- `console.debug(...)` added in `saveConfiguration` `catch` block for non-JSON object values — improves debuggability without behavior change.

Kept (not simplified):
- Comment on object-type guard in `buildParamElement` (`// Free-form JSON objects ... designed only for load_peak_hour_periods`). Explains a non-obvious design constraint — kept per code-style rule (WHY comments only).
- Separate extraction of `checkConfigParam` + `buildParamElement` in each Node-replay test (tests 3 and 4). The overhead is sub-ms string slicing; a second fixture would add indirection without payoff.

---

## Status

Implementation complete. Branch `fix/i880-config-ui` committed (454c325) and pushed. Draft PR #907 open — awaiting CI and maintainer review.
