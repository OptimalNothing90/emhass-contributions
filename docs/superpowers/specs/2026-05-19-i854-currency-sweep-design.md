# I854 — Repo-wide currency-neutrality sweep (Cat 1 + Cat 2) — Design

**Date:** 2026-05-19
**Issue:** https://github.com/davidusb-geek/emhass/issues/854
**Target repo:** `davidusb-geek/emhass` (via `OptimalNothing90/emhass` fork)
**Branch:** `fix/i854-currency-sweep-cat-1-2`
**Effort:** S
**Maintainer pre-approval:** Yes — #854 comment 2026-05-19 19:52 UTC: `Cat 1 & Cat 2 (Docs & Comments): Go right ahead! Cat 3 (Core Logic & Defaults): Let's definitely keep this out of scope for this sweep.`

## 1. Problem

Issue #854 catalogued literal `€` / `€/kWh` strings remaining across the EMHASS repo after PR #850's structured `unit` field landed with `¤/kWh`. The maintainer green-lit Cat 1 (user-facing docs) and Cat 2 (code comments) for replacement, deferring Cat 3 (core defaults + HA-unit-detection priority list).

## 2. Goal

Replace literal `€` / `€/kWh` with spelled-out `currency` / `currency/kWh` across human-readable surfaces. `¤/kWh` stays reserved for the structured `unit` field per #850.

## 3. Decisions

| # | Decision | Source |
|---|----------|--------|
| 1 | Target glyph: `currency/kWh` (spelled-out, accessible without Unicode knowledge). `¤/kWh` reserved for the machine-readable structured `unit` field. | Issue #854 body, maintainer comment |
| 2 | Cat 3 (core defaults + HA-unit priority) untouched per maintainer. `utils.py` `EUR/€` mappings, `default_currency_unit = "€"`, `retrieve_hass.py` priority list all left as-is. | Maintainer comment 2026-05-19 19:52 |
| 3 | `docs/thermal_battery.md:586` example sensor `unit_of_measurement: "€"` left untouched. The example is a Home Assistant template-sensor config the reader copy-pastes; HA's `monetary` device class expects a real currency symbol, not the placeholder string `"currency"`. The user supplies their own locale's symbol. | HA `monetary` device-class semantics |
| 4 | `docs/images/hp_hc_periods.svg:1605` text label "Load cost (€/kWh)" edited as plain XML text inside the existing `<tspan>`. No re-rendering needed; SVG is served as-is by Sphinx. | SVG = text-XML; browsers render directly |
| 5 | `CHANGELOG.md:641` left untouched (historical entry). | Issue #854 Cat 4 |
| 6 | Single bundled PR for Cat 1 + Cat 2 (not split). One review pass for the maintainer. | Issue body proposal |

## 4. Files touched

**Cat 1 — Docs / Description text (6 files, ~7 strings):**

| File:Line | Current | Target |
|---|---|---|
| `src/emhass/static/data/param_definitions.json:303` (Description) | `... in €/kWh.` | `... in currency/kWh.` |
| `docs/config.md:144` | `... in €/kWh.` | `... in currency/kWh.` |
| `docs/config.md:145` | `... in €/kWh.` | `... in currency/kWh.` |
| `docs/config.md:151` | `... in €/kWh.` | `... in currency/kWh.` |
| `docs/forecasts.md:204` | `... in €/kWh.` | `... in currency/kWh.` |
| `docs/images/hp_hc_periods.svg:1605` | `Load cost (€/kWh)` | `Load cost (currency/kWh)` |

**Cat 2 — Code comments (5 files, ~14 strings):**

| File:Lines | Current | Target |
|---|---|---|
| `src/emhass/optimization.py:2826-2827` | `# €/kWh` (×2) | `# currency/kWh` (×2) |
| `tests/test_optimization.py:724-725` | `# €/kWh` (×2) | `# currency/kWh` (×2) |
| `scripts/optimization_legacy.py:1647-48, 1680-81, 1752-53` | `# €/kWh` (×6) | `# currency/kWh` (×6) |
| `scripts/script_simple_thermal_model.py:164-165` | `# €/kWh` (×2) | `# currency/kWh` (×2) |
| `scripts/script_thermal_model_optim.py:156-157` | `# €/kWh` (×2) | `# currency/kWh` (×2) |

**Total: ~21 string replacements across 11 files.** No behavior change; doc/comment-only.

## 5. Concrete edits

Mechanical find-replace `€/kWh` → `currency/kWh` across the targeted files. Each file's surrounding context preserved.

## 6. Test strategy

- **JSON validity** on `param_definitions.json` (existing pre-commit + CI).
- **Sphinx build smoke-test** on docs/ if available; otherwise rely on CI.
- **SVG read-back**: grep `currency/kWh` in `hp_hc_periods.svg` confirms exactly one occurrence post-edit.
- **Grep cross-check on PR scope:** after the edits, `grep -n '€' <changed files>` returns clean (no remaining `€` in any touched file).
- **No new tests.** Comment text isn't covered by tests; behavior is unchanged.

## 7. Acceptance criteria

- Every `€` / `€/kWh` in the 11 targeted files replaced with `currency` / `currency/kWh`.
- `docs/thermal_battery.md:586` `"€"` left untouched (example sensor, Decision #3).
- `CHANGELOG.md` untouched.
- Cat 3 files (`utils.py`, `retrieve_hass.py`) untouched.
- JSON validity + Sphinx (if locally runnable) green.
- PR closes #854.

## 8. Out of scope

- Cat 3 (core defaults, HA-unit priority) — maintainer deferred.
- `docs/thermal_battery.md:586` example sensor — Decision #3.
- `CHANGELOG.md` historical entry — Cat 4.
- Reformatting / restructuring surrounding text.
- Adding new currency-neutrality docs or comments.

## 9. References

- Issue: https://github.com/davidusb-geek/emhass/issues/854
- Maintainer pre-approval: #854 comment 2026-05-19 19:52
- Predecessor PR: #850 (introduced `¤/kWh` on `param_definitions.json` structured `unit` field)
