"""JSON REST transport. Thin: validation + registry/view calls, no business logic."""

from fastapi import FastAPI, HTTPException, Query, Response

from flexd.models import Demand, utcnow
from flexd.registry import OwnershipError
from flexd.transports import reject_standing_squat
from flexd.transports.simple_api import create_simple_router


def create_app(
    *,
    registry,
    view,
    scheduler,
    driver,
    standing=None,
    templates=None,
    default_ttl_s: int = 3600,
) -> FastAPI:
    app = FastAPI(title="flexd", version="0.1.0")

    @app.post("/api/v1/demands", status_code=201)
    def register(demand: Demand):
        if (
            standing is not None
            and standing.is_standing(demand.id)
            and demand.source == "config"
        ):
            raise HTTPException(
                status_code=409,
                detail="use PUT (correction) or the materializer owns this id",
            )
        reject_standing_squat(standing, demand.id, demand.source)
        try:
            saved = registry.upsert(demand)
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_change()
        return saved

    @app.get("/api/v1/demands")
    def list_demands():
        return registry.list_active()

    @app.put("/api/v1/demands/{demand_id}")
    def update(demand_id: str, demand: Demand):
        """PUT re-anchors ttl_s deliberately: the client re-declares expires_at, so
        ttl becomes time-to-that-expiry from now. That is the declared contract."""
        if demand.id != demand_id:
            raise HTTPException(status_code=400, detail="id mismatch")
        if standing is not None and standing.is_standing(demand_id):
            if demand.source != "config":
                raise HTTPException(
                    status_code=409,
                    detail=f"{demand_id} is reserved for a standing demand",
                )
            standing.correct(
                demand_id,
                remaining_hours=demand.energy_target_wh / demand.nominal_power_w,
                now=utcnow(),
            )
            scheduler.notify_change()
            return {
                "corrected": True,
                "applies": "next cycle",
                "remaining_hours": demand.energy_target_wh / demand.nominal_power_w,
            }
        reject_standing_squat(standing, demand.id, demand.source)
        try:
            saved = registry.upsert(demand)
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_change()
        return saved

    @app.post("/api/v1/demands/{demand_id}/refresh")
    def refresh(demand_id: str, source: str = Query(...)):
        """Bump expires_at by the stored ttl_s (spec refresh semantics). PUT, by
        contrast, re-anchors: it replaces the demand with a fresh declaration."""
        try:
            saved = registry.refresh(demand_id, source=source)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown demand")
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return saved

    @app.delete("/api/v1/demands/{demand_id}", status_code=204)
    def withdraw(demand_id: str, source: str = Query(...)):
        if standing is not None and standing.is_standing(demand_id):
            if source != "config":
                raise HTTPException(
                    status_code=409,
                    detail=f"{demand_id} is a standing demand; only source 'config' may mark it done",
                )
            standing.mark_done(demand_id, now=utcnow())
            scheduler.notify_change()
            return Response(status_code=204)
        try:
            registry.delete(demand_id, source=source)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown demand")
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_change()
        return Response(status_code=204)

    @app.get("/api/v1/plan")
    def plan():
        raw = view.raw_plan
        return {**(raw or {}), "flexd_meta": {"state": view.state(now=utcnow())}}

    @app.get("/api/v1/plan/demands/{demand_id}")
    def plan_demand(demand_id: str):
        # None-contract (plan_view docstring): registered-but-unmapped means
        # "pending next solve", NOT unknown — only a demand absent from the
        # registry is a 404.
        dv = view.demand_view(demand_id, now=utcnow())
        state = view.state(now=utcnow())
        if dv is None:
            if registry.get(demand_id) is None:
                raise HTTPException(status_code=404, detail="unknown demand")
            return {
                "setpoint_w": 0,
                "on": False,
                "clamped": False,
                "truncated": False,
                "unschedulable": False,
                "state": state,
                "pending": True,
            }
        return {
            "setpoint_w": dv.setpoint_w,
            "on": dv.on,
            "clamped": dv.clamped,
            "truncated": dv.truncated,
            "unschedulable": dv.unschedulable,
            "state": state,
            "pending": False,
        }

    @app.post("/api/v1/templates/{template_id}/start", status_code=201)
    def template_start(template_id: str, body: dict):
        if templates is None:
            raise HTTPException(status_code=404, detail="no templates configured")
        source = body.get("source")
        if not source:
            raise HTTPException(status_code=422, detail="source required")
        try:
            saved = templates.start(template_id, source=source, now=utcnow())
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown template")
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_change()
        return saved

    @app.post("/api/v1/cycle")
    async def trigger_cycle():
        result = await scheduler.run_once()
        return {"result": result}

    @app.get("/healthz")
    async def healthz():
        emhass_ok = await driver.healthy() if hasattr(driver, "healthy") else True
        return {"status": "ok", "emhass": "ok" if emhass_ok else "down"}

    app.include_router(
        create_simple_router(
            registry=registry,
            view=view,
            scheduler=scheduler,
            standing=standing,
            templates=templates,
            default_ttl_s=default_ttl_s,
        )
    )

    return app
