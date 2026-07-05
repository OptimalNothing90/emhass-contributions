"""Shared transport helpers."""

from fastapi import HTTPException


def reject_standing_squat(standing, demand_id: str, source: str) -> None:
    """Standing ids are reserved for source 'config': the registry ownership guard
    only protects while an instance exists (outside the window a dynamic client
    could squat the id and starve the standing demand)."""
    if standing is not None and standing.is_standing(demand_id) and source != "config":
        raise HTTPException(
            status_code=409, detail=f"{demand_id} is reserved for a standing demand"
        )
