"""emhass-contrib prototypes — feature-flagged additions to upstream EMHASS.

Each module here registers extra Quart routes (or other extensions)
on the upstream EMHASS app. Routes always register at import time;
each handler checks `flags.is_enabled(<feature>)` per-request and
returns 404 when the flag is off.

This package's import is triggered by docker/entrypoint.sh; if any
prototype module fails to import, the entrypoint logs the traceback
and continues with vanilla EMHASS (does NOT crash the container).

See AGENTS.md > "Adding a new prototype" for the contributor flow.
"""

from __future__ import annotations

# Re-export flags utilities so prototype modules can `from prototypes import flags`
from . import flags

__all__ = ["flags"]
