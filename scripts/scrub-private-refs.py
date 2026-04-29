#!/usr/bin/env python3
"""Pre-commit hook: scan staged files for private-repo / personal-account refs.

Exits non-zero if any forbidden pattern is matched. Skips upstream/ submodule
content (handled by the pre-commit `exclude` rule, defensive duplicate here).
"""

from __future__ import annotations

import re
import sys

PATTERNS: list[tuple[str, str]] = [
    # Full URLs into the private repo are leaks. Bare narrative mentions
    # ("see notes in OptimalNothing90/loxonesmarthome") are fine — the repo's
    # existence isn't secret, only its contents.
    (r"github\.com/OptimalNothing90/loxonesmarthome", "private repo URL"),
    (r"/mnt/user/appdata/emhass/Loxone", "private path reference"),
    (r"TIBBER_TOKEN", "private token name"),
    (r"EVCC_PASS", "private credential"),
]


def main(argv: list[str]) -> int:
    violations: list[str] = []
    for fname in argv[1:]:
        if fname.startswith("upstream/"):
            continue
        try:
            with open(fname, "r", encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        for pat, label in PATTERNS:
            if re.search(pat, text):
                violations.append(f"{fname}: matched {label} (pattern: {pat})")

    if violations:
        sys.stderr.write("Private-ref scrub violations:\n")
        for v in violations:
            sys.stderr.write(f"  {v}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
