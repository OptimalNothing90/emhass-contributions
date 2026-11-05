"""Runtime-params provider: fresh EMHASS runtime parameters for every solve.

`extra_runtime_params` is read once at boot, so forecasts and `soc_init` in it
are frozen for the life of the process. The provider reads a JSON object of
runtime parameters plus `generated_at` (ISO 8601 with offset) from a file or
a URL right before each solve. Anything that makes the document unusable
(too old, missing, unreachable, not JSON, no usable `generated_at`, a list
that is not `prediction_horizon` long, a `first_step_start` that is not this
solve's step 0) raises StaleInputs and the scheduler skips the cycle instead
of solving on old data. The StaleInputs text is the cycle's reason: it goes
into last_cycle.json and onto plan/state, so it must stay readable.

Why age alone is not enough (LesIT1, issue #1): forecast lists are positional,
entry i belongs to step i of the grid the solve anchors on. A relay that
rebuilds its document once per step is fresh by age for the whole step, but a
re-solve triggered mid-step (a demand change) anchors on the NEXT boundary
under ts_round=nearest, so every list would be read one step shifted. The
optional `first_step_start` stamp lets the relay say which boundary the
document was built for; when present it must equal the cycle's anchor.
"""

import asyncio
import json
from datetime import datetime

import httpx

from flexd.aggregator import FLEXD_CANONICAL_KEYS, FLEXD_LEGACY_ALIASES
from flexd.config import RuntimeParamsProviderConfig
from flexd.models import parse_generated_at

# bounds the whole fetch, not httpx's per-read timeout: a trickling server must
# not hold the cycle lock open
FETCH_TIMEOUT_S = 10.0
# forecasts are a few KB; anything bigger is not a provider document
MAX_DOC_BYTES = 1_000_000
# an HTTP error body is the relay's own explanation (a bridge answering 503 with
# text); keep enough to read, bounded. The scheduler uses the same bound for the
# EMHASS 4xx log tail.
MAX_ERROR_BODY_CHARS = 500
# an ISO 8601 instant with offset is under 40 characters
MAX_STAMP_CHARS = 64
# lists the aggregator overrides and drops with a warning anyway: their length says
# nothing about the forecasts, so they are not held to prediction_horizon
_FLEXD_OWNED_KEYS = FLEXD_CANONICAL_KEYS | FLEXD_LEGACY_ALIASES


def _reject_constant(name: str):
    # NaN / Infinity are not JSON; EMHASS would choke on them later
    raise ValueError(f"{name} is not valid JSON")


class StaleInputs(Exception):
    """The provider document is unusable for this cycle; the message says why."""


class RuntimeParamsProvider:
    def __init__(self, cfg: RuntimeParamsProviderConfig, *, horizon_steps: int):
        self._path = cfg.path
        self._url = cfg.url
        self.max_age_s = cfg.max_age_s
        self.source = str(cfg.path if cfg.path is not None else cfg.url)
        # what flexd sends as prediction_horizon; every forecast list must match it
        self._horizon_steps = horizon_steps

    async def fetch(self, *, now: datetime, first_step_start: datetime) -> dict:
        """Return the runtime parameters (metadata keys removed) or raise StaleInputs.
        `first_step_start` is step 0 of the solve about to run (the grid anchor)."""
        text = await self._read()
        if len(text) > MAX_DOC_BYTES:
            raise StaleInputs(
                f"{self.source}: document too large ({len(text)} chars, "
                f"max {MAX_DOC_BYTES})"
            )
        try:
            doc = json.loads(text, parse_constant=_reject_constant)
        except (ValueError, RecursionError) as exc:
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
        if age_s < -self.max_age_s:
            # a relay clock far ahead would otherwise produce a document that
            # never ages out; small skew (within max_age_s) is tolerated
            raise StaleInputs(
                f"{self.source}: generated_at is {-age_s:.0f}s in the future, "
                f"max_age_s is {self.max_age_s:.0f}"
            )
        if age_s > self.max_age_s:
            raise StaleInputs(
                f"{self.source}: generated_at is {age_s:.0f}s old, "
                f"max_age_s is {self.max_age_s:.0f}"
            )
        self._check_first_step(doc.pop("first_step_start", None), first_step_start)
        self._check_list_lengths(doc)
        return doc

    def _check_first_step(self, raw, first_step_start: datetime) -> None:
        """Optional stamp: when present, the document must be built for this solve's
        step 0. Absent (None): the age check above is all there is (older relays)."""
        if raw is None:
            return
        # the text ends up in a retained MQTT payload: never echo an unbounded value
        if not isinstance(raw, str) or not 0 < len(raw) <= MAX_STAMP_CHARS:
            raise StaleInputs(
                f"{self.source}: first_step_start must be an ISO 8601 string, "
                f"got {raw!r:.{MAX_STAMP_CHARS}}"
            )
        try:
            stamped = parse_generated_at(raw, field="first_step_start")
        except ValueError as exc:
            raise StaleInputs(f"{self.source}: {exc}") from exc
        if stamped != first_step_start:
            raise StaleInputs(
                f"{self.source}: first_step_start {stamped.isoformat()} is not this "
                f"solve's first step {first_step_start.isoformat()}"
            )

    def _check_list_lengths(self, doc: dict) -> None:
        """Every top-level list is positional over the horizon: a wrong length would
        reach EMHASS as a short or shifted forecast, so it is stale, not a warning."""
        for key, value in doc.items():
            if not isinstance(value, list) or key in _FLEXD_OWNED_KEYS:
                continue
            if len(value) != self._horizon_steps:
                raise StaleInputs(
                    f"{self.source}: {key} has {len(value)} entries, "
                    f"prediction_horizon is {self._horizon_steps}"
                )

    async def _read(self) -> str:
        if self._path is not None:
            try:
                return self._path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise StaleInputs(f"{self._path}: unreadable ({exc})") from exc
        try:
            async with asyncio.timeout(FETCH_TIMEOUT_S):
                async with httpx.AsyncClient(timeout=FETCH_TIMEOUT_S) as client:
                    resp = await client.get(self._url)
                    resp.raise_for_status()
                    return resp.text
        except TimeoutError as exc:
            raise StaleInputs(
                f"{self._url}: fetch timed out after {FETCH_TIMEOUT_S}s"
            ) from exc
        except httpx.HTTPStatusError as exc:
            # the body is the relay's own explanation; keep it readable but bounded
            body = exc.response.text[:MAX_ERROR_BODY_CHARS].strip()
            detail = f": {body}" if body else ""
            raise StaleInputs(
                f"{self._url}: HTTP {exc.response.status_code}{detail}"
            ) from exc
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            raise StaleInputs(f"{self._url}: unreachable ({exc})") from exc
