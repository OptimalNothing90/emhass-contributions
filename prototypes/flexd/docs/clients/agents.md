# LLM agents

flexd exposes a full OpenAPI schema, so an agent with a generic HTTP tool can discover and call
its API without any flexd-specific integration code.

- OpenAPI schema: `http://<flexd-host>:8321/openapi.json`
- Interactive docs (Swagger UI): `http://<flexd-host>:8321/docs`

Point an agent framework's OpenAPI/tool-loader at the schema URL, or just paste it into a
system prompt if the agent only has a raw HTTP-request tool.

## 1. Register an EV charging demand

```bash
curl -X POST http://<flexd-host>:8321/api/v1/demands \
  -H "Content-Type: application/json" \
  -d '{
    "id": "ev-garage",
    "source": "agent",
    "type": "ev",
    "flexibility": "shiftable",
    "energy_target_wh": 20000,
    "nominal_power_w": 7400,
    "deadline": "2026-07-06T07:00:00+02:00",
    "expires_at": "2026-07-06T09:00:00+02:00"
  }'
```

`id` must be unique and match `[a-z0-9][a-z0-9-]{0,63}`. `source` is an ownership tag — only
requests carrying the same `source` may later update or delete this demand. `expires_at` is
mandatory: flexd sweeps and drops any demand past its expiry, so a crashed or disconnected agent
never leaves a stale charging target active indefinitely.

## 2. Read the plan for that demand

```bash
curl http://<flexd-host>:8321/api/v1/plan/demands/ev-garage
```

```json
{
  "setpoint_w": 7400,
  "on": true,
  "clamped": false,
  "truncated": false,
  "unschedulable": false,
  "state": "ok",
  "pending": false
}
```

Field meanings:

| Field | Meaning |
|---|---|
| `setpoint_w` / `on` | current recommended power and on/off state |
| `pending: true` | the demand is registered but hasn't been through a solve cycle yet — not an error, just not scheduled *yet*. Treat as "off" until it flips to `false` |
| `clamped: true` | the deadline falls beyond flexd's prediction horizon; the demand may legitimately schedule later as the rolling horizon advances |
| `truncated: true` | the requested energy was cut down to fit the available window so this one demand couldn't make the whole solve infeasible |
| `unschedulable: true` | the deadline/window is expired or degenerate; the load was deactivated for this plan rather than left silently unconstrained |
| `state` | overall plan health: `ok`, `stale`, or `no-run` — see the fail-safe contract below. `down` (EMHASS unreachable) is NOT surfaced here — an agent that needs it must also check `GET /healthz` (field `emhass`) or `/simple/status` |

A 404 here means the `id` was never registered (or has already expired and been swept) — not
"no plan yet". Compare against `GET /api/v1/demands` to check whether the id still exists in the
registry at all.

## 3. Withdraw the demand

```bash
curl -X DELETE "http://<flexd-host>:8321/api/v1/demands/ev-garage?source=agent"
```

`source` must match the value used at registration. A `409` means a different source owns this
id — an agent should treat that as "not mine to touch" rather than retrying.

If `id` names a standing demand (configured under `standing_demands` in `flexd.yaml`), a
`source=config` `PUT` is a correction to today's remaining target, not a registration — to zero
out a standing demand's remaining for today use `done`/`DELETE`, not a 0-energy correction (REST
rejects `energy_target_wh: 0`).

## Example agent prompt

```
You control EV charging via flexd, a REST service at http://<flexd-host>:8321.
Its OpenAPI schema is at http://<flexd-host>:8321/openapi.json.

When the user asks to charge the car by a certain time:
1. POST /api/v1/demands with source="agent", type="ev", the requested energy_target_wh
   and nominal_power_w, a deadline matching the user's request, and expires_at set a
   couple of hours past the deadline as a safety margin.
2. Confirm back to the user once the POST returns 201.
3. If asked for status, GET /api/v1/plan/demands/{id} and report on/setpoint_w/state in
   plain language — say "not scheduled yet" if pending is true, and "past the planning
   horizon, will be scheduled as the plan rolls forward" if clamped is true.
4. If asked to cancel, DELETE /api/v1/demands/{id}?source=agent.

Never invent field names outside the schema. If a call returns a 4xx, report the error
detail to the user instead of retrying silently.
```

## Fail-safe contract

- Actuate (or report as actionable) only when `state == "ok"` **and** `on == true`.
- On `stale`, `no-run`, or a request timeout: report that flexd's recommendation is not
  currently trustworthy, and defer to the device's own native/manual control rather than acting
  on a stale setpoint. The REST `state` field never reads `down` — to detect an unreachable
  EMHASS, also check `GET /healthz` (field `emhass`) or `/simple/status`, and treat `down`
  there the same way.
- Never expose flexd, EMHASS, or the MQTT broker to the internet unauthenticated. Keep them on
  the LAN, or put a reverse proxy with authentication in front — an agent with unauthenticated
  internet access to flexd's REST API could register or withdraw arbitrary demands. flexd's
  `source` field is an ownership convention, not authentication; per-source tokens are planned
  for a later phase.
- Simple-API poll endpoints (`setpoint`, `on`, `status`) never return a 404 or other HTTP error —
  they always return a value. The REST API's mutating endpoints (`POST`/`PUT`/`DELETE`
  `/api/v1/demands/...`) fail loudly with a non-2xx status and a JSON error detail instead of
  failing silently.
