"""JSON REST transport. Thin: validation + registry/view calls, no business logic."""

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from flexd.models import Demand, utcnow
from flexd.registry import OwnershipError, RegistryFull
from flexd.templates import TemplateRunWithdrawn
from flexd.transports import live_demand_view, reject_standing_squat
from flexd.transports.simple_api import create_simple_router

MAX_BODY_BYTES = 64 * 1024  # a demand is a few hundred bytes; anything bigger is abuse


class BodyLimitMiddleware:
    """Refuse oversized request bodies before a handler reads them (#1 Lows).

    Content-Length above the limit is a 413. A chunked body without Content-Length
    is a 411: flexd's clients (Loxone, HA rest_command, curl) all send a length, and
    refusing the length-less case keeps the check a header check, no body streaming.
    """

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self._app = app
        self._max = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("method") in ("POST", "PUT", "PATCH"):
            headers = {k.lower(): v for k, v in scope.get("headers", [])}
            length = headers.get(b"content-length")
            if length is None:
                if b"chunked" in headers.get(b"transfer-encoding", b"").lower():
                    response = JSONResponse(
                        status_code=411,
                        content={"detail": "Content-Length required"},
                    )
                    await response(scope, receive, send)
                    return
            elif not length.isdigit() or int(length) > self._max:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": f"request body exceeds {self._max} bytes"},
                )
                await response(scope, receive, send)
                return
        await self._app(scope, receive, send)


def _lean_errors(errors: list[dict]) -> list[dict]:
    """Keep loc/msg/type only. FastAPI's stock body echoes `input` and `ctx`; the
    input may be non-finite (not JSON serialisable, #1 HIGH 3) or carry request
    content that has no business in an error response or in downstream logs."""
    return [
        {
            "loc": list(err.get("loc", ())),
            "msg": str(err.get("msg", "")),
            "type": str(err.get("type", "")),
        }
        for err in errors
    ]


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
    app.add_middleware(BodyLimitMiddleware, max_bytes=MAX_BODY_BYTES)

    @app.exception_handler(RequestValidationError)
    async def _validation_422(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422, content={"detail": _lean_errors(exc.errors())}
        )

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
        except (OwnershipError, RegistryFull) as exc:
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
            # energy is the client's statement; hours follow from the definition's
            # power inside correct (#1 Lows: mis-scaled when the powers differed)
            remaining_hours = standing.correct(
                demand_id,
                remaining_wh=demand.energy_target_wh,
                nominal_power_w=demand.nominal_power_w,
                now=utcnow(),
            )
            scheduler.notify_change()
            return {
                "corrected": True,
                "applies": "next cycle",
                "remaining_hours": remaining_hours,
            }
        reject_standing_squat(standing, demand.id, demand.source)
        try:
            saved = registry.upsert(demand)
        except (OwnershipError, RegistryFull) as exc:
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
            scheduler.notify_off(demand_id)  # MQTT consumers stop now, not next cycle
            scheduler.notify_change()
            return Response(status_code=204)
        try:
            registry.delete(demand_id, source=source)
        except KeyError:
            raise HTTPException(status_code=404, detail="unknown demand")
        except OwnershipError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        scheduler.notify_off(demand_id)
        scheduler.notify_change()
        return Response(status_code=204)

    @app.get("/api/v1/plan")
    def plan():
        raw = view.raw_plan
        return {**(raw or {}), "flexd_meta": {"state": view.state(now=utcnow())}}

    @app.get("/api/v1/plan/demands/{demand_id}")
    def plan_demand(demand_id: str):
        # Gated by the registry (live_demand_view): absent is 404, expired is OFF with
        # expired=true, registered-but-unmapped is "pending next solve".
        now = utcnow()
        dv, status = live_demand_view(registry, view, demand_id, now=now)
        state = view.state(now=now)
        if status == "unknown":
            raise HTTPException(status_code=404, detail="unknown demand")
        if dv is None:  # pending next solve
            return {
                "setpoint_w": 0,
                "on": False,
                "clamped": False,
                "truncated": False,
                "unschedulable": False,
                "state": state,
                "pending": True,
                "expired": False,
            }
        return {
            "setpoint_w": dv.setpoint_w,
            "on": dv.on,
            "clamped": dv.clamped,
            "truncated": dv.truncated,
            "unschedulable": dv.unschedulable,
            "state": state,
            "pending": False,
            "expired": status == "expired",
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
        except (OwnershipError, RegistryFull, TemplateRunWithdrawn) as exc:
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
