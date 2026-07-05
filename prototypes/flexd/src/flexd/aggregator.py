"""Fold active demands into one EMHASS runtimeparams payload.

Key names verified against upstream/src/emhass/utils.py treat_runtimeparams.
Emits canonical long-name runtime keys (associations.csv col 2); legacy
aliases are blocked from extra_runtime_params so neither spelling can
override flexd.

Deliberately-unmapped Demand fields (not expressible in the MVP
runtimeparams mapping): interruptible, priority, p_min_w, flexibility.
Phase-2 candidates: p_min_w -> min_power_of_deferrable_loads,
interruptible=False -> set_deferrable_load_single_constant.

Note: extra values are passed by reference into the payload; callers must
not mutate the returned payload.
"""

import logging
import math
from datetime import datetime

from flexd.models import Demand

log = logging.getLogger(__name__)

FLEXD_CANONICAL_KEYS = {
    # canonical long names (what flexd emits)
    "number_of_deferrable_loads",
    "nominal_power_of_deferrable_loads",
    "operating_hours_of_each_deferrable_load",
    "start_timesteps_of_each_deferrable_load",
    "end_timesteps_of_each_deferrable_load",
    "def_current_power",
    "prediction_horizon",
}

FLEXD_LEGACY_ALIASES = {
    # legacy aliases (associations.csv col 1) — blocked so extra can't smuggle either spelling
    "num_def_loads",
    "P_deferrable_nom",
    "def_total_hours",
    "def_start_timestep",
    "def_end_timestep",
}

FLEXD_OWNED_KEYS = FLEXD_CANONICAL_KEYS | FLEXD_LEGACY_ALIASES


def build_runtimeparams(
    demands: list[Demand],
    *,
    now: datetime,
    extra: dict,
    timestep_min: int,
    horizon_steps: int,
) -> tuple[dict, dict]:
    """Returns (payload, mapping).

    mapping: demand id -> {slot, clamped, truncated, unschedulable}.
    """
    ordered = sorted(demands, key=lambda d: d.id)
    payload: dict = {}
    for key, value in extra.items():
        if key in FLEXD_CANONICAL_KEYS:
            log.warning(
                "extra_runtime_params key %r conflicts with flexd; flexd wins", key
            )
            continue
        if key in FLEXD_LEGACY_ALIASES:
            log.warning("extra_runtime_params key %r is a legacy alias; blocked", key)
            continue
        payload[key] = value

    def to_step(dt: datetime) -> int:
        return math.ceil((dt - now).total_seconds() / 60 / timestep_min)

    mapping: dict = {}
    nominal, op_hours, starts, ends, currents = [], [], [], [], []
    for slot, d in enumerate(ordered):
        # END uses floor: never run past the deadline (ceil overshot by up to
        # one step). START keeps ceil (to_step): never start before window_start.
        end_raw = math.floor((d.deadline - now).total_seconds() / 60 / timestep_min)
        clamped = end_raw > horizon_steps
        end_step = min(max(end_raw, 0), horizon_steps)
        start_step = (
            0
            if d.window_start is None
            else min(max(to_step(d.window_start), 0), horizon_steps)
        )
        unschedulable = end_step <= start_step
        truncated = False
        if unschedulable:
            # deadline expired or window degenerate: hours 0 deactivates the load upstream
            # (constraint gate def_total_hours > 0); slot numbering stays stable.
            hours = 0.0
        else:
            capacity_h = (end_step - start_step) * timestep_min / 60
            wanted_h = d.energy_target_wh / d.nominal_power_w
            truncated = wanted_h > capacity_h
            # cap unconditionally: round(wanted) may exceed a non-2dp capacity even when not truncated
            hours = min(round(wanted_h, 2), math.floor(capacity_h * 100) / 100)
            if hours < 0.01:
                hours = 0.01  # never round a real demand to zero (silent vanish)
        nominal.append(d.nominal_power_w)
        op_hours.append(hours)
        starts.append(start_step)
        ends.append(end_step)
        # a deactivated load must be allowed to turn off — pinning it would conflict
        # with hours=0 and make the model infeasible
        currents.append(0 if unschedulable else d.current_power_w)
        mapping[d.id] = {
            "slot": slot,
            "clamped": clamped,
            "truncated": truncated,
            "unschedulable": unschedulable,
        }

    payload.update(
        {
            "number_of_deferrable_loads": len(ordered),
            "nominal_power_of_deferrable_loads": nominal,
            "operating_hours_of_each_deferrable_load": op_hours,
            "start_timesteps_of_each_deferrable_load": starts,
            "end_timesteps_of_each_deferrable_load": ends,
            "def_current_power": currents,
            "prediction_horizon": horizon_steps,
        }
    )
    return payload, mapping
