"""Shared transport helpers."""

from datetime import datetime

from fastapi import HTTPException

from flexd.plan_view import DemandView

OFF = DemandView(setpoint_w=0.0, on=False, clamped=False)


def reject_standing_squat(standing, demand_id: str, source: str) -> None:
    """Standing ids are reserved for source 'config': the registry ownership guard
    only protects while an instance exists (outside the window a dynamic client
    could squat the id and starve the standing demand)."""
    if standing is not None and standing.is_standing(demand_id) and source != "config":
        raise HTTPException(
            status_code=409, detail=f"{demand_id} is reserved for a standing demand"
        )


def live_demand_view(registry, view, demand_id: str, now: datetime):
    """Plan view gated by registry state (Codex review 2026-10-16 finding 3).

    Returns (DemandView | None, status) where status is one of
    "unknown" (not in registry), "expired" (in registry, expires_at <= now),
    "pending" (registered, not in the adopted mapping, or registered after the
    adopted plan was solved), "outside-window" (before window_start or at/after the
    deadline) or "ok". A withdrawn or expired demand must read as OFF immediately;
    the adopted plan may still carry a positive slot for it until the next
    successful solve, and a solve with zero demands is skipped altogether.

    The window gate is the last word on timing: the plan view serves the first
    record up to one step early and a slot runs to its end, so without it a setpoint
    could precede window_start or outlive the deadline (Codex review 2026-10-17
    finding 1). Serving OFF inside the window where the plan says ON is never done
    here; EMHASS's start/end steps already honour the window at slot resolution.

    A demand deleted and registered again while a solve was in flight keeps its id
    but is a different run: the mapped slot was solved for the old one, so until the
    next adoption it is pending, not served (#1 Lows). created_at marks that: the
    registry keeps it across re-declarations of a live demand (PUT, MQTT set).
    """
    demand = registry.get(demand_id)
    if demand is None:
        return None, "unknown"
    if demand.expires_at <= now:
        return OFF, "expired"
    dv = view.demand_view(demand_id, now=now)
    if dv is None:
        return None, "pending"
    if dv.solved_at is not None and demand.created_at > dv.solved_at:
        return None, "pending"
    if (demand.window_start is not None and now < demand.window_start) or (
        now >= demand.deadline
    ):
        return OFF, "outside-window"
    return dv, "ok"
