# ioBroker

flexd's MQTT topics are the same regardless of consumer, so the ioBroker path is mostly
configuration: point the `mqtt` adapter at the same broker flexd uses, and read/write the
`flexd/` topic tree from there.

## 1. `mqtt` adapter instance

Create (or reuse) an `mqtt` client adapter instance pointed at the broker configured in
`flexd.yaml`'s `mqtt:` block (the bundled Mosquitto, or your own):

- **Host / Port** — the broker's address, e.g. `mosquitto` / `1883` if you're on the same
  docker-compose network, or the broker's LAN IP/port otherwise.
- **Subscribe** to `flexd/#` (or narrow it to `flexd/plan/#` and `flexd/availability` if you
  don't need to inspect flexd's raw plan or error events).

Once connected, the same topics documented for [Home Assistant](home-assistant.md#1-mqtt-sensors)
appear as ioBroker states under the adapter's namespace, e.g.:

```
mqtt.0.flexd.plan.demands.dishwasher.setpoint
mqtt.0.flexd.plan.demands.dishwasher.on
mqtt.0.flexd.plan.state
mqtt.0.flexd.availability
```

Wire these into a VIS view, a script, or a Blockly rule exactly like any other ioBroker state.
`flexd.plan.state` carries the raw cycle result, so besides `ok`/`stale`/`no-run`/`down` it can
also read `skipped` or `rejected` — treat anything other than `ok` as not-ok.

## 2. Register a demand via REST — javascript adapter

For registering, updating, or withdrawing demands, call flexd's Simple-API directly from a
`javascript` adapter script rather than going through MQTT (simpler request/response semantics
for a one-shot action):

```javascript
// Register a dishwasher demand: 1400 Wh at up to 2000 W, done within 8 hours.
const url =
  "http://<flexd-host>:8321/simple/demands/register" +
  "?source=iobroker&id=dishwasher&power_w=2000&energy_wh=1400&deadline_in_h=8";

request.post(url, (err, response, body) => {
  if (err || response.statusCode >= 300) {
    log(`flexd register failed: ${err || body}`, "error");
    return;
  }
  log(`flexd register ok: ${body}`); // "1" on success
});
```

Withdraw the same way against `POST /simple/demands/dishwasher/done?source=iobroker` when the
appliance finishes. See the [Loxone guide](loxone.md#1-register-a-demand--virtual-output-http)
for the full parameter reference (`power_w`, `energy_wh` vs `hours`, `deadline_in_h`) — the
Simple-API itself is identical across every client.

If your ioBroker instance's `javascript` adapter doesn't have the `request` module available,
use `fetch` (Node.js 18+ runtimes) or the adapter's built-in `httpGet`/`httpPost` sendTo pattern
instead — the URL and query parameters are unchanged.

## Fail-safe contract

- Actuate only when `state == "ok"` **and** `on == 1`.
- On `stale`, `down`/`offline`, `no-run`, or a request timeout: fall back to the device's own
  native logic rather than trusting a stale setpoint.
- Never expose flexd, EMHASS, or the MQTT broker to the internet unauthenticated. Keep them on
  the LAN, or put a reverse proxy with authentication in front. flexd's `source` claim is an
  ownership convention, not authentication — it assumes a trusted LAN. Per-source tokens are a
  later phase.
- Simple-API poll endpoints (`setpoint`, `on`, `status`) never return a 404 or other HTTP error —
  they always return a value. Mutating endpoints (`register`, `done`, `refresh`,
  `templates/.../start`) fail loudly with a non-2xx status instead of failing silently.
