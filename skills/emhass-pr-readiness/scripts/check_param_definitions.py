#!/usr/bin/env python3
"""Check that param_definitions.json changed additively (AGENTS.md don't-touch rule 4).

    check_param_definitions.py <old.json> <new.json>

[FAIL] key removed, `input` kind changed, select option removed  -> exit 1
[WARN] key moved between sections, default_value changed         -> exit 0
[OK]   added keys / options are listed                           -> exit 0
exit 2 when a file cannot be read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _flatten(doc: dict) -> dict[str, tuple[str, dict]]:
    flat: dict[str, tuple[str, dict]] = {}
    for section, params in doc.items():
        if isinstance(params, dict):
            for key, definition in params.items():
                if isinstance(definition, dict):
                    flat[key] = (section, definition)
    return flat


def compare(old: dict, new: dict) -> tuple[list[str], bool]:
    lines: list[str] = []
    failed = False
    old_flat, new_flat = _flatten(old), _flatten(new)

    for key in sorted(set(old_flat) - set(new_flat)):
        lines.append(
            f"[FAIL]  param_definitions.json: key removed (`{key}`) - additive only"
        )
        failed = True
    added = sorted(set(new_flat) - set(old_flat))
    for key in added:
        lines.append(
            f"[OK]    param_definitions.json: key added (`{key}`, input={new_flat[key][1].get('input')}); "
            "config_defaults.json + associations.csv must change too"
        )
    for key in sorted(set(old_flat) & set(new_flat)):
        (old_sec, old_def), (new_sec, new_def) = old_flat[key], new_flat[key]
        if old_def.get("input") != new_def.get("input"):
            lines.append(
                f"[FAIL]  param_definitions.json: `{key}` input changed "
                f"{old_def.get('input')} -> {new_def.get('input')} - breaks config UI and tooling"
            )
            failed = True
        old_opts = set(old_def.get("select_options") or [])
        new_opts = set(new_def.get("select_options") or [])
        removed = sorted(old_opts - new_opts)
        if removed:
            lines.append(
                f"[FAIL]  param_definitions.json: `{key}` select option(s) removed {removed}"
            )
            failed = True
        if old_sec != new_sec:
            lines.append(
                f"[WARN]  param_definitions.json: `{key}` moved from section "
                f"'{old_sec}' to '{new_sec}' (UI grouping changes)"
            )
        if old_def.get("default_value") != new_def.get("default_value"):
            lines.append(
                f"[WARN]  param_definitions.json: `{key}` default_value "
                f"{old_def.get('default_value')!r} -> {new_def.get('default_value')!r}; "
                "align config_defaults.json (docs/develop.md: changing default values)"
            )
    if not lines:
        lines.append("[OK]    param_definitions.json: no schema change")
    elif not failed and not any(ln.startswith("[OK]") for ln in lines):
        lines.append("[OK]    param_definitions.json: additive")
    return lines, failed


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        old = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
        new = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"[FAIL]  cannot read param_definitions.json: {exc}")
        return 2
    for label, doc in (("old", old), ("new", new)):
        if not isinstance(doc, dict):
            print(
                f"[FAIL]  {label} param_definitions.json root is "
                f"{type(doc).__name__}, expected an object of sections"
            )
            return 2
    lines, failed = compare(old, new)
    print("\n".join(lines))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
