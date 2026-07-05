# Home Assistant

flexd publishes retained MQTT topics under `flexd/` and accepts commands the same way. This
guide uses manual YAML (`mqtt:` sensors + `rest_command:`) — MQTT Discovery, which would create
these entities automatically, is planned for a later phase but not in the MVP.

Make sure the `mqtt:` block in `flexd.yaml` is enabled and points at the same broker your Home
Assistant `mqtt` integration uses (the bundled Mosquitto, or your own).

## 1. MQTT sensors

```yaml
mqtt:
  sensor:
    - name: "flexd dishwasher setpoint"
      state_topic: "flexd/plan/demands/dishwasher/setpoint"
      unit_of_measurement: "W"
      unique_id: flexd_dishwasher_setpoint

    - name: "flexd plan state"
      state_topic: "flexd/plan/state"
      value_template: "{{ value_json.state }}"
      unique_id: flexd_plan_state

  binary_sensor:
    - name: "flexd dishwasher on"
      state_topic: "flexd/plan/demands/dishwasher/on"
      payload_on: "1"
      payload_off: "0"
      unique_id: flexd_dishwasher_on

    - name: "flexd availability"
      state_topic: "flexd/availability"
      payload_on: "online"
      payload_off: "offline"
      unique_id: flexd_availability
```

Add one `sensor`/`binary_sensor` pair per demand id you care about — `<id>` is whatever you
registered the demand under. `flexd/plan/state` carries a JSON payload
(`{"state": "ok", "generated_at": "..."}`); the `value_template` above extracts just the state
string. Note that this topic carries the raw cycle result: `ok|skipped|rejected|down` — treat
anything other than `ok` as not-ok.
`flexd/availability` is flexd's MQTT last-will topic — `offline` means flexd itself
(not just EMHASS) is unreachable.

## 2. `rest_command` for register / done / refresh

```yaml
rest_command:
  flexd_register:
    url: "http://<flexd-host>:8321/simple/demands/register?source=ha&id={{ id }}&power_w={{ power_w }}&energy_wh={{ energy_wh }}&deadline_in_h={{ deadline_in_h }}"
    method: POST

  flexd_done:
    url: "http://<flexd-host>:8321/simple/demands/{{ id }}/done?source=ha"
    method: POST

  flexd_refresh:
    url: "http://<flexd-host>:8321/simple/demands/{{ id }}/refresh?source=ha"
    method: POST
```

Call from an automation or script with, e.g.:

```yaml
action: rest_command.flexd_register
data:
  id: dishwasher
  power_w: 2000
  energy_wh: 1400
  deadline_in_h: 8
```

`energy_wh` wins over an `hours` alternative if you pass both — see the
[Loxone guide](loxone.md#1-register-a-demand--virtual-output-http) for the full parameter list
(identical Simple-API regardless of client).

If `id` names a standing demand (configured under `standing_demands` in `flexd.yaml`), a
`source=config` correction updates today's remaining target instead of registering a new demand
— to zero out a standing demand's remaining for today use `done`/`DELETE`, not a 0-energy
correction (REST rejects `energy_target_wh: 0`).

## 3. Automation: `on` → switch / EV mode

```yaml
automation:
  - alias: "flexd dishwasher setpoint -> switch"
    trigger:
      - platform: mqtt
        topic: "flexd/plan/demands/dishwasher/on"
    condition:
      - condition: state
        entity_id: sensor.flexd_plan_state
        state: "ok"
    action:
      - service: >-
          {{ 'switch.turn_on' if trigger.payload == '1' else 'switch.turn_off' }}
        target:
          entity_id: switch.<your-dishwasher-switch>
```

The `condition` gate is the fail-safe check from below, inlined: don't act on the `on` topic
unless `flexd/plan/state` currently says `ok`.

## 4. Home Connect dishwasher walkthrough

This is the reference flow for BSH Home Connect appliances (Neff/Bosch/Siemens) using a
[trigger template](../../flexd.yaml.example). It requires **remote start enabled on the
appliance itself** (set on the dishwasher's own control panel or its Home Connect app profile —
Home Assistant's `home_connect` integration cannot start a program unless the appliance has
already armed remote start).

Configure the template once in `flexd.yaml`:

```yaml
templates:
  - id: dishwasher
    type: generic
    nominal_power_w: 2000
    energy_wh: 1400
    interruptible: false
    default_finish_in_h: 8
    deadline_rules:
      - if_started_between: "06:00-12:00"
        finish_by: "15:00"
      - if_started_between: "20:00-06:00"
        not_before: "21:30"
        finish_by: "06:30"
```

`interruptible: false` is stored but NOT yet enforced by the optimizer (MVP): plans may still
split a run; enforcement is a Phase-2 item.

Read as: load the dishwasher and select a program in the morning (06:00–12:00) and flexd targets
"done by 15:00 the same day". Load it in the evening (20:00 through 06:00, the bracket wraps
midnight) and flexd targets "don't start before 21:30, done by 06:30" — letting cheap
overnight power do the work without running the machine in the early evening peak. Any start
time falling in neither bracket uses `default_finish_in_h` (8 hours) with a warning logged at
boot if the gap wasn't intentional. The deadline is computed once, at the first trigger — a
`home_connect` event that fires again for the same run (e.g. on reconnect) is a harmless
refresh, not a new deadline.

**Wiring:**

1. **Program selected / remote start armed** — `home_connect` fires an event when a program is
   selected and the appliance is armed for remote start. An automation on that event publishes
   an empty MQTT message to trigger the template:

   ```yaml
   automation:
     - alias: "Home Connect dishwasher -> flexd trigger"
       trigger:
         - platform: event
           event_type: home_connect_program_selected  # confirm the exact event name/data
             # for your integration version; some setups instead watch a state change on
             # the appliance's "operation state" or "remote control active" entity
       action:
         - service: mqtt.publish
           data:
             topic: "flexd/templates/ha/dishwasher/start"
             payload: ""
   ```

   This publishes to `flexd/templates/{source}/{id}/start` (here `source=ha`) — flexd resolves
   the matching `deadline_rules` bracket against the current local time and registers the
   demand.

2. **Plan says start it** — a second automation watches the resulting `on` topic and starts the
   program once flexd says to:

   ```yaml
   automation:
     - alias: "flexd dishwasher on -> start Home Connect program"
       trigger:
         - platform: mqtt
           topic: "flexd/plan/demands/dishwasher/on"
           payload: "1"
       condition:
         - condition: state
           entity_id: sensor.flexd_plan_state
           state: "ok"
       action:
         - service: home_connect.start_program
           target:
             entity_id: <your-dishwasher-entity>
   ```

3. **Program finished** — when Home Connect reports the program has ended, withdraw the demand
   so it doesn't linger in flexd's registry:

   ```yaml
   automation:
     - alias: "Home Connect dishwasher finished -> flexd delete"
       trigger:
         - platform: event
           event_type: home_connect_program_finished  # confirm against your integration version
       action:
         - service: mqtt.publish
           data:
             topic: "flexd/demands/ha/dishwasher/delete"
             payload: ""
   ```

The exact `home_connect` event names and payload shapes depend on your Home Assistant and
Home Connect integration version — check **Developer Tools → Events** while operating the
appliance to confirm the event type and attributes before wiring the automations above.

## Fail-safe contract

- Actuate only when `state == "ok"` **and** `on == 1`.
- On `stale`, `down`/`offline`, `no-run`, or a request timeout: fall back to the device's own
  native logic (EV: evcc `off` or `pv` mode; dishwasher: just run the program now).
- Never expose flexd, EMHASS, or the MQTT broker to the internet unauthenticated. Keep them on
  the LAN, or put a reverse proxy with authentication in front. flexd's `source` claim is an
  ownership convention, not authentication — it assumes a trusted LAN. Per-source tokens are a
  later phase.
- Simple-API poll endpoints (`setpoint`, `on`, `status`) never return a 404 or other HTTP error —
  they always return a value. Mutating endpoints (`register`, `done`, `refresh`,
  `templates/.../start`) fail loudly with a non-2xx status instead of failing silently.
