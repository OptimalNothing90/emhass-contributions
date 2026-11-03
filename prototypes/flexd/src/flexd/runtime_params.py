"""Runtime-params provider: fresh EMHASS runtime parameters for every solve.

A stateless EMHASS behind flexd only sees what flexd sends. The static
`extra_runtime_params` dict is read once at boot, so forecasts (PV, load,
prices) and `soc_init` would be frozen for the life of the process. The
provider closes that gap: a JSON object with runtime parameters plus
`generated_at` (ISO 8601 with offset), read from a file or a URL right before
each solve. An external relay that today rebuilds EMHASS payloads itself can
write this document instead.

Contract (OptimalNothing90/emhass-contributions#1, 2026-11-03):
- exactly one of `path` / `url`
- older than `max_age_s`, missing, unreachable or unparsable raises
  StaleInputs; the scheduler then skips the cycle (no solve on old data)
- `generated_at` missing or without an offset counts as stale
- the returned dict never contains `generated_at`; conflict filtering against
  flexd's own keys happens in the aggregator, as for the static dict
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import httpx

log = logging.getLogger(__name__)


class StaleInputs(Exception):
    """The provider document is unusable for this cycle; the reason is the message."""


class RuntimeParamsProvider:
    def __init__(
        self,
        *,
        path: Path | str | None = None,
        url: str | None = None,
        max_age_s: float,
        timeout_s: float = 10.0,
        client_factory=httpx.AsyncClient,
    ):
        if (path is None) == (url is None):
            raise ValueError("runtime_params_provider needs exactly one of path or url")
        self._path = None if path is None else Path(path)
        self._url = url
        self._max_age_s = float(max_age_s)
        self._timeout_s = timeout_s
        self._client_factory = client_factory

    @property
    def source(self) -> str:
        return str(self._path) if self._path is not None else str(self._url)

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
        generated_at = self._parse_generated_at(doc.get("generated_at"))
        age_s = (now - generated_at).total_seconds()
        if age_s > self._max_age_s:
            raise StaleInputs(
                f"{self.source}: generated_at is {age_s:.0f}s old, "
                f"max_age_s is {self._max_age_s:.0f}"
            )
        return {k: v for k, v in doc.items() if k != "generated_at"}

    async def _read(self) -> str:
        if self._path is not None:
            try:
                return self._path.read_text(encoding="utf-8")
            except OSError as exc:
                raise StaleInputs(f"{self._path}: unreadable ({exc})") from exc
        try:
            async with self._client_factory(timeout=self._timeout_s) as client:
                resp = await client.get(self._url)
                resp.raise_for_status()
                return resp.text
        except httpx.HTTPStatusError as exc:
            raise StaleInputs(f"{self._url}: HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise StaleInputs(f"{self._url}: unreachable ({exc})") from exc

    def _parse_generated_at(self, raw) -> datetime:
        if not isinstance(raw, str) or not raw:
            raise StaleInputs(f"{self.source}: generated_at missing")
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise StaleInputs(
                f"{self.source}: generated_at {raw!r} is not ISO 8601"
            ) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise StaleInputs(f"{self.source}: generated_at {raw!r} has no UTC offset")
        return parsed
