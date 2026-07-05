"""Trigger templates: appliance recipes with start-time-dependent deadlines."""

import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flexd.config import TemplateDefinition
from flexd.models import Demand

log = logging.getLogger(__name__)


def _to_time(hhmm: str) -> time:
    h, m = map(int, hhmm.split(":"))
    return time(h, m)


class TemplateManager:
    def __init__(
        self,
        definitions: list[TemplateDefinition],
        *,
        tz: str,
        registry,
        default_ttl_s: int,
    ):
        self._defs = {d.id: d for d in definitions}
        self._tz = ZoneInfo(tz)
        self._registry = registry
        self._ttl = default_ttl_s

    def start(self, template_id: str, *, source: str, now: datetime) -> Demand:
        defn = self._defs[template_id]  # KeyError -> transport maps to 404

        # Re-trigger while active = pure refresh (spec): deadlines are computed exactly
        # once at first trigger; a flapping event must not move them across a rule boundary.
        existing = self._registry.get(template_id)
        if existing is not None and existing.expires_at > now:
            return self._registry.refresh(template_id, source=source)

        local = now.astimezone(self._tz)
        rule = self._match_rule(defn, local.time())

        if rule is None:
            deadline = now + timedelta(hours=defn.default_finish_in_h)
            window_start = None
        else:
            deadline = self._next_occurrence(local, _to_time(rule.finish_by))
            window_start = None
            if rule.not_before is not None:
                nb_local = local.replace(
                    hour=_to_time(rule.not_before).hour,
                    minute=_to_time(rule.not_before).minute,
                    second=0,
                    microsecond=0,
                )
                nb = nb_local.astimezone(timezone.utc)
                if nb > now and nb < deadline:
                    window_start = nb

        demand = Demand(
            id=template_id,
            source=source,
            type=defn.type,
            energy_target_wh=defn.energy_wh,
            nominal_power_w=defn.nominal_power_w,
            interruptible=defn.interruptible,
            window_start=window_start,
            deadline=deadline,
            expires_at=deadline + timedelta(seconds=self._ttl),
            ttl_s=self._ttl,  # refresh bumps by exactly default_ttl_s, not by time-to-deadline
        )
        return self._registry.upsert(demand)

    def _match_rule(self, defn: TemplateDefinition, t: time):
        for rule in defn.deadline_rules:
            a, b = (
                _to_time(rule.if_started_between[0]),
                _to_time(rule.if_started_between[1]),
            )
            inside = (a <= t < b) if a < b else (t >= a or t < b)  # wrap bracket
            if inside:
                return rule
        log.warning(
            "template %s: no bracket for %s, using default_finish_in_h", defn.id, t
        )
        return None

    def _next_occurrence(self, local_now: datetime, target: time) -> datetime:
        # nonexistent local times (DST spring-forward) resolve via fold-0: shifted
        # forward one hour — accepted for appliance deadlines
        candidate = local_now.replace(
            hour=target.hour, minute=target.minute, second=0, microsecond=0
        )
        if candidate <= local_now:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    def has(self, template_id: str) -> bool:
        return template_id in self._defs
