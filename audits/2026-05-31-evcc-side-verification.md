# evcc-side verification — optimizer seam audit

**Date:** 2026-05-31
**Method:** Read-only source verification of `evcc-io/evcc` (`master`) via `gh api` (raw contents), `gh search code`, `gh issue view`, `gh pr list`. No writes/PRs to evcc. Primary file `core/site_optimizer.go` read in full (786 lines). Helpers traced to `core/site.go`, `core/site_api.go`, `core/site_tariffs.go`, `core/solar.go`, `core/loadpoint_plan.go`, `core/optimizer.md`.
**Scope:** Verify the evcc→optimizer seam claims (demand-mode mapping, execution status, sponsor gating, units/horizon helpers) and the execution roadmap (Epic #23042).
**Status:** Complete. All four Task-1 claims resolved with quoted code. Roadmap resolved from the epic body + comments + PR survey.

Line numbers below refer to the `master` revision of `core/site_optimizer.go` fetched on 2026-05-31 (786 lines total). Where I cite other files I name the file explicitly.

---

## 1. DEMAND-MODE MAPPING — VERDICT: NUANCED (mode IS the driver, but it sets demand/goal/cap fields, not a watt setpoint; and crucially nothing is executed — see §2)

The loadpoint MODE is read inside `loadpointRequest()` via `lp.GetMode()` and switched on directly. So MODE *does* reach the optimizer — it shapes the `BatteryConfig` that is sent. It is **not** applied as a control action by this code (the result is never enforced; §2). The mapping:

```go
// core/site_optimizer.go:368  loadpointRequest()
bat := optimizer.BatteryConfig{
	ChargeFromGrid: true,
	CMin:           float32(lp.EffectiveMinPower()),  // W
	CMax:           float32(lp.EffectiveMaxPower()),  // W
	DMax:           0,
	SMin:           0,
}
...
// :397
bat.SInitial = float32(v.Capacity() * lp.GetSoc() * 10)   // Wh (kWh*1000 * soc%/100)
bat.SMax     = max(bat.SInitial, float32(maxSoc))          // Wh
```

`maxSoc` (the SoC/energy ceiling) is computed *before* the mode switch from `EffectiveLimitSoc()` / `GetLimitEnergy()`:

```go
// :390
maxSoc := v.Capacity() * 1e3 // Wh
if v := lp.EffectiveLimitSoc(); v > 0 {
	maxSoc *= float64(v) / 100
} else if v := lp.GetLimitEnergy(); v > 0 {
	maxSoc = v * 1e3
}
```

The mode switch (`:419`):

```go
switch lp.GetMode() {
case api.ModeOff:
	bat.CMax = 0                                 // disable charging (drops the loadpoint: add() is gated on req.CMax>0)
case api.ModeNow:
	demand = continuousDemand(lp, minLen)        // forced max charging
case api.ModeMinPV:
	demand = continuousDemand(lp, minLen)        // forced min charging
	demand = applySmartCostLimit(lp, demand, grid, minLen)
	site.applyPlanGoal(lp, &bat, minLen)
case api.ModePV:
	demand = applySmartCostLimit(lp, nil, grid, minLen)  // no floor demand
	site.applyPlanGoal(lp, &bat, minLen)
}
if demand != nil {
	bat.PDemand = prorate(demand, firstSlotDuration)   // Wh per slot
}
```

Mapping the four user intents to concrete `BatteryConfig` fields:

- **(a) charge with PV (`ModePV`)** — sets `ChargeFromGrid=true`, `CMin/CMax` = min/max power (W), `SInitial`/`SMax` (Wh). `PDemand` is left empty (the `nil` arg to `applySmartCostLimit`) *unless* a smart-cost limit is configured, in which case affordable slots get `maxPower/slotsPerHour` Wh demand. `applyPlanGoal` may set `SGoal[slot]` + raise `SMax` if a plan exists. So plain PV mode = no forced demand; the MILP decides charging from the solar `Ft` series and prices.
- **(b) charge now (`ModeNow`)** — `PDemand` = `continuousDemand(lp,…)` which fills every slot with `EffectiveMaxPower()/slotsPerHour` Wh (forced max), **only if** `lp.GetStatus()==api.StatusC` (vehicle actively connected+charging); otherwise `continuousDemand` returns `nil` (`:505`). No `applyPlanGoal`/`applySmartCostLimit`. Fields: `PDemand` (Wh/slot), `CMin/CMax`, `SInitial/SMax`.
- **(c) charge to target SoC by tomorrow 07:00** — handled by `applyPlanGoal()` (called in `ModeMinPV`/`ModePV` only), NOT a dedicated mode:
  ```go
  // :677  applyPlanGoal()
  goal, socBased := lp.GetPlanGoal()
  if goal <= 0 { return }
  if vehicle := lp.GetVehicle(); socBased && vehicle != nil {
  	goal *= vehicle.Capacity() * 10   // soc% -> Wh
  } else {
  	goal *= 1000                      // kWh -> Wh
  }
  ts := lp.EffectivePlanTime()
  if ts.IsZero() { return }
  slot := int(time.Until(ts) / tariff.SlotDuration)
  if slot >= 0 && slot < minLen {
  	bat.SGoal = make([]float32, minLen)
  	bat.SGoal[slot] = float32(goal)         // Wh required AT that slot
  	bat.SMax = max(bat.SMax, float32(goal))
  }
  ```
  So a "target SoC by time T" becomes a single non-zero entry in `SGoal[]` at the slot index nearest T, plus an `SMax` bump. `GetPlanGoal()` (`core/loadpoint_plan.go:95`) returns the vehicle plan SoC (socBased=true) or `getPlanEnergy()` limit (socBased=false). **Caveat:** if the plan time is beyond the forecast horizon (`slot >= minLen`) the goal is silently dropped (logged DEBUG only, `:702`). Also note `applyPlanGoal` is only reached in MinPV/PV — a plan set while in `ModeNow` is ignored by the optimizer request.
- **(d) charge when price < X ct/kWh** — `applySmartCostLimit()` (`:707`), reached in `ModeMinPV`/`ModePV`:
  ```go
  costLimit := lp.GetSmartCostLimit()
  if costLimit == nil { return demand }
  ...
  for i := range maxLen {
  	if grid[i].Value <= *costLimit {
  		demand[i] = float32(maxPower / slotsPerHour)   // Wh/slot in affordable slots
  	}
  }
  ```
  i.e. it injects max-power `PDemand` into exactly the slots whose grid price is at/below the user's `smartCostLimit`. The X-ct threshold itself never crosses to the optimizer as a parameter; evcc pre-resolves it into per-slot demand. (Function is flagged `// TODO remove once smart cost limit usage becomes obsolete`, `:706`.)

**Fields never set from loadpoints:** `CPriority`, `PA` is set uniformly for every battery in `add()` (`:197`, value `pa = lo.Min(PN)*eta*0.99`, the end-of-horizon Wh value `:181`), `SCapacity` is left zero for loadpoints (only home batteries set it, `:452`) — this is how `batteryForecastSocExtremes` tells home batteries apart from EVs (`SCapacity > 0`, `:338`).

**Does MODE reach the optimizer?** Yes, MODE is read and shapes the request. But the *result* is not applied back to the loadpoint (§2). The actual real-time charging is still driven by evcc's existing loadpoint control loop, independent of the optimizer.

---

## 2. EXECUTION STATUS — VERDICT: CONFIRMED information-only. The result is published for display, never enforced.

`PostOptimizeChargeScheduleWithResponse` is called once (`:241`). Its successful response `resp.JSON200` flows to exactly three sinks, all publish/forecast (display) — never to a charge-current / mode / power setter:

```go
// core/site_optimizer.go:259
site.publish("evopt", optimizerResult{Req: req, Res: *resp.JSON200, Details: details})
...
// :266  derive Full/Empty timestamps per battery for the UI
batResult := batteryResult{ ... Full: matchSoc(...), Empty: matchSoc(...) }
...
// :282
site.publish("evopt-batteries", batteries)
// :284
site.battery.Forecast = site.addBatteryForecastTotals(req.Batteries, resp.JSON200.Batteries)
// :286
site.publish(keys.Battery, site.battery)
```

`addBatteryForecastTotals` (`:291`) only builds a `types.BatteryForecast` (highest/lowest SoC points + a `Limit` flag) for the UI. `matchSoc` carries a `// TODO first slot` and just derives display timestamps.

**Proof of absence of a control consumer (whole-repo search, 2026-05-31):**
- `gh search code --repo evcc-io/evcc "OptimizationResult"` → only `assets/js/types/evcc.ts` (frontend type) and `core/site_optimizer.go`. No backend control code references the result type.
- `gh search code --repo evcc-io/evcc "evopt"` → core hits are limited to `core/site_optimizer.go`; everything else is `assets/js/...` Vue components (`Optimize.vue`, `SocChart.vue`, `PriceChart.vue`, `ChargeChart.vue`, `TimeSeriesDataTable.vue`, `OptimizerModal.vue`, `Site.vue`, `BottomTabs/*`) and `assets/js/types/evcc.ts`.
- `gh search code --repo evcc-io/evcc "BatteryForecast"` → core hits are only `site_optimizer.go`, `site_optimizer_test.go`, `core/types/types.go` (the type def); all other consumers are `assets/js/components/Energyflow/*` and `i18n/*.json`. No loadpoint/charger setter.

There is no path from the optimizer schedule to `SetChargeCurrent`, `SetMode`, `SetLimitSoc`, battery-controller setpoints, or any actuator. The published `evopt`/`evopt-batteries`/`battery.forecast` topics feed only MQTT/UI. **"Information-only" is CONFIRMED** and matches the maintainer's own note in the epic (§ roadmap).

---

## 3. SPONSOR GATING — VERDICT: NUANCED. The *whole run* is sponsor-gated (not just the header), AND the header is set only when authorized. The 2-day cap is what's tied to the URL, not the sponsor check.

The optimizer is invoked from two places, both guarded by `sponsor.IsAuthorized()` before any request is built:

```go
// core/site.go:814  (periodic, inside updateMeters)
if sponsor.IsAuthorized() && optimizerEnabled() && time.Since(optimizerUpdated) >= tariff.SlotDuration {
	go site.optimizerUpdateAsync()
}
```

```go
// core/site_api.go:39  (manual API trigger)
func (site *Site) Optimize() error {
	if !sponsor.IsAuthorized() || !optimizerEnabled() {
		return api.ErrNotAvailable
	}
	go site.optimizerUpdateAsync()
	return nil
}
```

`optimizerEnabled()` additionally requires both the `Experimental` and `Optimizer` settings flags (`core/site.go:821`). So: **no sponsor token ⇒ the optimizer never runs at all**, regardless of URI. Separately, *inside* the request, the bearer header is conditionally attached (this part is what would matter for a self-hosted URL):

```go
// core/site_optimizer.go:241
resp, err := apiClient.PostOptimizeChargeScheduleWithResponse(context.TODO(), req,
	func(_ context.Context, req *http.Request) error {
		if sponsor.IsAuthorized() {
			req.Header.Set("Authorization", "Bearer "+sponsor.Token)
		}
		return nil
	})
```

Net: the seam is sponsor-gated end-to-end at the call sites; the header is only an additional auth layer for the hosted backend. A non-sponsor cannot reach even a custom `OPTIMIZER_URI`, because the gate is upstream of URI selection. (The CONTEXT claim "only the HTTP auth header is gated" is REFUTED; the feature itself is gated.)

---

## 4. UNITS / HORIZON HELPERS — VERDICT: CONFIRMED (with documented details)

**`timeSteps(minLen, now)` → `[]int` seconds.** Builds the `Dt` array. First entry is the partial remainder of the current 15-min slot in seconds (if 1s < remainder < SlotDuration); all subsequent entries are full `tariff.SlotDuration` in seconds (15 min = 900 s):
```go
// :636
eos := now.Truncate(tariff.SlotDuration).Add(tariff.SlotDuration)
if d := eos.Sub(now); d > time.Second && d < tariff.SlotDuration {
	res = append(res, int(d.Seconds()))
}
for i := len(res); i < minLen; i++ {
	res = append(res, int(tariff.SlotDuration.Seconds())) // 15min slots
}
```
**Units: in = slot count + wall clock; out = seconds.** Matches the evopt `dt[]` (seconds) contract.

**`homeProfile(minLen)` → `[]float64` Wh.** Pulls a 15-min import profile averaged over the last 30 days (`ImportProfile`, kWh), tiles it to cover the horizon (+4 days padding), strips past slots (`profileSlotsFromNow`), trims to `minLen`, then converts kWh→Wh by `*1e3`:
```go
// :574
return lo.Map(res, func(v float64, i int) float64 { return v * 1e3 }), nil   // kWh -> Wh
```
**Units: in = kWh profile; out = Wh.** This becomes `Gt` (base load) after prorating.

**`prorate(slots, firstSlotDuration)` → `[]float32`.** Scales only the first slot's energy by `firstSlotDuration / SlotDuration` (because the first slot is partial), passes the rest through, and narrows `float64→float32`. Pure energy scaling, **units unchanged (Wh in, Wh out)**:
```go
// :587
res[0] = res[0] * T(firstSlotDuration) / T(tariff.SlotDuration)
```
Applied to `Gt` (`:173`), `Ft` (`:161`), and loadpoint/battery `PDemand` (`:379,:442,:485`).

**`scaleAndPrune(rates, scale, maxLen)` → `[]float32`.** Multiplies each rate value by `scale` and caps the length at `maxLen`:
```go
// :664
res = append(res, float32(slot.Value*scale))
```
**Units: depend on `scale`.** Used three ways:
- `PN: scaleAndPrune(grid, 0.001, minLen)` (`:175`)
- `PE: scaleAndPrune(feedIn, 0.001, minLen)` (`:176`)
- `scaleAndPrune(solarEnergy, site.solarScale(), minLen)` for solar power before prorate→`Ft` (`:161`).

**Price × 0.001 — CONFIRMED.** Grid and feed-in tariffs (currency per **kWh**) are multiplied by `0.001` to yield currency per **Wh**, matching the evopt `p_N[]`/`p_E[]` contract (currency/Wh) alongside Wh energy. Quoted at `:175–:176` above. (`pa`, the end-of-horizon value at `:181`, is therefore also in currency/Wh × Wh terms consistent with `PN`.)

**`solarScale()`** (`core/site_tariffs.go:167`) returns a unitless correction factor `pv/fcst` (measured PV today ÷ forecast today), defaulting to `1` when there's <0.5 kWh or no forecast. `solarRatesToEnergy` (`:600`) converts the solar power tariff into per-slot Wh via `solarEnergy()` (`core/solar.go:47`, trapezoidal integration, "Result is in Wh"). So `Ft` = `prorate(scaleAndPrune(solarEnergy_Wh, solarScale, minLen), …)` → **Wh per slot**.

**2-day cap tied to the DEFAULT hosted URL only — CONFIRMED:**
```go
// :124
uri := lo.CoalesceOrEmpty(os.Getenv("OPTIMIZER_URI"), OPTIMIZER_URI)
if uri == OPTIMIZER_URI {
	// limit to 2 days for sake of performance
	minLen = min(2*96, minLen)   // 2 days * 96 fifteen-min slots
}
```
The cap (`2*96` = 192 fifteen-minute slots = 2 days) applies **only** when `uri` equals the hardcoded `https://optimizer.evcc.io` (`OPTIMIZER_URI`, `:57`). Setting `OPTIMIZER_URI` to anything else (self-hosted evopt) skips the cap entirely, so a custom backend can optimize the full available forecast horizon. CONFIRMED.

---

## Execution roadmap

**Source:** Epic `evcc-io/evcc#23042` "Epic: Improve experimental optimizer", author **andig** (maintainer), opened **2025-08-17**, state **OPEN** as of 2026-05-31. Body + all comments read in full; linked integration issue #25562 inspected; optimizer-PR history surveyed.

**Verdict: evcc is NOT close to executing the optimizer plan. The official position is explicitly information-only, and there is no scheduled work, owner, or timeline to apply the result to loadpoints/battery.**

Direct evidence — the epic body ends with the maintainer's own note (andig, 2025-08-17):

> **NOTE**: at this time, the optimizer is purely information-only ("what would happen if we actually used this"). It is not used to make actual decisions.

The epic's open checklist items are all **model-capability** work (what the optimizer can *represent*), not execution wiring:

> - [ ] PV AC limitation
> - [ ] Grid Feed-in limitation/ peak shaving
> - [ ] Grid Consumption/ Load management restrictions
> - [ ] Loadpoint priorities
> - Blocked (missing parameters): [ ] Battery charge goal
> - Improvements: [ ] fix batteries flip-flopping

None of these is "apply the schedule to charge current / battery setpoint." There is no "execute the plan" / "hand over control" checklist item at all.

**Demand-side pressure exists, but is unanswered.** A user (dsgrafiniert, undated comment) asked directly:

> I would like to give it a try and hand over control to the optimizer. When can we expect that this possibility is given and Optimizer is not "information only"?

The maintainer did **not** give a timeline. His only response pointed to a *third-party* user integration (andig):

> Maybe @konstantinschubert wants to share his integration (https://github.com/evcc-io/evcc/issues/25562#issuecomment-3580736852)

Inspecting that thread (#25562, by BMMayr, 2025-11-25, CLOSED), KonstantinSchubert (2025-11-26) states his contributions were rejected:

> You were not interested when I offered contributions and repeatedly closed my merge requests.

— to which andig replied "I can't remember any PR for such feature." So the *only* execution story on the table is an external/unmerged integration consuming the published result, not an evcc-native control loop.

**PR survey (2026-05-31) corroborates info-only.** Recent merged optimizer PRs are all model/UI/forecasting/transport, none wire execution:
- #29564 "expose forecasted highest/lowest battery SOC", #29936 "UI: fix line charts", #29784 "PV: track energy metrics and apply forecast scaling", #29510 "increase timeout", #29137 "reduce interval to 15min", #28610 "publish optimizer results as single MQTT message", #28213 "enable by default", #23429 "Battery soc limits", #22944 "Battery max charge/discharge power".
No **open** PR applies the optimizer result to control (open PRs mentioning "optimizer": #27906 NoCharge battery mode, #27780 tariffs/OpenMeteo, #28232 energy demand profile/heating, #21839 zero feed-in — all are *inputs/capabilities*, not actuation).

**Implication for our decision (wait vs. build):** Waiting for native execution is not viable on any visible timeline. evcc deliberately keeps the optimizer as a forecast/preview brain and leaves actuation to its existing loadpoint loop + (for batteries) external control. If we want the optimizer schedule to actually drive hardware, we (or a third party) must build the control loop that consumes the published `evopt` result — exactly the gap KonstantinSchubert tried to fill and was turned away. **Build our own control loop now** is the supported reading; do not block on upstream native execution.

---

## BOTTOM LINE

- **Demand mapping is real but advisory:** loadpoint MODE/plan/smartCostLimit are read in `loadpointRequest()`/`applyPlanGoal()`/`applySmartCostLimit()` and shape `PDemand[]`/`SGoal[]`/`CMax`/`SMax` (Wh, with W power caps) — there is **no watt setpoint**, and a plan beyond the horizon is silently dropped.
- **Execution: CONFIRMED information-only.** `resp.JSON200` flows only to `site.publish("evopt"/"evopt-batteries"/battery)` and `site.battery.Forecast`; whole-repo search shows zero backend consumer that sets charge current/mode/power. The feature is sponsor-gated at the call site (not merely the auth header), and the 2-day horizon cap applies only to the default hosted URL.
- **Roadmap verdict: do not wait.** The maintainer explicitly documents info-only, lists only model-capability TODOs (no "execute" item), gives no timeline when asked, and points users to a rejected third-party integration — so build our own control loop on the published result rather than waiting for native execution.
