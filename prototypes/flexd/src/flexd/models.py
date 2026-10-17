"""Demand schema. Pure data — no I/O here.

The model is mutable by design; after construction the Registry is the sole
mutator (refresh/updated_at). validate_assignment is deliberately off — see
the registry for the write discipline.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"

# Sanity ceilings, not physics: anything above is a client bug (or an Infinity token
# that json.loads accepted). One bad register would otherwise poison the whole solve
# until expires_at.
MAX_POWER_W = 1_000_000.0  # 1 MW
MAX_ENERGY_WH = 1_000_000_000.0  # 1 GWh
MAX_TTL_S = 366 * 24 * 3600.0  # one year


def utcnow() -> datetime:
    return datetime.now(UTC)


class Demand(BaseModel):
    # a typo'd field (p_min_watt) must be a 422, not a silent no-op (#1 Lows). Registry
    # files are dumped from this model, so a reload only ever sees known fields.
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_PATTERN)
    source: str = Field(pattern=ID_PATTERN)
    type: Literal["ev", "thermal", "generic"] = "generic"
    flexibility: Literal["shiftable", "committed", "hybrid"] = "shiftable"
    energy_target_wh: float = Field(gt=0, le=MAX_ENERGY_WH, allow_inf_nan=False)
    nominal_power_w: float = Field(gt=0, le=MAX_POWER_W, allow_inf_nan=False)
    p_min_w: float = Field(default=0, ge=0, le=MAX_POWER_W, allow_inf_nan=False)
    window_start: datetime | None = None
    deadline: datetime
    expires_at: datetime
    priority: int = Field(default=1, ge=0)
    interruptible: bool = True
    # False (default): the device runs at nominal power or not at all -> semi-continuous
    # slot in EMHASS, remaining energy rounded UP to whole timesteps. True: the device
    # modulates -> continuous power, fractional hours are fine (Codex review finding 1,
    # #1 Medium 5).
    modulating: bool = False
    current_power_w: float = Field(default=0, ge=0, le=MAX_POWER_W, allow_inf_nan=False)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    # Run identity, assigned by the registry from a registry-wide counter: a new
    # registration (first, after delete, after expiry) gets a fresh, higher value; a
    # re-declaration of a live demand keeps it. The aggregated mapping carries the
    # revision it was solved for, so a slot solved for an older run reads as pending
    # (Codex review 2026-10-17 finding 2). 0 means "not registered yet".
    revision: int = Field(default=0, ge=0)
    ttl_s: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )  # derived below; persisted for refresh semantics. Ceiling applies to explicit values only (see _finalize)

    @field_validator(
        "window_start", "deadline", "expires_at", "created_at", "updated_at"
    )
    @classmethod
    def _aware_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return v.astimezone(UTC)

    @model_validator(mode="after")
    def _finalize(self, info: ValidationInfo) -> "Demand":
        if self.window_start is not None and self.window_start >= self.deadline:
            raise ValueError("window_start must be before deadline")
        if self.p_min_w > self.nominal_power_w:
            raise ValueError("p_min_w must not exceed nominal_power_w")
        persisted = bool(info.context and info.context.get("persisted"))
        if not persisted:
            # Client input: no expiry further out than one year (#1 Medium 12). A
            # registry reload is exempt so nothing already persisted is thrown away.
            now = (info.context or {}).get("now") or utcnow()
            if (self.expires_at - now).total_seconds() > MAX_TTL_S:
                raise ValueError(
                    f"expires_at must not be more than {MAX_TTL_S:.0f} s (one year) "
                    "from now"
                )
        if self.ttl_s is None:
            # expires_at in the past -> ttl_s 0: born expired, swept next cycle (intended).
            # Derived ttl is not capped: it must round-trip through the registry file.
            self.ttl_s = max(0.0, (self.expires_at - self.created_at).total_seconds())
        elif not persisted and self.ttl_s > MAX_TTL_S:
            # Only client input is capped. A registry reload passes context={"persisted": True}
            # and may carry any ttl_s, including one lifted by refresh() (review finding 2).
            raise ValueError(f"ttl_s must not exceed {MAX_TTL_S:.0f} s (one year)")
        return self
