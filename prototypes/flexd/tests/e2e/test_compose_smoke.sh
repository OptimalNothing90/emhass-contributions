#!/usr/bin/env bash
# Compose E2E against the pinned EMHASS release: bring the bundle up with the offline
# EMHASS config, register one non-modulating and one modulating demand, trigger a cycle
# and assert the solver-level contract (tests/e2e/check_plan.py).
# Requires docker compose; not part of pytest CI (manual + release gate).
# KEEP=1 leaves the bundle running for manual inspection.
set -euo pipefail
cd "$(dirname "$0")/../.."
COMPOSE=(docker compose -f docker-compose.yml -f tests/e2e/compose.e2e.yml)
"${COMPOSE[@]}" up -d --build
if [ "${KEEP:-0}" != "1" ]; then
  trap '"${COMPOSE[@]}" down -v' EXIT
fi
for i in $(seq 1 30); do
  curl -fsS http://localhost:8321/healthz >/dev/null 2>&1 && break
  sleep 2
done
# EMHASS answers 503 "degraded" until its first run; wait for the server, not for 200.
for i in $(seq 1 30); do
  code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:5000/healthz || true)"
  [ "$code" != "000" ] && break
  sleep 2
done

# healthz: infra truth regardless of EMHASS configuration state.
healthz_body="$(curl -fsS http://localhost:8321/healthz)"
echo "$healthz_body" | grep -q '"status":"ok"' || {
  echo "FAIL: healthz did not report status:ok — $healthz_body" >&2
  exit 1
}

# non-modulating 2000 W / 1200 Wh -> two whole slots; modulating 3000 W / 1800 Wh -> 0.6 h
for q in "id=e2e-dishwasher&power_w=2000&energy_wh=1200&deadline_in_h=4" \
         "id=e2e-heatpump&power_w=3000&energy_wh=1800&deadline_in_h=4&modulating=1"; do
  register_body="$(curl -fsS -X POST "http://localhost:8321/simple/demands/register?source=e2e&$q")"
  [ "$register_body" = "1" ] || {
    echo "FAIL: register did not return 1 — $register_body" >&2
    exit 1
  }
done

cycle_body="$(curl -fsS -X POST http://localhost:8321/api/v1/cycle)"
echo "$cycle_body" | grep -q '"result":"ok"' || {
  echo "FAIL: cycle did not adopt a plan — $cycle_body" >&2
  "${COMPOSE[@]}" logs --no-log-prefix --tail 40 emhass >&2 || true
  exit 1
}

plan_body="$(curl -fsS http://localhost:8321/api/v1/plan/demands/e2e-dishwasher)"
echo "$plan_body" | grep -q '"pending":false' || {
  echo "FAIL: per-demand plan view still pending — $plan_body" >&2
  exit 1
}

status_body="$(curl -fsS http://localhost:8321/simple/status)"
[ "$status_body" = "ok" ] || {
  echo "FAIL: /simple/status is $status_body, expected ok" >&2
  exit 1
}

python tests/e2e/check_plan.py http://localhost:8321 30

echo "E2E OK"
