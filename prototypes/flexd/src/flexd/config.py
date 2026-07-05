"""flexd.yaml loading with FLEXD_* env overrides. Fail loud at boot, never at runtime."""

import os
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from flexd.models import ID_PATTERN

_WINDOW_RE = re.compile(r"^(\d{2}:\d{2})-(\d{2}:\d{2})$")


class MqttConfig(BaseModel):
    enabled: bool = False
    host: str = "localhost"
    port: int = 1883
    base_topic: str = "flexd"
    username: str | None = None
    password: str | None = None


class StandingDefinition(BaseModel):
    id: str = Field(pattern=ID_PATTERN)
    type: str = "generic"
    nominal_power_w: float = Field(gt=0)
    daily_hours: float | None = Field(default=None, gt=0)
    daily_energy_wh: float | None = Field(default=None, gt=0)
    window: tuple[str, str]
    interruptible: bool = True

    @field_validator("window", mode="before")
    @classmethod
    def _parse_window(cls, v):
        if isinstance(v, str):
            m = _WINDOW_RE.match(v)
            if not m:
                raise ValueError(f"window must look like '06:00-22:00', got {v!r}")
            start, end = m.group(1), m.group(2)
            if start >= end:
                raise ValueError(f"window start must be before end, got {v!r}")
            return (start, end)
        return v

    @property
    def effective_daily_hours(self) -> float:
        # spec precedence: energy wins over hours when both given
        if self.daily_energy_wh is not None:
            return self.daily_energy_wh / self.nominal_power_w
        if self.daily_hours is not None:
            return self.daily_hours
        raise ValueError(
            f"standing demand {self.id}: daily_hours or daily_energy_wh required"
        )


class FlexdConfig(BaseModel):
    emhass_url: str = "http://localhost:5000"
    timestep_min: int = 30
    horizon_steps: int = 48
    timezone: str = "UTC"
    data_dir: Path = Path("/data")
    stale_after_cycles: int = 2
    default_ttl_s: int = 3600
    mqtt: MqttConfig = MqttConfig()
    extra_runtime_params: dict = {}
    standing_demands: list[StandingDefinition] = []


_ENV_MAP = {
    "FLEXD_EMHASS_URL": ("emhass_url",),
    "FLEXD_TIMESTEP_MIN": ("timestep_min",),
    "FLEXD_HORIZON_STEPS": ("horizon_steps",),
    "FLEXD_TIMEZONE": ("timezone",),
    "FLEXD_DATA_DIR": ("data_dir",),
    "FLEXD_MQTT_ENABLED": ("mqtt", "enabled"),
    "FLEXD_MQTT_HOST": ("mqtt", "host"),
    "FLEXD_MQTT_PORT": ("mqtt", "port"),
    "FLEXD_MQTT_USERNAME": ("mqtt", "username"),
    "FLEXD_MQTT_PASSWORD": ("mqtt", "password"),
}


def load_config(path: Path | str) -> FlexdConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    for env, keypath in _ENV_MAP.items():
        val = os.environ.get(env)
        if val is None:
            continue
        node = raw
        for key in keypath[:-1]:
            node = node.setdefault(key, {})
        node[keypath[-1]] = val
    cfg = FlexdConfig(**raw)
    for sd in cfg.standing_demands:
        sd.effective_daily_hours  # raises at boot if neither hours nor energy given
    return cfg
