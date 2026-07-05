"""EMHASS client. POST optim (awaited, single writer upstream) then GET /api/v1/plan.

Guards enforce the spec: adopt a plan only if status=ok, schema version known,
generated_at strictly newer than the last adopted plan.
"""

import logging

import httpx

log = logging.getLogger(__name__)

OPTIM_TIMEOUT_S = 300.0


class PlanRejected(Exception):
    """Plan response failed a contract guard; do not adopt."""


class EmhassDriver:
    def __init__(self, base_url: str, known_schema_versions: set[str]):
        self._base = base_url.rstrip("/")
        self._known = known_schema_versions

    async def run_cycle(
        self, runtimeparams: dict, last_generated_at: str | None = None
    ) -> dict:
        async with httpx.AsyncClient(timeout=OPTIM_TIMEOUT_S) as client:
            resp = await client.post(
                f"{self._base}/action/naive-mpc-optim", json=runtimeparams
            )
            resp.raise_for_status()
            plan_resp = await client.get(f"{self._base}/api/v1/plan")
            plan_resp.raise_for_status()
        plan = plan_resp.json()
        if plan.get("status") != "ok":
            raise PlanRejected(
                f"plan status is {plan.get('status')!r} (no-run or invalid)"
            )
        version = plan.get("emhass_schema_version")
        if version not in self._known:
            raise PlanRejected(f"unknown emhass schema version {version!r}")
        if (
            last_generated_at is not None
            and plan.get("generated_at") <= last_generated_at
        ):
            raise PlanRejected(
                f"plan generated_at {plan.get('generated_at')} not newer than {last_generated_at}"
            )
        return plan

    async def healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base}/healthz")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False
