# flexd SOTA check — comparable projects & standards (2026-07-05)

Pre-implementation scan for the flexd sidecar design
(`docs/superpowers/specs/2026-07-05-flexd-sidecar-design.md`). Three parallel research passes
(Predbat/EOS, FlexMeasures, S2/EEBUS/Matter-DEM); raw notes condensed here. Sources cited in
line; ~2026-07 state.

## Comparable projects

| | Predbat (~290★) | Akkudoktor-EOS (~1.6k★) | FlexMeasures (LF Energy) | flexd (design) |
|---|---|---|---|---|
| Demand intake | static `apps.yaml` + HA helper entities | REST `POST /optimize` per run | REST flex-model per trigger | registry: REST/Simple/MQTT, lifecycle |
| Generic cross-device registry | no (battery+EV bolt-on) | no (fixed device classes) | closest (storage+process models) | **yes (core primitive)** |
| Replanning | rolling 5-min replan | **up-front plans; staleness unsolved** (evcc #20283: andig rejected EOS integration over exactly this) | consumer re-triggers; poll-only | MPC cycle + debounced re-solve on demand change |
| Demand lifecycle/expiry | none | none | job-TTL only (Redis) | `expires_at` mandatory, sweep, done/corrections ledger |
| Manual override / "already ran" | global read-only toggle (coarse) | none (complaint: disconnect mid-plan → stale plan) | full re-trigger with fresh state | per-demand correction (rebased day target), `done_today` |
| Actuation | actuates inverter directly; EV via user automation | recommend-only (like EMHASS) | recommend-only, REST poll | recommend-only, retained MQTT + Simple poll |
| Stack weight | AppDaemon inside HA, huge config surface | server + EOSdash | **Postgres + Redis + workers, multi-container** | 1 container + optional broker |
| EMHASS/evcc interop | none | evcc PoC only, unmerged, contested | none | EMHASS-native; evcc via Topology A |

**Gap confirmation:** none of the three has a generic demand registry with lifecycle + per-demand
correction. The two failure modes flexd's design centers on (plan staleness on mid-session
change; "device already ran" correction) are documented pain points in EOS (evcc discussion
#20283) and Predbat (global read-only toggle as only override; community threads on devices not
following plans).

**Design echo:** FlexMeasures' process scheduler types `INFLEXIBLE|SHIFTABLE|BREAKABLE` map
closely to flexd's `committed|shiftable|(hybrid)` — independent convergence on the same
typology. FlexMeasures expresses deadlines as timestamped `soc-minima`/`soc-targets` entries;
flexd's explicit `deadline` is simpler and covers the home cases.

## Standards (S2 / EEBUS / Matter DEM)

- **S2 (EN 50491-12-2):** CEM↔RM over WebSocket/JSON, 5 control types. **FRBC** (fill-rate,
  storage/thermal) maps almost 1:1 onto flexd's schema: fill level/target profile ≈
  `energy_target_wh`+`deadline`, power_ranges ≈ `p_min_w`/`nominal_power_w`, control-type choice ≈
  `flexibility`. Adoption pilot-stage (AdoptS2, s2-ruby 01/2026, ElaadNL-funded connectors);
  no scheduling-capable consumer OSS ships it yet.
- **EEBUS:** evcc ships it for chargers only (curtailment/§14a), not for scheduling; SPINE
  incentive-table model is heavyweight.
- **Matter 1.3+ DEM:** ForecastStruct/slots + PowerAdjustment + `OptOutState` (user-override
  concept analogous to flexd's `done_today`). HA support = attribute reporting, scheduling not
  shipped as of 2026.07.

**Verdict:** custom JSON demand schema is defensible for the MVP — no standard has
consumer-grade scheduling OSS uptake; even evcc/HA haven't converged. **Least-effort future
alignment: S2/FRBC** (JSON-native, active OSS libs, near-1:1 field mapping). flexd should carry
a documented S2 mapping note so a Phase-3 S2-RM adapter is a wrapper, not a redesign.

## SOTA assessment

State of the art for home-scale OSS on: rolling MPC replanning (EOS lacks), demand lifecycle
(nobody has), per-demand correction semantics (nobody has), fail-safe consumer contract
(Predbat's pain), setup weight (vs FlexMeasures). Not claiming SOTA on: standards compliance
(S2 = Phase-3 path), priority arbitration (EMHASS-gated, Phase 3), within-slot power modulation
(EMHASS model limit, documented).

## Actions taken into the spec

1. `interruptible` field decision → user question (schema stability argument).
2. S2/FRBC alignment note added to spec (doc-only, Phase-3 pointer).
3. Deadline-beyond-horizon clamp rule added to aggregator contract.
