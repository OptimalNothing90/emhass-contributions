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
    "pending" (registered, not in the adopted mapping) or "ok". A withdrawn or
    expired demand must read as OFF immediately; the adopted plan may still carry a
    positive slot for it until the next successful solve, and a solve with zero
    demands is skipped altogether.
    """
    demand = registry.get(demand_id)
    if demand is None:
        return None, "unknown"
    if demand.expires_at <= now:
        return OFF, "expired"
    dv = view.demand_view(demand_id, now=now)
    if dv is None:
        return None, "pending"
    return dv, "ok"
