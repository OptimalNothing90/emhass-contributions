## Context

PR #850 (open, awaiting review) proposes a structured `"unit"` field on `param_definitions.json` and uses `¤/kWh` (U+00A4 generic currency sign) for the seven cost-related entries — a single glyph is parse-friendly for openapi.json generators, Pydantic auto-gen, and AI-readable consumers.

For human-readable prose (Description text, docs, code comments), `¤/kWh` is less accessible — not every reader knows U+00A4. This sweep targets human-readable surfaces and uses the spelled-out form `currency/kWh` instead.

EMHASS users run with USD/JPY/GBP/CHF/etc. via the project-level currency setting. Several literal `€` / `€/kWh` strings remain across the repo in user-facing docs and code comments that mislead non-EUR users.

## Glyph choice — split by audience

| Surface | Target | Reason |
|---|---|---|
| Structured `unit` field (machine-readable consumers) | `¤/kWh` (proposed by #850) | Single glyph, parse-friendly |
| Description text in `param_definitions.json` | `currency/kWh` | Readable without Unicode knowledge |
| User-facing docs (`docs/*.md`, SVG labels) | `currency/kWh` | Same |
| Code comments (Python `# €/kWh`) | `currency/kWh` | Same, reader-friendly |

## Scope (sweep candidates)

**Cat 1 — User-facing documentation and Description text (mechanical sweep, target `currency/kWh`):**

| File:Line | Current string |
|---|---|
| `src/emhass/static/data/param_definitions.json:303` | `photovoltaic_production_sell_price` Description: "in €/kWh" |
| `docs/config.md:144` | `load_peak_hours_cost` description "in €/kWh" |
| `docs/config.md:145` | `load_offpeak_hours_cost` description "in €/kWh" |
| `docs/config.md:151` | `photovoltaic_production_sell_price` description "in €/kWh" |
| `docs/forecasts.md:204` | `photovoltaic_production_sell_price` description "in €/kWh" |
| `docs/thermal_battery.md:586` | example sensor `unit_of_measurement: "€"` (could stay as example; check intent) |
| `docs/images/hp_hc_periods.svg:1605` | SVG text label "Load cost (€/kWh)" — needs SVG edit |

**Cat 2 — Code comments (data-column annotations, target `currency/kWh`):**

| File:Lines | Pattern |
|---|---|
| `src/emhass/optimization.py:2826-2827` | `# €/kWh` (2x) |
| `tests/test_optimization.py:724-725` | `# €/kWh` (2x) |
| `scripts/optimization_legacy.py:1647-48, 1680-81, 1752-53` | `# €/kWh` (6x) |
| `scripts/script_simple_thermal_model.py:164-165` | `# €/kWh` (2x) |
| `scripts/script_thermal_model_optim.py:156-157` | `# €/kWh` (2x) |

**Total mechanical sweep: ~21 string replacements across 12 files.**

## Out of scope (this issue)

**Cat 3 — Real currency-handling code logic** — needs maintainer decision, separate concern:

- `src/emhass/utils.py:546` — `"EUR": "€"` mapping. Literal EUR → € symbol; intentional, leave as-is.
- `src/emhass/utils.py:575` — `ha_config["currency"] = "€"` fallback when HA has no currency set.
- `src/emhass/utils.py:641` — `default_currency_unit = "€"` constant.
- `src/emhass/retrieve_hass.py:745` — HA-unit-detection priority list `["EUR/kWh", "€/kWh", "W", "EUR", "€", "%", ...]`.

These reflect EMHASS's EUR-as-default project decision (geographic, reasonable). Open question for a follow-up: should defaults shift to currency-neutral, with EUR-specific mapping retained only on the HA-detection side? Or leave defaults as-is and rely on per-user override?

**Cat 4 — Historical** — `CHANGELOG.md:641` left untouched (historical changelog entry).

## Proposal

1. Get sign-off on the Cat 1 + Cat 2 sweep direction (`currency/kWh` for human-readable surfaces; `¤/kWh` reserved for the structured `unit` field).
2. Single PR for Cat 1 + Cat 2 combined (~21 strings, mechanical, one review pass). Or split docs / code-comments if preferred — let me know.
3. Defer Cat 3 to a follow-up discussion / issue once Cat 1+2 land.

## Acceptance criteria (per sweep PR)

- Every targeted `€` / `€/kWh` occurrence in PR scope replaced with `currency` / `currency/kWh`
- Cat 3 + Cat 4 untouched
- `grep -n '€' <changed files>` returns clean (or only intentional EUR-specific lines)
- JSON validity / Sphinx build green where applicable
- No behaviour change (doc/comment-only)
