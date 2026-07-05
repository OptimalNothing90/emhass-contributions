"""Fold active demands into one EMHASS runtimeparams payload.

Key names verified against upstream/src/emhass/utils.py treat_runtimeparams.
"""

import logging
import math
from datetime import datetime

from flexd.models import Demand

log = logging.getLogger(__name__)

FLEXD_OWNED_KEYS = {
    "number_of_deferrable_loads",
    "nominal_power_of_deferrable_loads",
    "def_total_hours",
    "start_timesteps_of_each_deferrable_load",
    "end_timesteps_of_each_deferrable_load",
    "def_current_power",
    "prediction_horizon",
}


def build_runtimeparams(
    demands: list[Demand],
    *,
    now: datetime,
    extra: dict,
    timestep_min: int,
    horizon_steps: int,
) -> tuple[dict, dict]:
    """Returns (payload, mapping). mapping: demand id -> {slot, clamped}."""
    ordered = sorted(demands, key=lambda d: d.id)
    payload: dict = {}
    for key, value in extra.items():
        if key in FLEXD_OWNED_KEYS:
            log.warning(
                "extra_runtime_params key %r conflicts with flexd; flexd wins", key
            )
            continue
        payload[key] = value

    def to_step(dt: datetime) -> int:
        return math.ceil((dt - now).total_seconds() / 60 / timestep_min)

    mapping: dict = {}
    nominal, hours, starts, ends, currents = [], [], [], [], []
    for slot, d in enumerate(ordered):
        end_step = to_step(d.deadline)
        clamped = end_step > horizon_steps
        end_step = min(max(end_step, 0), horizon_steps)
        start_step = (
            0
            if d.window_start is None
            else min(max(to_step(d.window_start), 0), horizon_steps)
        )
        nominal.append(d.nominal_power_w)
        hours.append(round(d.energy_target_wh / d.nominal_power_w, 2))
        starts.append(start_step)
        ends.append(end_step)
        currents.append(d.current_power_w)
        mapping[d.id] = {"slot": slot, "clamped": clamped}

    payload.update(
        {
            "number_of_deferrable_loads": len(ordered),
            "nominal_power_of_deferrable_loads": nominal,
            "def_total_hours": hours,
            "start_timesteps_of_each_deferrable_load": starts,
            "end_timesteps_of_each_deferrable_load": ends,
            "def_current_power": currents,
            "prediction_horizon": horizon_steps,
        }
    )
    return payload, mapping
