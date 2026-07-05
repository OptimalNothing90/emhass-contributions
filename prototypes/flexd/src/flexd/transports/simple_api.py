"""Plain-value transport for Loxone Virtual I/O. text/plain in, text/plain out, no JSON."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from flexd.models import Demand, utcnow
from flexd.registry import OwnershipError


def create_simple_router(
    *, registry, view, scheduler, driver, standing=None, default_ttl_s: int = 3600
) -> APIRouter:
    router = APIRouter(prefix="/simple", default_response_class=PlainTextResponse)

    @router.post("/demands/register", status_code=201)
    def register(
        source: str = Query(...),
        id: str = Query(...),
        power_w: float | None = Query(default=None),
        energy_wh: float | None = Query(default=None),
        hours: float | None = Query(default=None),
        deadline_in_h: float = Query(default=8),
        window_start_in_h: float | None = Query(default=None),
    ):
        if power_w is None:
            raise HTTPException(status_code=400, detail="power_w required")
        if energy_wh is None:  # spec precedence: energy wins when both given
            if hours is None:
                raise HTTPException(
                    status_code=400, detail="energy_wh or hours required"
                )
            energy_wh = hours * power_w
        if standing is not None and standing.is_standing(id) and source != "config":
            raise HTTPException(
                status_code=409, detail=f"{id} is reserved for a standing demand"
            )
        now = utcnow()
        deadline = now + timedelta(hours=deadline_in_h)
        try:
            registry.upsert(
                Demand(
                    id=id,
                    source=source,
                    energy_target_wh=energy_wh,
                    nominal_power_w=power_w,
                    window_start=(now + timedelta(hours=window_start_in_h))
                    if window_start_in_h
                    else None,
                    deadline=deadline,
                    expires_at=deadline + timedelta(seconds=default_ttl_s),
                )
            )
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_change()
        return "1"

    @router.get("/demands/{demand_id}/setpoint")
    def setpoint(demand_id: str):
        if registry.get(demand_id) is None:
            raise HTTPException(status_code=404, detail="unknown demand")
        dv = view.demand_view(demand_id, now=utcnow())
        return str(int(dv.setpoint_w)) if dv else "0"

    @router.get("/demands/{demand_id}/on")
    def on(demand_id: str):
        if registry.get(demand_id) is None:
            raise HTTPException(status_code=404, detail="unknown demand")
        dv = view.demand_view(demand_id, now=utcnow())
        return "1" if (dv and dv.on) else "0"

    @router.post("/demands/{demand_id}/refresh")
    def refresh(demand_id: str, source: str = Query(...)):
        try:
            registry.refresh(demand_id, source=source)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown demand")
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return "1"

    @router.post("/demands/{demand_id}/done")
    def done(demand_id: str, source: str = Query(...)):
        try:
            registry.delete(demand_id, source=source)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown demand")
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_change()
        return "1"

    @router.get("/status")
    def status():
        return view.state(now=utcnow())

    return router
