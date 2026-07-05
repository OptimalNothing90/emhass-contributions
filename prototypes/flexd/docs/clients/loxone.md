# Loxone

flexd talks to Loxone through the Simple-API: plain `text/plain` values over HTTP, matching what
a Loxone Miniserver's Virtual Outputs and Virtual Inputs expect natively. No JSON, no
authentication headers — everything is a query-string GET or POST.

Replace `<flexd-host>` below with the flexd container's address on your LAN (e.g. its Docker
host IP) and `8321` with your configured port.

## 1. Register a demand — Virtual Output (HTTP)

Create a **Virtual Output** in Loxone Config with the command:

```
POST /simple/demands/register?source=loxone&id=<load>&power_w=<power_w>&energy_wh=<energy_wh>&deadline_in_h=<deadline_in_h>
```

against `http://<flexd-host>:8321`.

Parameters:

| Param | Meaning |
|---|---|
| `source=loxone` | ownership tag — only requests with this `source` may later update or withdraw this demand id |
| `id` | a stable identifier for this load, `[a-z0-9-]`, e.g. `dishwasher` |
| `power_w` | nominal power draw in watts while running |
| `energy_wh` | total energy this run needs, in Wh |
| `hours` | alternative to `energy_wh`: how many hours at `power_w`. **If both `energy_wh` and `hours` are given, `energy_wh` wins** — `hours` is silently ignored, not an error |
| `deadline_in_h` | hours from now by which the energy must be delivered (default 8 if omitted) |

Example: a dishwasher needing 1.4 kWh at up to 2000 W, done within 8 hours:

```
POST /simple/demands/register?source=loxone&id=dishwasher&power_w=2000&energy_wh=1400&deadline_in_h=8
```

A successful call returns `1`. In Loxone Config, wire this Virtual Output's command to a
Virtual Input Text or a program-start block that fires once when the load should start being
considered.

![TODO screenshot: Virtual Output configuration dialog]

## 2. Mark it done, or refresh — a second Virtual Output

When the appliance actually finishes (or you want to cancel), call:

```
POST /simple/demands/dishwasher/done?source=loxone
```

To extend an active demand's expiry without changing its target (e.g. a periodic "still
running" heartbeat), call refresh instead:

```
POST /simple/demands/dishwasher/refresh?source=loxone
```

`source` must match the one used at registration, or the call is rejected.

![TODO screenshot: second Virtual Output for done/refresh]

## 3. Read the setpoint — Virtual Inputs (HTTP polling)

Create two **Virtual Inputs** polling every 30 seconds:

```
GET /simple/demands/dishwasher/setpoint
GET /simple/demands/dishwasher/on
```

`setpoint` returns the current recommended power draw in watts as a bare number (e.g. `2000`).
`on` returns `1` or `0`.

**These poll endpoints never return an HTTP error, even for an id flexd has never seen.** They
always return a number, so a Virtual Input's error handling never has to special-case flexd:
`0` covers "off", "unknown id", and "expired" alike. Mutating endpoints (register, done,
refresh, template start) behave the opposite way — they fail loudly with a non-2xx status so a
misconfigured Virtual Output is visible in the Miniserver's log.

![TODO screenshot: Virtual Input polling configuration]

## 4. Watchdog — fall back when flexd or EMHASS is unhealthy

Poll `/simple/status` (also 30 s) into a Virtual Input Text:

```
GET /simple/status
```

It returns one of four values:

| Value | Meaning |
|---|---|
| `ok` | last cycle succeeded; setpoints are current |
| `stale` | flexd is running but hasn't had a successful cycle in a while (2× the configured cycle interval by default) |
| `no-run` | no demands are currently registered, so there's nothing to schedule — not an error |
| `down` | EMHASS was unreachable on the most recent cycle |

**`status` is more eager than plan staleness by design**: it flips to `down` after a *single*
failed cycle (an HTTP error talking to EMHASS), whereas `stale` only appears after multiple
missed cycles. Treat anything other than `ok` as "don't trust the setpoint right now" — wire a
Loxone logic block so that `status != "ok"` overrides the setpoint/`on` inputs and falls back to
the device's own native control logic (see the [fail-safe section](#fail-safe-contract) below).

**`/simple/status` cannot show `down` while no demands are registered** — a cycle with an empty
registry skips before it ever contacts EMHASS, so a permanently-empty registry reads `no-run`,
not `down`. Don't rely on the watchdog alone to catch "EMHASS is broken and nobody registered
anything yet"; register at least one demand (or check `/healthz` directly) if that distinction
matters to you.

![TODO screenshot: watchdog logic block]

## 5. Trigger a template — one button, deadline computed for you

If you've configured a [trigger template](../../flexd.yaml.example) (e.g. `dishwasher`) in
`flexd.yaml`, wire a Loxone start button to:

```
POST /simple/templates/dishwasher/start?source=loxone
```

flexd works out the deadline from the template's `deadline_rules` and the current time — you
don't need to compute `deadline_in_h` yourself. Pressing the button again while the instance is
still active is a harmless refresh (the deadline is not recomputed); to restart with a fresh
deadline, call `done` first, then `start` again.

## Worked example: dishwasher

1. Physical dishwasher start button (or a Loxone program-start sensor) triggers the Virtual
   Output from step 1 (or step 5, if you're using the template) — this registers the demand.
2. The two Virtual Inputs from step 3 drive a relay or a smart plug's on/off state, gated by the
   watchdog from step 4.
3. When the dishwasher's program-end contact fires, a second Virtual Output calls
   `/simple/demands/dishwasher/done?source=loxone` — the demand is withdrawn and its topics
   clear.

## Fail-safe contract

- Actuate only when `state == "ok"` **and** `on == 1`.
- On `stale`, `down`, `no-run`-when-you-expected-active, or any request timeout: fall back to
  the device's own native logic (for a dishwasher: just run the program now, don't wait on
  flexd).
- Never expose flexd, EMHASS, or the MQTT broker to the internet unauthenticated. Keep them on
  the LAN, or put a reverse proxy with authentication in front. flexd's `source` parameter is an
  ownership *convention*, not an authentication mechanism — it assumes a trusted LAN. Per-source
  tokens are planned for a later phase, not the MVP.
- Simple-API poll endpoints (`setpoint`, `on`, `status`) never return a 404 or other HTTP error —
  they always return a value. Mutating endpoints (`register`, `done`, `refresh`,
  `templates/.../start`) fail loudly with a non-2xx status instead of failing silently.
