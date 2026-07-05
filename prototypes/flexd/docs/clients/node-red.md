# Node-RED

An importable flow covering the three things most consumers need: register a demand on a
trigger, poll the setpoint and drive a device, and watch flexd's health so you can fall back
when it's unavailable.

All URLs and entity references below are placeholders — replace `<flexd-host>` and
`<your-device-node>` with your own values before deploying. No private hostnames or tokens are
included.

## Import this flow

In Node-RED: hamburger menu → Import → paste the JSON below → Import to a new flow.

```json
[
  {
    "id": "flexd-register-inject",
    "type": "inject",
    "name": "Start dishwasher demand",
    "props": [{ "p": "payload" }],
    "repeat": "",
    "once": false,
    "topic": "",
    "payload": "",
    "payloadType": "date",
    "wires": [["flexd-register-request"]]
  },
  {
    "id": "flexd-register-request",
    "type": "http request",
    "name": "POST /simple/demands/register",
    "method": "POST",
    "ret": "txt",
    "url": "http://<flexd-host>:8321/simple/demands/register?source=node-red&id=dishwasher&power_w=2000&energy_wh=1400&deadline_in_h=8",
    "wires": [["flexd-register-log"]]
  },
  {
    "id": "flexd-register-log",
    "type": "debug",
    "name": "register result",
    "active": true,
    "wires": []
  },
  {
    "id": "flexd-poll-inject",
    "type": "inject",
    "name": "Poll every 30s",
    "props": [{ "p": "payload" }],
    "repeat": "30",
    "once": true,
    "topic": "",
    "payload": "",
    "payloadType": "date",
    "wires": [["flexd-poll-on", "flexd-poll-status"]]
  },
  {
    "id": "flexd-poll-on",
    "type": "http request",
    "name": "GET /simple/demands/dishwasher/on",
    "method": "GET",
    "ret": "txt",
    "url": "http://<flexd-host>:8321/simple/demands/dishwasher/on",
    "wires": [["flexd-on-switch"]]
  },
  {
    "id": "flexd-on-switch",
    "type": "switch",
    "name": "on == 1?",
    "property": "payload",
    "propertyType": "msg",
    "rules": [
      { "t": "eq", "v": "1", "vt": "str" },
      { "t": "eq", "v": "0", "vt": "str" }
    ],
    "checkall": "true",
    "outputs": 2,
    "wires": [["flexd-device-on"], ["flexd-device-off"]]
  },
  {
    "id": "flexd-device-on",
    "type": "change",
    "name": "build ON command",
    "rules": [{ "t": "set", "p": "payload", "pt": "msg", "to": "on", "tot": "str" }],
    "wires": [["<your-device-node>"]]
  },
  {
    "id": "flexd-device-off",
    "type": "change",
    "name": "build OFF command",
    "rules": [{ "t": "set", "p": "payload", "pt": "msg", "to": "off", "tot": "str" }],
    "wires": [["<your-device-node>"]]
  },
  {
    "id": "flexd-poll-status",
    "type": "http request",
    "name": "GET /simple/status",
    "method": "GET",
    "ret": "txt",
    "url": "http://<flexd-host>:8321/simple/status",
    "wires": [["flexd-status-switch"]]
  },
  {
    "id": "flexd-status-switch",
    "type": "switch",
    "name": "status == ok?",
    "property": "payload",
    "propertyType": "msg",
    "rules": [{ "t": "eq", "v": "ok", "vt": "str" }, { "t": "else" }],
    "checkall": "true",
    "outputs": 2,
    "wires": [[], ["flexd-fallback"]]
  },
  {
    "id": "flexd-fallback",
    "type": "change",
    "name": "fall back to native logic",
    "rules": [{ "t": "set", "p": "payload", "pt": "msg", "to": "fallback", "tot": "str" }],
    "wires": [["<your-device-node>"]]
  }
]
```

## Walkthrough

**Register** — the `inject` node fires (wire it to a real trigger in your own flow: a button, a
program-start MQTT message, whatever starts the dishwasher). It calls the Simple-API register
endpoint with `source=node-red` so this flow owns the `dishwasher` demand id. Swap the query
parameters for your load's actual power/energy/deadline; see the
[Loxone guide](loxone.md#1-register-a-demand--virtual-output-http) for what each parameter
means — the Simple-API is identical regardless of which client calls it.

**Poll and drive** — every 30 seconds, two parallel requests go out:

- `GET /simple/demands/dishwasher/on` returns `1` or `0` as plain text. The `switch` node routes
  to an "on" or "off" branch, which you wire to your actual device node
  (`<your-device-node>` — a Zigbee/Z-Wave relay node, another `http request` to Home Assistant,
  an MQTT out node, whatever fits your setup).
- `GET /simple/status` is the watchdog. When it is anything other than `ok`, the fallback branch
  fires instead of the setpoint-driven branch — wire `<your-device-node>` to accept a distinct
  "fallback" message so your device logic can fall back to its own native behavior rather than
  sitting idle.

**Withdraw** — add a mirror of the register `http request` node pointed at
`POST /simple/demands/dishwasher/done?source=node-red`, triggered by your program-end signal.
Not included above to keep the flow minimal; it's the same pattern as register with a different
URL and no query parameters beyond `source`.

If you'd rather work in JSON than plain values, every one of these calls has a REST/JSON
equivalent under `/api/v1/...` — see the [agent guide](agents.md) for the JSON shapes.

## Fail-safe contract

- Actuate only when `state == "ok"` **and** `on == 1`.
- On `stale`, `down`, `no-run`, or a request timeout: fall back to the device's own native logic
  rather than leaving it in whatever state the last successful poll left it in.
- Never expose flexd, EMHASS, or the MQTT broker to the internet unauthenticated. Keep them on
  the LAN, or put a reverse proxy with authentication in front. flexd's `source` parameter is an
  ownership convention, not authentication — per-source tokens are a later phase.
- Simple-API poll endpoints (`setpoint`, `on`, `status`) never return a 404 or other HTTP error —
  they always return a value. Mutating endpoints (`register`, `done`, `refresh`,
  `templates/.../start`) fail loudly with a non-2xx status instead of failing silently.
