# flexd

flexd is a small sidecar that sits between EMHASS and everything in your house that has a
flexible load: an EV charger, a dishwasher, a water heater, a pool pump. Consumers (Loxone,
Home Assistant, ioBroker, Node-RED, LLM agents) register demands — how much energy, by when —
over REST, a plain-value Simple-API, or MQTT. On every cycle flexd folds all currently active
demands into a single EMHASS `naive-mpc-optim` call, so the whole house is optimized together
instead of each device fighting for capacity on its own, then republishes a setpoint per demand.
EMHASS remains the only solver; flexd never optimizes and never actuates. flexd recommends,
consumers actuate — each client guide below documents a fail-safe fallback for when flexd or
EMHASS is unavailable.

**Status:** pre-placement prototype, living here in `emhass-contributions` while its final home
(likely a standalone community-org repo) is decided with EMHASS's maintainer. "flexd" is a
working name, not a final one. Licensed MIT, matching EMHASS itself.

- [Quickstart](docs/quickstart.md) — zero to a running system in about 10 minutes.
- Client guides: [Loxone](docs/clients/loxone.md) · [Home Assistant](docs/clients/home-assistant.md) ·
  [Node-RED](docs/clients/node-red.md) · [ioBroker](docs/clients/iobroker.md) ·
  [LLM agents](docs/clients/agents.md)

## Architecture

```
Consumers                          flexd (one container)                    EMHASS (unchanged, the solver)
─────────                          ────────────────────────────            ────────────────────────────────
Loxone ── HTTP simple ──┐          ┌──────────────────────────┐
HA/ioBroker ── MQTT ────┼──▶ intake│ transports               │
Node-RED ── REST JSON ──┘          │  ├─ rest_api   (FastAPI) │
LLM agent ── REST/OpenAPI ─▶       │  ├─ simple_api (plain)   │
                                   │  └─ mqtt_bridge (aiomqtt)│
                                   ├──────────────────────────┤
                                   │ registry  (JSON, atomic) │
                                   ├──────────────────────────┤
                                   │ scheduler (MPC cycle)    │
                                   │   └─ aggregator          │──POST /action/naive-mpc-optim──▶ MILP
                                   │   └─ emhass_driver       │◀─GET /api/v1/plan────────────────┘
                                   ├──────────────────────────┤
                                   │ plan_view (per-demand    │──publish──▶ MQTT topics
                                   │  setpoints from plan)    │◀──poll──── Loxone / anyone
                                   └──────────────────────────┘
```

Each demand carries an energy target, a nominal power, a deadline, and a mandatory expiry —
a demand a consumer forgets to withdraw simply ages out. flexd persists its own state
(registry, standing-load ledger, last adopted plan) as JSON on a volume; there is no database.
