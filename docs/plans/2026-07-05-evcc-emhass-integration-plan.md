# evcc ↔ EMHASS integration — consolidated plan

**Date:** 2026-07-05
**Author:** OptimalNothing90
**Basis:** RFC 0001 (S1 sidecar pivot), coordination synthesis `audits/2026-05-31`,
upstream state verified against emhass `master@f11d8dea`, evcc `master@0b3b0a6`,
evcc-io/optimizer `openapi.yaml` (pulled 2026-07-05).
**Supersedes:** the open-ended "Topology A vs B" question tracked since the 2026-06-18 snapshot.

## 1. Verified state of both codebases (2026-07-05)

### EMHASS (`davidusb-geek/emhass`, master `f11d8dea`)

| Capability | Status | Evidence |
|---|---|---|
| Machine-readable plan | **Merged** | `GET /api/v1/plan` (#995, our N1); published iff run is `Optimal`; UTC timestamps; schema `docs/api/v1/plan.schema.json` |
| Run metadata / liveness | Merged | `GET /api/v1/last-run` (#851), `GET /healthz` (#914) |
| Mid-session charge pin | Merged | `def_current_power` (#982/#605), t=0 pin, in release **after v0.17.7** |
| evcc-as-executor recipe | **Merged upstream** | `docs/cookbook/ev_evcc_executor.md` — full Topology-A HA glue, verified field names |
| EV as SoC battery (N2) | Not started | EV still a windowed deferrable load; lossy vs. an SoC curve |
| Load priority MILP | Not started | conflicts fall to cost objective |
| Persistent demand registry | Out of core by design | RFC 0001 S1: registry lives in an external sidecar |

### evcc (`evcc-io/evcc`, master `0b3b0a6`)

| Capability | Status | Evidence |
|---|---|---|
| Built-in optimizer (evopt) | Experimental + **sponsor-gated** | `core/site_optimizer.go`: `sponsor.IsAuthorized() && optimizerEnabled()` (experimental+optimizer settings flags) |
| Optimizer backend | External service, **public + self-hostable** | `evcc-io/optimizer` repo: Python MILP (EOS-inspired), MIT, Dockerfile, port 7050; evcc points at it via `OPTIMIZER_URI` env (default `https://optimizer.evcc.io`, hosted one caps horizon at 2 days) |
| Optimizer → control wiring | **Still info-only** | result is `site.publish("evopt", …)` → UI charts, battery full/empty forecast, MQTT. Nothing actuates. |
| "remote/optimised" loadpoint mode | **Not built** | `api/chargemode.go` still only `off / now / minpv / pv` (the mode scruysberghs asked for in #824, andig said he'd build) |
| Loadpoint control API | Stable, unauthenticated LAN REST | `POST /api/loadpoints/{n}/mode/{mode}` — what the Topology-A recipe drives |

### evcc optimizer contract (Topology-B surface, now fully sized)

`POST /optimize/charge-schedule` — stateless, generic multi-battery MILP:

- **Input:** `batteries[]` (`s_min/s_max/s_initial/s_capacity`, `c_min/c_max/d_max`, per-step `s_goal[]` and `p_demand[]`, end-value `p_a`, `charge_from_grid`/`discharge_to_grid`, `c_priority` 0–2), `time_series` (`dt/gt/ft/p_N/p_E`, Wh + price/Wh), optional grid import/export limits with soft-violation pricing, charging/discharging strategies.
- **Output:** per-battery `charging_power/discharging_power/state_of_charge`, `grid_import/export`, `flow_direction`, limit-violation flags. Status enum incl. `Infeasible`.
- Auth: sponsor Bearer token added by evcc when talking to the hosted instance.

Two things this contract tells us:

1. **It models the EV as an SoC battery with per-step goals and inter-battery `c_priority`** — exactly the two capabilities EMHASS lacks (N2 and priority MILP). Strong prior art to cite when we propose N2 upstream.
2. **It has no notion of deferrable loads, thermal loads, or whole-home context.** Household demand enters only as the aggregate `gt` series. The whole-home MILP remains EMHASS's differentiator.

## 2. The problems, restated against today's state

| # | Problem | State after this fetch |
|---|---|---|
| P1 | No machine-readable plan out of EMHASS | **Solved** (N1 merged) |
| P2 | No documented actuation loop EMHASS→EV | **Solved on paper** — upstream cookbook covers HA glue; our NR/MQTT variant (EV-9) still open |
| P3 | Load contention across sources (evcc / heat pump / HA) — no shared registry | Open; sidecar MVP unblocked by N1, **placement David-gated** |
| P4 | EV modeled lossily as deferrable (no SoC curve) | Open (N2); evopt contract is fresh prior art |
| P5 | Two optimizers, two masters (evcc evopt vs EMHASS) | Structurally defused today: evopt is info-only, so EMHASS-as-planner + evcc-as-executor has no fight. Becomes real the day evcc wires control. |
| P6 | Topology B (evcc calls EMHASS as backend) unsized | **Sized today.** Contract known; see §4 verdict. |

## 3. Decision: Topology A is the plan; Topology B is a tripwire

**Topology A (EMHASS-master, evcc executes)** is the only coupling that actuates anything today, it is David-endorsed, it is now upstream documentation, and it is LesIT1's production setup. Everything we build next builds on it.

**Topology B (evcc-master, EMHASS as optimizer backend)** is technically feasible now — one POST endpoint implementing the openapi above, mapping `batteries[]+time_series` onto an EMHASS solve — but delivers **zero actuation** (evcc discards the result into UI/MQTT), sits behind a **sponsor gate even for self-hosted backends**, and duplicates a working, self-hostable evopt. Building it now would be effort spent on a display feature. We do **not** build it; we watch for the two tripwires below.

**Tripwires that reopen Topology B (watch evcc releases / #29815):**
- evcc wires optimizer output to actual charge control (the "remote/optimised" loadpoint mode, or any apply-path from `evopt` results), **or**
- the sponsor gate is lifted for self-hosted `OPTIMIZER_URI`.

If either fires, the build is a bounded shim: EMHASS-side `POST /optimize/charge-schedule` translating the evopt contract into a dayahead solve and back. Estimate M (one endpoint, pure translation, no state). Until then: no code, one recheck per evcc minor release.

## 4. The plan — four workstreams, strictly ordered by what actuates

### WS1 — Own-setup Topology A bring-up (EV-9, immediate, ungated)

Get the merged pattern running against our own hardware, as the NR/MQTT variant of the upstream cookbook (David greenlit the cookbook angle; LesIT1 owns the HA variant — ours is complementary, not competing).

1. EV as third deferrable in our EMHASS config; `naive-mpc-optim` with runtime `def_total_hours`/`end_timesteps` computed from evcc SoC (Node-RED instead of HA templates).
2. Drive `POST /api/loadpoints/1/mode/{now|off}` from the plan's `P_deferrable` — via Node-RED flow, reading `GET /api/v1/plan` (not HA sensors: we consume our own N1 endpoint, which also dogfoods it).
3. `def_current_power` pin from evcc's live charge power (needs post-v0.17.7 release or master image).
4. Fail-safe per cookbook caveats: watchdog on plan staleness (`generated_at` vs now), default-to-`off` on stale/`no-run`, evcc excluded from house-battery meters.
5. Deliverable: working local loop + the EV-9 cookbook PR (`docs/cookbook/` NR/MQTT variant), field-verified like the upstream one.

**Why first:** it is the only workstream that both actuates today and produces an upstream-valued artifact; it also produces the operational experience the sidecar aggregation logic needs.

### WS2 — Sidecar MVP (unblocked by N1; placement handled honestly)

Scope per RFC 0001 S1: external stateless-core sidecar owning register/refresh/withdraw + `expires_at` lifecycle, folding active demands into one `naive-mpc-optim` runtimeparams payload per cycle, reading the result back via `GET /api/v1/plan`.

- **MVP cut:** single-writer JSON persistence (atomic tmp+rename), REST consumer API, no recurrence, no templates, no MQTT — those are follow-ons per the RFC.
- **First two consumers:** (a) the WS1 EV flow (evcc demand registered on plug-in, withdrawn on target/unplug), (b) one recurring dummy load to prove multi-demand folding.
- **Placement:** still David's steer. Building the MVP in `emhass-contributions/prototypes/` explicitly labeled *pre-placement prototype* does not pre-empt that call. When it runs, ping #931 with the working demo and re-ask the placement question with something concrete to place. No unilateral repo/org creation.
- **Contract guard:** sidecar treats `/api/v1/plan` per its schema — act only on `status=ok`, respect the published-iff-Optimal invariant (D4a), UTC alignment.

### WS3 — N2 upstream: EV as SoC battery (the fidelity gap)

The remaining modeling gap after WS1/WS2 is P4: "40%→80% by 07:00" can't be expressed, only approximated as energy-in-window. Now is the right time to draft N2 because the evopt contract demonstrates the exact target shape (battery with `s_initial/s_goal[]/c_min/c_max`, no discharge for non-V2G) in a shipping adjacent project — a concrete, reviewable formulation rather than an abstract ask.

- PR-first per our standing policy (no RFC-first for strategic items): a scoped PR adding an EV-type deferrable with SoC accumulator, citing evopt's formulation and #824 demand.
- Sequenced **after** WS1 lands (field data on where the deferrable approximation actually hurts strengthens the PR) and independent of WS2.

### WS4 — Topology B tripwire watch (no build)

Per §3: recheck on each evcc minor release — `api/chargemode.go` for a new mode, `site_optimizer.go` for any apply-path from `resp.JSON200` to loadpoint/battery control, sponsor-gate conditions. One grep, five minutes, no standing effort.

## 5. Risks and guards

- **Two-master conflict (P5):** hard rule stays — evcc never controls the house battery; EMHASS owns dispatch. If evcc ever wires evopt to control, WS4 fires and the boundary must be renegotiated *before* enabling both.
- **Happy-path risk (standing concern):** WS1/WS2 must handle `no-run`, `Infeasible`, stale plan, unavailable SoC sensor (→ safe `off`), DST deadline math. These are the exact edge classes the contributor wave keeps shipping without.
- **Sponsor dependency:** nothing in WS1–WS3 depends on evcc sponsorship (loadpoint API is free). Only Topology B does.
- **Placement gate:** WS2 stays a prototype until David steers; the ping happens with a demo, not another abstract ask.

## 6. Sequence summary

```
now ──► WS1 EV-9 bring-up + cookbook PR ──► WS3 N2 SoC PR (field-informed)
   └──► WS2 sidecar MVP prototype ──► #931 ping w/ demo ──► placement steer
   └──► WS4 tripwire watch (passive, per evcc release)
```

Board mapping: WS1 = EV-9 (existing card), WS2 = sidecar-MVP (existing next-pick), WS3 = new card on creation of the PR draft, WS4 = no card (watch note in snapshot memory).
