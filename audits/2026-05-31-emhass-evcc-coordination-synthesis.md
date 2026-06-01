# EMHASS ↔ evcc coordination — verification synthesis for brainstorming

- **Date:** 2026-05-31
- **Purpose:** Integrate all five verification streams into a decision-ready brief for the human-led brainstorming that finalizes the "EMHASS-as-planner / evcc-as-executor" concept. This document **resolves what evidence resolves** and **isolates the genuine forks** a human must decide. It does not choose a plan.
- **Inputs (all read in full):**
  1. `audits/2026-05-31-emhass-side-verification.md` — EMHASS capabilities/gaps *(EMHASS-side)*
  2. `audits/2026-05-31-contributions-evcc-context.md` — what's already conceived in-repo *(repo-context)*
  3. `audits/2026-05-31-evcc-side-verification.md` — evcc seam + execution roadmap *(evcc-side)*
  4. `audits/2026-05-31-evopt-model.md` — evopt MILP deep-read *(evopt)*
  5. `audits/2026-05-31-emhass-extensibility.md` — EMHASS build-effort assessment *(extensibility)*
- **Method note:** Two claims in the original framing were **refuted by source** during verification and are corrected below: (i) evopt's `BatteryConfig` has **no `Type` vehicle/battery field** — the "type" lives only on evcc's internal `batteryDetail` telemetry struct and is never sent to the optimizer; (ii) the evcc optimizer is **sponsor-gated as a whole feature**, not merely on the HTTP auth header.

---

## 1. Executive summary

EMHASS can become the planning brain behind evcc, but the concept's second half — "evcc as executor" — **does not exist in evcc today**: evcc's optimizer integration is explicitly *information-only*, sponsor-gated, and its result drives no charger/battery actuator, with no roadmap, owner, or timeline to change that. So the realistic concept is: **EMHASS does whole-house MILP planning (inside the #789 guard); a glue-layer control loop we build (not evcc's optimizer path) turns the plan into evcc control-API commands.** evopt — the contract EMHASS would imitate to be a drop-in — is a single MILP that treats every asset (incl. EVs) as a generic soft-constrained battery over a variable-width seconds grid; EMHASS is currently single-battery, fixed-step, and hard-constraint. Closing the EV-SoC gap (deferrable-load + SoC accumulator, **L**) and adding a JSON optimization endpoint (**S**) are the high-value, low-invasiveness builds; full multi-battery parity is an **XL** structural refactor that should only be undertaken if genuinely required.

---

## 2. Verified-facts table (load-bearing facts only)

| # | Claim | Verdict | Source audit (file:line / quote) |
|---|---|---|---|
| F1 | evcc's optimizer result is **information-only** — never sets charge current/mode/power | **CONFIRMED** | evcc-side §2: `resp.JSON200` flows only to `site.publish("evopt"/...)` + `battery.Forecast` (`site_optimizer.go:259-286`); whole-repo search finds zero control consumer. Maintainer note in #23042: *"the optimizer is purely information-only … not used to make actual decisions."* |
| F2 | The whole optimizer feature is **sponsor-gated** (not just the auth header) | **CONFIRMED (corrects framing)** | evcc-side §3: `sponsor.IsAuthorized()` guards both call sites (`site.go:814`, `site_api.go:39`) upstream of URI selection |
| F3 | A **custom `OPTIMIZER_URI`** is honored and **removes the 2-day slot cap**; the cap is tied only to the default hosted URL | **CONFIRMED** | evcc-side §4: `if uri == OPTIMIZER_URI { minLen = min(2*96, minLen) }` (`site_optimizer.go:124`) |
| F4 | evopt treats **EV and stationary battery identically** — no `Type` field; EV-ness = a battery carrying soft `s_goal[]` / `p_demand[]` with `d_max=0` | **CONFIRMED (corrects framing)** | evopt §1: `BatteryConfig` dataclass (`optimizer.py:24-38`) + `openapi.yaml:186-271` have no type/enum |
| F5 | evopt is a **single MILP that maximizes** economic benefit; `s_min/s_max`, `s_goal`, `p_demand`, grid limits are all **soft penalties** → essentially never returns Infeasible | **CONFIRMED** | evopt §4-5: penalty/slack vars (`optimizer.py:265-297`); `get_clean_objective_value()` reports penalty-free money (`:589-622`) |
| F6 | evopt **multi-battery is genuinely supported** — N independent SoC chains, one shared power balance, `c_priority` 0..2 as a cost-neutral tie-break | **CONFIRMED** | evopt §3: `for i, bat in enumerate(self.batteries)` vars/SoC (`optimizer.py:126-146, 425-438`), shared balance (`:339-368`) |
| F7 | evopt horizon is a **variable-width, seconds-resolution `dt[]`**; in practice evcc sends **uniform slots except one short leading partial slot** | **CONFIRMED + reconciled** | evopt §2 (`dt=[328,3600,...]`, test 016); evcc-side §4 `timeSteps()` (`site_optimizer.go:636`) emits partial-remainder slot then `SlotDuration` (900s) ×N |
| F8 | evopt units: energy **Wh**, power **W**, durations **seconds**, prices **currency/Wh**; evcc multiplies tariffs ×0.001 (EUR/kWh→currency/Wh) | **CONFIRMED** | evopt §7; evcc-side §4 (`scaleAndPrune(grid,0.001,...)`, `site_optimizer.go:175-176`) |
| F9 | EMHASS is **single battery only** (scalar-hardcoded vars/SOC/balance) | **CONFIRMED** | EMHASS-side Claim 1; extensibility (a) (`optimization.py:801-824, 1120-1260, 991-1016`) |
| F10 | EMHASS deferrable loads have **no SoC state** — only a total-energy target + time window; cannot express "40%→80% by 07:00" | **CONFIRMED** | EMHASS-side Claim 2; extensibility (b) (`optimization.py:1899-1922`) |
| F11 | EMHASS `/action` returns a **plain-text 201 ack, not JSON**; schedule lives in `opt_res_latest.csv` | **CONFIRMED** | EMHASS-side Claim 4; extensibility (c) (`web_server.py:600-668`, `opt_res` discarded at `:519`) |
| F12 | EMHASS uses a **single uniform `time_step`** (minutes) threaded through SOC/energy/cost | **CONFIRMED** | EMHASS-side Claim 5; extensibility (d) (`optimization.py:76-78, 872, 1192`) |
| F13 | evcc loadpoint MODE/plan **does reach** the optimizer request (shapes `PDemand[]`/`SGoal[]`/`CMax`/`SMax`), but a plan beyond the forecast horizon is **silently dropped** | **CONFIRMED (NUANCED)** | evcc-side §1 (`loadpointRequest()` `:368`, `applyPlanGoal()` `:677`) |
| F14 | evcc control API has **no direct watt setpoint** — power is set via amps (min/maxCurrent) + mode + plan/limit SoC | **CONFIRMED** (repo-context; consistent with evcc-side §1 "no watt setpoint") | repo-context "evcc control API"; evcc-side BOTTOM LINE |
| F15 | **No in-repo artifact** specs an EMHASS↔evcc coordination/optimizer-API layer; the EV-flexible-load registry exists only as a *promised* RFC in the `DISC-824` card body; AM-1b (structured `/action` payload) is the nearest enabler, unstarted | **CONFIRMED** | repo-context §4-5, GAPS |
| F16 | **#789 scope guard**: EMHASS core = MILP optimiser; charger modulation / vehicle APIs / evcc control = glue layer, out of core | **CONFIRMED (standing constraint)** | repo-context "Note on the #789 scope guard" |

---

## 3. Architecture concept (placement & flow)

**The demand → plan flow that the evidence supports:**

```
        ┌────────────┐   demand (EV: s_initial, target SoC, deadline,        ┌─────────────────────┐
        │   evcc     │   c_min/c_max; home batt; gt/ft/prices; dt[])         │   EMHASS (planner)  │
        │ (direct car│ ───────────────────────────────────────────────────▶ │  MILP whole-house   │
        │  link +    │                                                       │  day-ahead / MPC    │
        │  realtime  │ ◀─────────────────────────────────────────────────── │  + EV-as-flex-load  │
        │  modulation│   per-slot plan (per-asset power/SoC, grid, cost)     │  with SoC (NEW)     │
        └─────┬──────┘                                                       └─────────────────────┘
              │ control API (/set): mode, minCurrent/maxCurrent,
              │ planSoc/planEnergy, limitSoc, smartCostLimit
              ▼
        ┌──────────────────────────────┐   ← THIS LOOP DOES NOT EXIST IN evcc TODAY (F1).
        │  CONTROL / EXECUTION LOOP     │     evcc's own optimizer path is info-only.
        │  (GLUE LAYER — #789 says      │     Someone (us / Node-RED / a service) must build it,
        │   NOT in EMHASS core)         │     OR drive evcc's /set API directly from the plan.
        └──────────────────────────────┘
```

**Where each piece lives, vs the #789 guard (F16):**
- **Inside the EMHASS-core guard:** the MILP planning extensions — EV-as-flexible-load with SoC (extensibility b), optional multi-storage (a), the JSON endpoint (c), and an evopt-contract mapping shim (d). These are *optimiser* concerns.
- **In the glue layer (out of core):** the control/execution loop that consumes the plan and issues evcc `/set` commands, vehicle/charger awareness, plug-in detection. This is exactly the modulation/vehicle-API territory #789 fences off.

**Relation to Pfad A / B / C and andig's stance (respected, not re-litigated):**
- **Pfad A — drop-in optimizer via `OPTIMIZER_URI`** (point evcc at a self-hosted EMHASS speaking the evopt contract). *Technically open today* (F3: custom URI honored, cap removed) and needs **no evcc change**. **But:** it is sponsor-gated (F2) and, fatally for the "executor" half, evcc would only *display* the EMHASS plan — it would not actuate (F1). Pfad A buys a forecast panel, not control.
- **Pfad B — pluggable/contract-extension in evcc** (a real optimizer-backend abstraction). andig: skeptical-but-not-no. Evidence note: there is currently **no backend abstraction** at all (evcc-side: generated client called directly), so Pfad B is a from-scratch ask.
- **Pfad C — native EMHASS adapter PR into evcc.** andig: qualified-green, PR-first, judged on submission. This is the maintainer-blessed route, but it lands EMHASS *as another info-only optimizer input* unless evcc also gains execution (F1 roadmap: not happening).

**The reframe the evidence forces:** "evcc as executor" presumes evcc acts on the plan. It does not (F1) and has no plan to (evcc-side roadmap). So the concept's execution must be **our glue-layer control loop driving evcc's well-documented `/set` control API** (F14) — independent of whether the *plan delivery* uses Pfad A/B/C.

---

## 4. Decisions RESOLVED by evidence

Each below is settled by a fact; the human need not reopen these (only act on them).

1. **Do not wait for evcc-native execution.** *(resolves "wait vs build")* — F1 + evcc-side roadmap: maintainer documents info-only, lists only model-capability TODOs (no "execute" item), gave no timeline when a user asked to "hand over control," and pointed to a *rejected* third-party integration (#25562). The execution loop must be ours.
2. **The interface basis is the evopt contract, and it is reachable.** *(resolves "what API/shape")* — F3 (custom URI honored, cap removed) + F4-F8 (full contract verified). EMHASS imitating evopt's `OptimizationInput`/`OptimizationResult` is a concrete, documented target.
3. **EV is modeled as a soft-constrained battery, not a typed object.** *(resolves "how to represent the EV in the contract")* — F4. EMHASS must emit/accept `s_goal[]` (soft per-slot SoC goal) + `p_demand[]` (soft per-slot min charge), `d_max=0` for charge-only — *not* invent a vehicle type.
4. **EMHASS must return a usable plan + violation flags, never "Infeasible," to be drop-in.** *(resolves "constraint semantics")* — F5: evopt's soft-penalty design is load-bearing; EMHASS's current hard-constraint/infeasible-prone battery+deferrable model would break evcc's expectations on edge inputs (out-of-band SoC, unreachable goal). This is a behavioral contract, not just a field map.
5. **Units/granularity are mechanical, with one wrinkle.** *(resolves "unit conversion risk")* — F7 + F8 + F12: Wh↔W via dt, currency/Wh↔EUR/kWh ×1000, seconds↔minutes are scalar conversions. The *only* non-mechanical wrinkle is the leading partial slot (F7): evcc's `dt[]` is uniform-except-first, so the adapter can merge/drop the partial slot and hand EMHASS its native uniform `time_step` — **a genuinely variable `dt[]` is NOT required for the evcc path** (this softens extensibility-(d)'s headline blocker for *this* consumer).
6. **The JSON endpoint is cheap and is the output half of any adapter.** *(resolves "how does the plan leave EMHASS")* — F11 + extensibility (c) = **S**: `opt_res` is in hand and discarded at `web_server.py:519`; serialize behind a `?format=json` flag without touching the HA plain-text contract.
7. **Multi-battery is the foundational refactor, and it is XL.** *(resolves "how big is the home-batt + EV co-opt build")* — F6 vs F9 + extensibility (a): single-battery is scalar-hardcoded across vars/balance/SOC-recovery/results + the hybrid-inverter DC-bus coupling (`optimization.py:1090/1092`) has no per-asset AC/DC seam. Treat as a deliberate, separate program — not a side effect of EV support.
8. **EV-with-SoC is achievable without the multi-battery refactor.** *(resolves "must we do (a) before EV support")* — extensibility (b-i) = **L**: extend the deferrable-load loop with an SoC accumulator; the existing time-window mask already gives plug-in/plug-out semantics. V2G is the only thing that forces the battery path (and thus (a)).

---

## 5. OPEN QUESTIONS for brainstorming (genuine forks — options + trade-off, not decided)

**Q1 — Where does the control/execution loop live?**
- (a) **New EMHASS endpoint/daemon** — keeps it in one project; **but** charger modulation in EMHASS violates #789 (F16) and the maintainer-blessed line.
- (b) **Standalone glue service** (our "own layer," which andig explicitly values) — clean #789 placement, full freedom; **but** new component to host/operate.
- (c) **Node-RED** (we already extract production flows from `U:/nodered/flows.json`) — fastest to a working loop, reuses existing infra; **but** logic spread across a visual runtime, harder to version/test.
- *Trade-off axis:* #789-compliance & maintainer-acceptance vs operational simplicity vs time-to-first-working-loop.

**Q2 — How is the plan delivered to evcc: Pfad A vs C (vs neither)?**
- **Pfad A** (self-host EMHASS at `OPTIMIZER_URI`): no evcc PR, works today (F3); **but** sponsor-gated (F2) and only yields a *display* (F1) — pairs *only* with a separate control loop (Q1) to mean anything.
- **Pfad C** (native adapter PR): maintainer-blessed, PR-first; **but** still info-only on landing (F1) and is upstream work on andig's timeline.
- **Neither for delivery** — skip evcc's optimizer entirely; our control loop calls EMHASS directly (JSON endpoint, F11) and drives evcc `/set` (F14). Simplest causal chain; **but** forgoes evcc's native optimizer UI/telemetry surface.
- *Trade-off axis:* maintainer alignment & native UI vs sponsor-gating & info-only dead-end vs directness/control.

**Q3 — EV-SoC modeling approach: deferrable-load+SoC (b-i) vs EV-as-2nd-battery (b-ii)?**
- (b-i) **L**, charge-only, reuses most-tested code path, independent of (a); **but** no V2G.
- (b-ii) **M bespoke / L–XL general**, gets V2G free; **but** inherits (a)'s single-battery hardcoding and the recovery state machine fits a car poorly.
- *Trade-off axis:* invasiveness/independence-from-(a) vs V2G capability.

**Q4 — Multi-storage build scope & sequencing — do we commit to (a) at all, and when?**
- Options: never (model EV only via b-i); now (foundational, unblocks true parity + V2G); deferred (after EV-SoC proves the use case).
- *Trade-off:* (a) is **XL** with a hard DC-bus-coupling knot (F7→extensibility hardest-blocker) and a config-schema migration touching the #869-regression render path; against that, only (a) delivers genuine home-batt + N-EV co-optimization and evopt multi-battery parity (F6).

**Q5 — Soft-constraint conversion: how far does EMHASS adopt evopt's never-Infeasible model?**
- Options: full soft-penalty rewrite of battery+deferrable constraints (true drop-in, F5); partial (soft only on the EV-SoC goal); none (accept that edge inputs can return Infeasible and handle upstream).
- *Trade-off:* drop-in fidelity & UX robustness vs scope of MILP changes.

**Q6 — Also pursue a contract-extension PR to andig (Pfad B)?**
- Options: yes (push for a real optimizer-backend abstraction so EMHASS is a first-class backend); no (stay in our own layer). Evidence: no abstraction exists today (from-scratch), and andig is skeptical-but-not-no.
- *Trade-off:* upstream legitimacy/longevity vs effort into a skeptical maintainer's uncertain acceptance, while execution is still info-only regardless.

**Q7 — How does this sequence against AM-1 / AM-1b / #824?**
- AM-1 (generic `/action` openapi) is gated on AC-4/#914 merge and models only the *generic* action; **AM-1b** (structured `/action/dayahead-optim` request+response) is the nearest enabler of an evopt mapping but is unstarted, blocked on AC-2b/AC-2c (F15, repo-context §1). #824 is the EV-use-case discussion that motivates EV-flex-load.
- *Trade-off:* fold the JSON endpoint (c) + EV-SoC (b-i) into the existing AM-1b/#824 corridor (coherent roadmap, but waits on AC-2b/2c + #914), vs run the coordination build as a parallel track (faster, but risks schema divergence from AM-1b).

---

## 6. Next-steps menu (effort + dependencies + strategic-goal served)

Strategic goals referenced: **G-EV** = native EV/EVCC integration; **G-LLM** = LLM-ready machine-readable surface. *(per `project_strategic_goals` memory)*

| # | Build item | Effort | Depends on | Serves |
|---|---|---|---|---|
| N1 | **JSON optimization endpoint** — serialize `opt_res` behind `?format=json` (`web_server.py:515-521`) | **S** | none | G-EV (output half of adapter), G-LLM (machine-readable plan) |
| N2 | **EV-as-flexible-load with SoC** — deferrable-load + SoC accumulator (b-i), reuse window mask for plug-in | **L** | none (independent of multi-batt) | G-EV (closes the SoC-goal gap; #824) |
| N3 | **evopt-contract mapping shim** — `OptimizationInput`→runtime params, `opt_res`→`OptimizationResult`, unit conversions, merge leading partial slot | **L** (shell) | N1 (output), N2 (s_goal), uniform-dt confirmed (✓ for evcc, F7) | G-EV (drop-in delivery, Pfad A/C) |
| N4 | **Glue-layer control loop** — consume plan, drive evcc `/set` (mode/current/planSoc) | **M–L** (glue, out of core) | a plan source (N1 or N3) | G-EV (the missing executor, F1) |
| N5 | **Soft-constraint hardening** — never-Infeasible behavior on EV goal/SoC band + violation flags | **M** (scoped to EV path) / **L–XL** (full) | N2 | G-EV (true drop-in fidelity, F5) |
| N6 | **Multi-storage co-optimization** — home batt + N EV as separate assets | **XL** | resolves DC-bus-coupling knot + config-schema migration | G-EV (V2G, multi-EV; only if required by Q4) |
| N7 | **Contract-extension / native adapter PR to evcc** (Pfad B/C) | **M–L** (PR) + upstream-dependent | N3 | G-EV (upstream legitimacy; maintainer-gated) |

A defensible *minimal* path implied by the evidence (for the human to accept/reject, not pre-decided): **N1 → N2 → N4**, optionally **N3** for evopt-shaped delivery, with **N5** as the drop-in-fidelity upgrade and **N6/N7** reserved for explicit V2G/upstream goals.

---

## 7. Risks / remaining unknowns

- **R1 — Sponsor gate (F2) blocks Pfad A's value even if technically open.** A non-sponsor never reaches a custom `OPTIMIZER_URI`; and even a sponsor gets only a display (F1). *Unknown:* whether the user's evcc instance is sponsor-authorized (user is an EVCC sponsor per memory — likely yes, but the gate still yields info-only).
- **R2 — Execution loop is unbudgeted in #789 terms.** The control loop is glue (Q1), but if any of it creeps into EMHASS core it breaches the guard and the maintainer line. Placement discipline is a live risk.
- **R3 — Plan-beyond-horizon silently dropped (F13).** evcc drops a `SGoal` whose plan time exceeds the forecast horizon (`applyPlanGoal` `:702`). A coordination design relying on long-deadline EV plans must ensure EMHASS's horizon covers the deadline, or the goal vanishes without error.
- **R4 — Soft vs hard constraint mismatch (F5) is a correctness risk, not just UX.** If EMHASS returns Infeasible where evopt would return a penalized best-effort, a drop-in deployment fails exactly on the edge inputs (out-of-band SoC, unreachable deadline) the user hits in practice. Scope of N5 is the open lever.
- **R5 — Variable `dt[]` for non-evcc consumers.** The "uniform-except-leading-partial-slot" reconciliation (F7) holds *for evcc*. Any other evopt client that sends genuinely variable `dt[]` would re-expose the XL horizon-model rewrite (extensibility d). The adapter must validate uniformity and reject/degrade otherwise.
- **R6 — Config-schema migration blast radius (N6).** Turning the flat scalar battery block into an asset list touches the param_definitions SoT and the config-UI render path that already caused the #869 regression. Multi-storage carries that regression risk.
- **R7 — Upstream timing & schema drift (Q7).** Running the coordination build ahead of AM-1b risks the evopt mapping diverging from the structured `/action` schema AM-1b will define; running behind it waits on AC-2b/AC-2c + #914.
- **Unverified / not in scope of these audits:** whether evcc's `/set` control API can be driven at the cadence/granularity a per-slot plan needs in practice (latency, mode-vs-current interplay) — verified only at the field level (F14), not behaviorally; and the operational hosting model for N4 (where the glue loop runs) is undecided.

---

*End of synthesis. All five audits are uncommitted in `audits/` for human review.*
