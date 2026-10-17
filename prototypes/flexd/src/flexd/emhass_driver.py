"""EMHASS client. POST optim (awaited, single writer upstream) then GET /api/v1/plan.

Guards enforce the spec: adopt a plan only if status=ok, schema version known,
generated_at strictly newer than the last adopted plan, and on first boot (no plan
ever adopted) generated within one cycle of now.
"""

import logging
from datetime import datetime, timedelta

import httpx

log = logging.getLogger(__name__)

OPTIM_TIMEOUT_S = 300.0
# First boot has no last_generated_at to compare against, so a days-old plan that
# /api/v1/plan re-serves after an infeasible first solve would be adopted as current
# (#1 Medium 7). A plan generated within one cycle plus this slack is fresh enough.
FIRST_BOOT_SLACK = timedelta(minutes=5)


def _parse_generated_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class PlanRejected(Exception):
    """Plan response failed a contract guard; do not adopt."""


class EmhassDriver:
    def __init__(self, base_url: str, known_schema_versions: set[str]):
        self._base = base_url.rstrip("/")
        self._known = known_schema_versions

    async def run_cycle(
        self,
        runtimeparams: dict,
        last_generated_at: str | None = None,
        *,
        now: datetime | None = None,
        timestep_min: int | None = None,
    ) -> dict:
        """POST the optim, GET the plan, enforce the adopt-guards.

        Pass last_generated_at whenever any plan was ever adopted; None only
        on true first-run — otherwise a stale previous plan re-served after an
        Infeasible solve would be adopted as fresh. On first run, `now` and
        `timestep_min` bound how old a plan may be (absolute freshness).
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(OPTIM_TIMEOUT_S, connect=10.0)
        ) as client:
            resp = await client.post(
                f"{self._base}/action/naive-mpc-optim", json=runtimeparams
            )
            resp.raise_for_status()
            plan_resp = await client.get(f"{self._base}/api/v1/plan", timeout=10.0)
            plan_resp.raise_for_status()
        plan = plan_resp.json()
        if plan.get("status") != "ok":
            msg = f"plan status is {plan.get('status')!r} (no-run or invalid)"
            log.warning(msg)
            raise PlanRejected(msg)
        version = plan.get("emhass_schema_version")
        if version not in self._known:
            msg = f"unknown emhass schema version {version!r}"
            log.warning(msg)
            raise PlanRejected(msg)
        if not plan.get("generated_at"):
            msg = "ok plan without generated_at"
            log.warning(msg)
            raise PlanRejected(msg)
        if (
            last_generated_at is not None
            and plan.get("generated_at") <= last_generated_at
        ):
            msg = f"plan generated_at {plan.get('generated_at')} not newer than {last_generated_at}"
            log.warning(msg)
            raise PlanRejected(msg)
        if last_generated_at is None and now is not None and timestep_min is not None:
            generated = _parse_generated_at(plan["generated_at"])
            max_age = timedelta(minutes=timestep_min) + FIRST_BOOT_SLACK
            if now - generated > max_age:
                msg = (
                    f"first boot: plan generated_at {plan['generated_at']} is older than "
                    f"one cycle plus slack ({max_age}) relative to {now.isoformat()}"
                )
                log.warning(msg)
                raise PlanRejected(msg)
        return plan

    async def healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base}/healthz")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False
