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
# register a demand via the simple API, deadline 4h out
curl -fsS -X POST "http://localhost:8321/simple/demands/register?source=e2e&id=e2e-load&power_w=2000&energy_wh=1000&deadline_in_h=4"
# trigger a cycle and read the per-demand view
curl -fsS -X POST http://localhost:8321/api/v1/cycle
curl -fsS http://localhost:8321/api/v1/plan/demands/e2e-load
curl -fsS http://localhost:8321/simple/status
echo "E2E OK"
