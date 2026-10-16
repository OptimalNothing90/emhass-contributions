"""Fold active demands into one EMHASS runtimeparams payload.

Key names verified against upstream/src/emhass/utils.py treat_runtimeparams.
Emits canonical long-name runtime keys (associations.csv col 2); legacy
aliases are blocked from extra_runtime_params so neither spelling can
override flexd.

Deliberately-unmapped Demand fields (not expressible in the MVP
runtimeparams mapping): interruptible, priority, p_min_w, flexibility.
Phase-2 candidates: p_min_w -> min_power_of_deferrable_loads,
interruptible=False -> set_deferrable_load_single_constant.
modulating -> treat_deferrable_load_as_semi_cont (inverted) +
operating_timesteps for non-modulating loads.

Note: extra values are passed by reference into the payload; callers must
not mutate the returned payload.
"""

import logging
import math
from datetime import datetime, timezone

from flexd.models import Demand

log = logging.getLogger(__name__)

FLEXD_CANONICAL_KEYS = {
    # canonical long names (what flexd emits)
    "number_of_deferrable_loads",
    "nominal_power_of_deferrable_loads",
    "operating_hours_of_each_deferrable_load",
    "operating_timesteps_of_each_deferrable_load",
    "treat_deferrable_load_as_semi_cont",
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
    "treat_def_as_semi_cont",
}


def grid_anchor(now: datetime, timestep_min: int, ts_round: str) -> datetime:
    """First optimization step as EMHASS computes it (utils.get_forecast_start):
    nearest = closest step on the UTC clock, ties to even; first = floor; last = ceil.
    flexd requires timestep_min to divide 60 and a UTC offset that is a multiple of
    the step, which makes UTC alignment equal to EMHASS's wall-clock alignment.
    Known limit: a request that crosses a rounding boundary between flexd's `now`
    and EMHASS's receipt can still shift one slot; the scheduler fires on the grid."""
    if ts_round not in ("nearest", "first", "last"):
        raise ValueError(f"ts_round must be nearest, first or last, got {ts_round!r}")
    step = timestep_min * 60
    epoch = int(now.timestamp())  # whole seconds, like upstream's floor("s")
    q, r = divmod(epoch, step)
    if ts_round == "first" or r == 0:
        anchored = q * step
    elif ts_round == "last":
        anchored = (q + 1) * step
    elif r * 2 < step:  # nearest
        anchored = q * step
    elif r * 2 > step:
        anchored = (q + 1) * step
    else:  # exact tie: to the even multiple, as pandas round() does
        anchored = (q if q % 2 == 0 else q + 1) * step
    return datetime.fromtimestamp(anchored, tz=timezone.utc)


def build_runtimeparams(
    demands: list[Demand],
    *,
    now: datetime,
    extra: dict,
    timestep_min: int,
    horizon_steps: int,
    ts_round: str = "nearest",
) -> tuple[dict, dict]:
    """Returns (payload, mapping).

    mapping: demand id -> {slot, clamped, truncated, unschedulable, nominal_power_w,
    modulating, timesteps, anchor}. `anchor` is the ISO instant of step 0 (the same
    for every demand) so a plan can be checked against absolute times.
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

    # step 0 sits where EMHASS will put it, not at the raw `now` (plan review finding 3)
    anchor = grid_anchor(now, timestep_min, ts_round)
    step_h = timestep_min / 60

    def to_step(dt: datetime) -> int:
        return math.ceil((dt - anchor).total_seconds() / 60 / timestep_min)

    mapping: dict = {}
    nominal, op_hours, op_steps, semi_cont, starts, ends, currents = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for slot, d in enumerate(ordered):
        # END uses floor: never run past the deadline (ceil overshot by up to
        # one step). START keeps ceil (to_step): never start before window_start.
        end_raw = math.floor((d.deadline - anchor).total_seconds() / 60 / timestep_min)
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
            # deadline expired or window degenerate: hours 0 and timesteps 0 deactivate the
            # load upstream (no energy constraint, power pinned to zero); slot numbering
            # stays stable.
            hours, steps = 0.0, 0
        else:
            capacity_steps = end_step - start_step
            capacity_h = capacity_steps * step_h
            wanted_h = d.energy_target_wh / d.nominal_power_w  # inf for subnormal power
            truncated = wanted_h > capacity_h
            if d.modulating:
                # continuous power: fractional hours are reachable; timesteps 0 = "use hours"
                if not math.isfinite(wanted_h):
                    hours = math.floor(capacity_h * 100) / 100
                else:
                    # cap unconditionally: round(wanted) may exceed a non-2dp capacity
                    # even when not truncated
                    hours = min(round(wanted_h, 2), math.floor(capacity_h * 100) / 100)
                if hours < 0.01:
                    hours = 0.01  # never round a real demand to zero (silent vanish)
                steps = 0
            else:
                # semi-continuous: energy is only reachable in whole slots at nominal power.
                # Round UP (over-deliver by < 1 slot), cap to the window. Guard the quotient:
                # a subnormal nominal_power_w makes wanted_h inf (plan review finding 4).
                if not math.isfinite(wanted_h) or wanted_h / step_h >= capacity_steps:
                    steps = capacity_steps
                else:
                    steps = max(1, math.ceil(wanted_h / step_h - 1e-9))
                hours = steps * step_h
        nominal.append(d.nominal_power_w)
        op_hours.append(hours)
        op_steps.append(steps)
        semi_cont.append(not d.modulating)
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
            # read-back accrual scales P_deferrable by this (nominal-equivalent hours)
            "nominal_power_w": d.nominal_power_w,
            "modulating": d.modulating,
            "timesteps": steps,
            "anchor": anchor.isoformat(),
        }

    payload.update(
        {
            "number_of_deferrable_loads": len(ordered),
            "nominal_power_of_deferrable_loads": nominal,
            "operating_hours_of_each_deferrable_load": op_hours,
            "operating_timesteps_of_each_deferrable_load": op_steps,
            "treat_deferrable_load_as_semi_cont": semi_cont,
            "start_timesteps_of_each_deferrable_load": starts,
            "end_timesteps_of_each_deferrable_load": ends,
            "def_current_power": currents,
            "prediction_horizon": horizon_steps,
        }
    )
    return payload, mapping
