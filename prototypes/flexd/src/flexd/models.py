"""Demand schema. Pure data — no I/O here."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Demand(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    source: str = Field(pattern=ID_PATTERN)
    type: Literal["ev", "thermal", "generic"] = "generic"
    flexibility: Literal["shiftable", "committed", "hybrid"] = "shiftable"
    energy_target_wh: float = Field(gt=0)
    nominal_power_w: float = Field(gt=0)
    p_min_w: float = Field(default=0, ge=0)
    window_start: datetime | None = None
    deadline: datetime
    expires_at: datetime
    priority: int = Field(default=1, ge=0)
    interruptible: bool = True
    current_power_w: float = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    ttl_s: float | None = None  # derived below; persisted for refresh semantics

    @field_validator(
        "window_start", "deadline", "expires_at", "created_at", "updated_at"
    )
    @classmethod
    def _aware_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        if v.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _derive_ttl(self) -> "Demand":
        if self.ttl_s is None:
            self.ttl_s = max(0.0, (self.expires_at - self.created_at).total_seconds())
        return self
