"""Plain-value transport for Loxone Virtual I/O. text/plain in, text/plain out, no JSON."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import ValidationError

from flexd.models import Demand, utcnow
from flexd.registry import OwnershipError
from flexd.transports import reject_standing_squat


def create_simple_router(
    *,
    registry,
    view,
    scheduler,
    driver,
    standing=None,
    templates=None,
    default_ttl_s: int = 3600,
) -> APIRouter:
    router = APIRouter(prefix="/simple", default_response_class=PlainTextResponse)

    @router.post("/demands/register", status_code=201)
    def register(
        source: str = Query(...),
        id: str = Query(...),
        power_w: float | None = Query(default=None, gt=0),
        energy_wh: float | None = Query(default=None, gt=0),
        hours: float | None = Query(default=None, gt=0),
        deadline_in_h: float = Query(default=8, gt=0),
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
        reject_standing_squat(standing, id, source)
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
                    if window_start_in_h is not None
                    else None,
                    deadline=deadline,
                    expires_at=deadline + timedelta(seconds=default_ttl_s),
                )
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_change()
        return "1"

    @router.get("/demands/{demand_id}/setpoint")
    def setpoint(demand_id: str):
        """Polling endpoints never 404: a Loxone Virtual Input reads '0' unambiguously
        as OFF regardless of its error config. Unknown, expired and pending demands
        are all 'off'. /simple/status is the health channel."""
        dv = view.demand_view(demand_id, now=utcnow())
        return str(round(dv.setpoint_w)) if dv else "0"

    @router.get("/demands/{demand_id}/on")
    def on(demand_id: str):
        """Polling endpoints never 404: a Loxone Virtual Input reads '0' unambiguously
        as OFF regardless of its error config. Unknown, expired and pending demands
        are all 'off'. /simple/status is the health channel."""
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
        if standing is not None and standing.is_standing(demand_id):
            if source != "config":
                raise HTTPException(
                    status_code=409,
                    detail=f"{demand_id} is a standing demand; only source 'config' may mark it done",
                )
            standing.mark_done(demand_id, now=utcnow())
            scheduler.notify_change()
            return "1"
        try:
            registry.delete(demand_id, source=source)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown demand")
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_change()
        return "1"

    @router.post("/templates/{template_id}/start", status_code=201)
    def template_start(template_id: str, source: str = Query(...)):
        if templates is None:
            raise HTTPException(status_code=404, detail="no templates configured")
        try:
            templates.start(template_id, source=source, now=utcnow())
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown template")
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_change()
        return "1"

    @router.get("/status")
    def status():
        if scheduler.last_result == "down":
            return "down"
        return view.state(now=utcnow())

    return router
