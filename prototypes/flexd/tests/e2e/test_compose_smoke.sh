#!/usr/bin/env bash
# Compose E2E: register a demand, trigger a cycle, read the per-demand view.
# Requires docker compose; not part of pytest CI (manual + release gate).
set -euo pipefail
cd "$(dirname "$0")/../.."
cp flexd.yaml.example flexd.yaml
docker compose up -d --build
trap 'docker compose down -v' EXIT
for i in $(seq 1 30); do
  curl -fsS http://localhost:8321/healthz && break
  sleep 2
done

# healthz: infra truth regardless of EMHASS configuration state.
healthz_body="$(curl -fsS http://localhost:8321/healthz)"
echo "$healthz_body" | grep -q '"status":"ok"' || {
  echo "FAIL: healthz did not report status:ok — $healthz_body" >&2
  exit 1
}

# register a demand via the simple API, deadline 4h out
register_body="$(curl -fsS -X POST "http://localhost:8321/simple/demands/register?source=e2e&id=e2e-load&power_w=2000&energy_wh=1000&deadline_in_h=4")"
[ "$register_body" = "1" ] || {
  echo "FAIL: register did not return 1 — $register_body" >&2
  exit 1
}

# trigger a cycle and read the per-demand view
curl -fsS -X POST http://localhost:8321/api/v1/cycle
# solver-level assertion (result ok + setpoint) requires a configured EMHASS — release-gate checklist, not smoke
plan_body="$(curl -fsS http://localhost:8321/api/v1/plan/demands/e2e-load)"
echo "$plan_body" | grep -q '"pending"' || {
  echo "FAIL: per-demand plan view missing 'pending' field — $plan_body" >&2
  exit 1
}

status_body="$(curl -fsS http://localhost:8321/simple/status)"
echo "$status_body" | grep -qE '^(ok|stale|no-run|down)$' || {
  echo "FAIL: /simple/status returned an unexpected value — $status_body" >&2
  exit 1
}

echo "E2E OK"
