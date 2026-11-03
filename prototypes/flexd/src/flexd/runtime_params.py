"""Runtime-params provider: fresh EMHASS runtime parameters for every solve.

`extra_runtime_params` is read once at boot, so forecasts and `soc_init` in it
are frozen for the life of the process. The provider reads a JSON object of
runtime parameters plus `generated_at` (ISO 8601 with offset) from a file or
a URL right before each solve. Anything that makes the document unusable
(too old, missing, unreachable, not JSON, no usable `generated_at`) raises
StaleInputs and the scheduler skips the cycle instead of solving on old data.
"""

import json
import logging
from datetime import datetime

import httpx

from flexd.config import RuntimeParamsProviderConfig
from flexd.models import parse_generated_at

log = logging.getLogger(__name__)

FETCH_TIMEOUT_S = 10.0


class StaleInputs(Exception):
    """The provider document is unusable for this cycle; the message says why."""


class RuntimeParamsProvider:
    def __init__(self, cfg: RuntimeParamsProviderConfig):
        self._path = cfg.path
        self._url = cfg.url
        self.max_age_s = cfg.max_age_s
        self.source = str(cfg.path if cfg.path is not None else cfg.url)

    async def fetch(self, *, now: datetime) -> dict:
        """Return the runtime parameters (without `generated_at`) or raise StaleInputs."""
        text = await self._read()
        try:
            doc = json.loads(text)
        except ValueError as exc:
            raise StaleInputs(f"{self.source}: not valid JSON ({exc})") from exc
        if not isinstance(doc, dict):
            raise StaleInputs(
                f"{self.source}: document must be a JSON object, got {type(doc).__name__}"
            )
        raw = doc.pop("generated_at", None)
        if not isinstance(raw, str) or not raw:
            raise StaleInputs(f"{self.source}: generated_at missing")
        try:
            generated_at = parse_generated_at(raw)
        except ValueError as exc:
            raise StaleInputs(f"{self.source}: {exc}") from exc
        age_s = (now - generated_at).total_seconds()
        if age_s > self.max_age_s:
            raise StaleInputs(
                f"{self.source}: generated_at is {age_s:.0f}s old, "
                f"max_age_s is {self.max_age_s:.0f}"
            )
        return doc

    async def _read(self) -> str:
        if self._path is not None:
            try:
                return self._path.read_text(encoding="utf-8")
            except OSError as exc:
                raise StaleInputs(f"{self._path}: unreadable ({exc})") from exc
        try:
            async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_S) as client:
                resp = await client.get(self._url)
                resp.raise_for_status()
                return resp.text
        except httpx.HTTPStatusError as exc:
            raise StaleInputs(f"{self._url}: HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise StaleInputs(f"{self._url}: unreachable ({exc})") from exc
