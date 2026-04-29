"""Feature-flag reader for emhass-contrib prototypes.

Reads a YAML config file (default: /app/data/contrib-flags.yaml).
File-based config so flags can be toggled without container restart.

Behavior on errors:
- Missing file -> all flags False (treat-missing-as-off).
- Parse error -> all flags False, log warning.

Caching: 5-second TTL with mtime invalidation to keep request-time
overhead minimal.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import yaml

# /data is the upstream EMHASS runtime data dir (see upstream/Dockerfile).
# /app/data holds *seed* files baked into the image and is overlaid on first
# boot only — mounting a host volume there would shadow the seeds and break
# the upstream init script. So the production flag file lives under /data.
DEFAULT_FLAGS_PATH = Path(
    os.environ.get("EMHASS_CONTRIB_FLAGS_PATH", "/data/contrib-flags.yaml")
)
CACHE_TTL_SECONDS = 5

_logger = logging.getLogger("emhass.contrib.flags")
_cache: dict[str, Any] = {"mtime": 0.0, "expires": 0.0, "data": {}}


def _read_flags(path: Path) -> dict[str, Any]:
    """Read flags YAML. Returns empty dict on any error."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if not isinstance(data, dict):
                if data is not None:
                    _logger.warning("flags file is not a dict: %s", path)
                return {}
            return data
    except FileNotFoundError:
        return {}
    except (yaml.YAMLError, OSError) as e:
        _logger.warning("flags file unreadable (%s): %s", e, path)
        return {}


def _get_cached(path: Path) -> dict[str, Any]:
    """Return cached flags. Invalidate if file mtime changed or TTL expired."""
    now = time.monotonic()
    try:
        mtime = path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        mtime = 0.0

    if now > _cache["expires"] or mtime != _cache["mtime"]:
        _cache["data"] = _read_flags(path)
        _cache["mtime"] = mtime
        _cache["expires"] = now + CACHE_TTL_SECONDS
    return _cache["data"]


def is_enabled(feature: str, *, path: Path | None = None) -> bool:
    """Return True if the named prototype feature is enabled in the flags file."""
    flags_dict = _get_cached(path or DEFAULT_FLAGS_PATH)
    return bool(flags_dict.get("prototypes", {}).get(feature, {}).get("enabled", False))


def get_setting(
    feature: str, key: str, default: Any = None, *, path: Path | None = None
) -> Any:
    """Return a feature-specific setting (e.g. cache_seconds for api_last_run)."""
    flags_dict = _get_cached(path or DEFAULT_FLAGS_PATH)
    return flags_dict.get("prototypes", {}).get(feature, {}).get(key, default)
