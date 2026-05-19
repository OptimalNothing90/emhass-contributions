# I854 — Currency-neutrality sweep (Cat 1 + Cat 2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`. Mechanical find-replace + grep verification + draft-first PR. Single bundle.

**Goal:** Replace `€` / `€/kWh` with `currency` / `currency/kWh` across 11 files. No behavior change. Closes #854.

**Architecture:** No code logic affected. Doc-text + Description-text + code-comment surface only.

**Tech Stack:** Plain text edit, grep, JSON validity check.

**Karpathy guardrails:** Think first (verify each occurrence is in spec scope before edit). Simplicity (no bonus rewrites). Surgical (touch only the 11 files listed in spec §4, no others). Goal-driven (success = grep returns clean on those 11 files post-edit + Cat 3 files unchanged).

---

## Task 1: Pre-flight + branch

- [ ] `gh auth status` shows `OptimalNothing90` active (switch via `gh auth switch --user OptimalNothing90` if not)
- [ ] `git config user.email` shows `202644606+OptimalNothing90@users.noreply.github.com` (set explicitly if not)
- [ ] `git fetch upstream && git checkout upstream/master`
- [ ] `git checkout -b fix/i854-currency-sweep-cat-1-2`
- [ ] `git status` clean

## Task 2: Cat 1 edits (6 files)

For each file:line in spec §4 Cat 1 table, apply find-replace `€/kWh` → `currency/kWh` (exception: SVG keeps the surrounding parentheses):

- [ ] `src/emhass/static/data/param_definitions.json` line 303 (inside `Description` text)
- [ ] `docs/config.md` lines 144, 145, 151
- [ ] `docs/forecasts.md` line 204
- [ ] `docs/images/hp_hc_periods.svg` line 1605 (inside `<tspan>` text content)

Verify after each: `grep -n '€' <file>` returns empty.

## Task 3: Cat 2 edits (5 files)

For each file:line in spec §4 Cat 2 table, apply find-replace `# €/kWh` → `# currency/kWh`:

- [ ] `src/emhass/optimization.py` lines 2826-2827 (×2)
- [ ] `tests/test_optimization.py` lines 724-725 (×2)
- [ ] `scripts/optimization_legacy.py` lines 1647-48, 1680-81, 1752-53 (×6)
- [ ] `scripts/script_simple_thermal_model.py` lines 164-165 (×2)
- [ ] `scripts/script_thermal_model_optim.py` lines 156-157 (×2)

Verify after each: `grep -n '€' <file>` returns empty.

## Task 4: Verification

- [ ] **JSON validity:** `python -c "import json; json.load(open('src/emhass/static/data/param_definitions.json', encoding='utf-8'))"` → exit 0.
- [ ] **Scope-confined grep:** `git diff --name-only upstream/master..HEAD | xargs grep -n '€' 2>&1 | grep -v 'Binary'` returns empty. (If anything shows, an edit was missed.)
- [ ] **Out-of-scope confirmation:** `git diff --name-only upstream/master..HEAD | sort` lists exactly these 11 files and nothing else (in particular: `src/emhass/utils.py`, `src/emhass/retrieve_hass.py`, `docs/thermal_battery.md`, `CHANGELOG.md` must NOT appear).
- [ ] **Sphinx build (optional):** `sphinx-build -b html docs docs/_build 2>&1 | tail -20`. Skip if Sphinx not available locally — CI covers this.
- [ ] **Targeted-test smoke:** run `pytest tests/test_optimization.py -q --tb=no 2>&1 | tail -5` to confirm comment-only change in test file didn't accidentally break something parsing-related.

If any check fails, STOP and pivot.

## Task 5: Gate 0 — Pre-PR quality pass

Skip — mechanical doc/comment find-replace, no simplification surface. Note in PR body: "Gate 0 N/A for mechanical text sweep."

## Task 6: Commit + push

- [ ] `git add <11 files>` (specific paths, not `git add .`)
- [ ] `git status` — only the 11 files staged, nothing else
- [ ] Commit:
  ```bash
  git commit -m "$(cat <<'EOF'
  docs(currency): sweep €/kWh → currency/kWh across docs + code comments (#854)

  Replaces literal €/kWh with currency/kWh in human-readable surfaces:
  - Cat 1: Description text in param_definitions.json + docs/config.md +
    docs/forecasts.md + docs/images/hp_hc_periods.svg
  - Cat 2: code-column comments in optimization.py + tests/test_optimization.py
    + scripts/optimization_legacy.py + scripts/script_simple_thermal_model.py
    + scripts/script_thermal_model_optim.py

  Out of scope (per maintainer #854 comment): src/emhass/utils.py EUR/€
  mappings, src/emhass/retrieve_hass.py HA-unit priority list, default_currency_unit,
  docs/thermal_battery.md example sensor (uses real symbol intentionally),
  CHANGELOG.md historical entry.

  ¤/kWh stays reserved for the structured unit field per #850.

  Closes #854.
  EOF
  )"
  ```
- [ ] `git push -u origin fix/i854-currency-sweep-cat-1-2`

## Task 7: Open draft PR

- [ ] `gh pr create --draft --repo davidusb-geek/emhass --base master --head OptimalNothing90:fix/i854-currency-sweep-cat-1-2 --title "docs(currency): sweep €/kWh → currency/kWh across docs + code comments (#854)" --body-file -` with body:
  ```
  ## Summary

  Closes #854.

  Replaces literal `€` / `€/kWh` with spelled-out `currency` / `currency/kWh` in human-readable surfaces (Description text, docs, code comments). `¤/kWh` stays reserved for the structured `unit` field per #850.

  Maintainer pre-approval in #854: `Cat 1 & Cat 2 (Docs & Comments): Go right ahead!`

  ## Changes

  Cat 1 — Docs / Description text (6 files):
  - `src/emhass/static/data/param_definitions.json:303`
  - `docs/config.md:144, 145, 151`
  - `docs/forecasts.md:204`
  - `docs/images/hp_hc_periods.svg:1605`

  Cat 2 — Code comments (5 files):
  - `src/emhass/optimization.py:2826-2827`
  - `tests/test_optimization.py:724-725`
  - `scripts/optimization_legacy.py:1647-48, 1680-81, 1752-53`
  - `scripts/script_simple_thermal_model.py:164-165`
  - `scripts/script_thermal_model_optim.py:156-157`

  Total: ~21 string replacements across 11 files. No behavior change.

  ## Out of scope (per #854 maintainer decision)

  - `src/emhass/utils.py` EUR/€ mappings and `default_currency_unit` constant — Cat 3, intentionally untouched per `prefer keeping the EUR (€) default fallback logic exactly as-is`.
  - `src/emhass/retrieve_hass.py` HA-unit-detection priority list — Cat 3.
  - `docs/thermal_battery.md:586` example sensor `unit_of_measurement: "€"` — Home Assistant `monetary` device class expects a real currency symbol; the user supplies their own locale.
  - `CHANGELOG.md` historical entry — Cat 4.

  ## Notes

  Gate 0 (pre-PR simplify pass) N/A for mechanical text sweep.
  ```
- [ ] Capture PR URL + number.

## Task 8: Mark-ready gates

Watch CI via `gh pr checks <PR> --watch`. Don't call `gh pr ready` until ALL:

1. CI green (any pre-existing master failures noted in HANDOFF-RESULT notes, not in our scope).
2. CodeQL: 0 new alerts.
3. Sourcery-AI feedback: addressed or replied with reasoning.
4. Self-review walk: `git diff upstream/master..HEAD` reviewed file-by-file; only the spec'd edits present.
5. Out-of-scope confirmation: re-verify no Cat 3 / Cat 4 files in the diff.

When all pass: `gh pr ready <PR>`.

## Task 9: Emit HANDOFF-RESULT

```
HANDOFF-RESULT fix-i854-currency-sweep
status: pr-open | blocked | failed
pr-url: <url>
branch: fix/i854-currency-sweep-cat-1-2
tests: skipped (doc/comment-only sweep)
notes: <one-line — e.g. "21 strings across 11 files, grep clean, Cat 3 untouched, CI green, marked ready">
```

---

## Pivot trigger

If `grep -n '€'` on the spec'd files returns lines that don't match the expected mechanical-edit pattern (e.g. embedded in a code expression rather than a comment or doc-string), STOP. Don't improvise the edit. Append `## Pivot Reason` with file:line citations to `../emhass-contributions/docs/superpowers/plans/2026-05-19-i854-pivot.md`. Return blocked.

If any Cat 3 file ends up in the diff accidentally, STOP — revert the file with `git checkout -- <path>` and re-grep.
