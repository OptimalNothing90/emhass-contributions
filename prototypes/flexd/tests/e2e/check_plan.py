"""Solver-level assertions for the compose e2e run (release gate, not pytest).

Reads flexd's adopted plan from GET /api/v1/plan and checks the per-slot
semi-continuous contract against two known demands:

  slot 0  non-modulating  2000 W, 1200 Wh, 4 h  -> 2 whole timesteps at exactly 2000 W
  slot 1  modulating      3000 W, 1800 Wh, 4 h  -> fractional hours, 0 <= P <= 3000

Usage: python tests/e2e/check_plan.py [FLEXD_URL] [TIMESTEP_MIN]
Exit 0 when every check passes, 1 otherwise. Prints one PASS/FAIL line per check.
"""

import json
import sys
import urllib.request

FLEXD = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8321"
TIMESTEP_MIN = int(sys.argv[2]) if len(sys.argv) > 2 else 30
STEP_H = TIMESTEP_MIN / 60

NONMOD_P, NONMOD_STEPS = 2000.0, 2
MOD_P, MOD_WH = 3000.0, 1800.0
TOL_WH = 1.0  # solver tolerance on energy equalities


def get(path: str):
    with urllib.request.urlopen(f"{FLEXD}{path}", timeout=10) as resp:
        body = resp.read().decode()
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def main() -> int:
    plan = get("/api/v1/plan")
    failures = 0

    def check(name: str, ok: bool, detail: str) -> None:
        nonlocal failures
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
        if not ok:
            failures += 1

    state = plan.get("flexd_meta", {}).get("state")
    generated_at = plan.get("generated_at")
    check(
        "(c) plan adopted",
        state == "ok" and bool(generated_at),
        f"state={state!r} generated_at={generated_at!r} schema={plan.get('emhass_schema_version')!r}",
    )
    records = plan.get("plan") or []
    check("(c) plan has records", len(records) > 0, f"{len(records)} records")
    if not records:
        return 1
    missing = [k for k in ("P_deferrable0", "P_deferrable1") if k not in records[0]]
    check(
        "(c) deferrable columns present",
        not missing,
        f"missing={missing} keys={sorted(records[0])[:12]}...",
    )
    statuses = {r.get("optim_status") for r in records}
    check(
        "(b) optim_status Optimal",
        statuses == {"Optimal"},
        f"optim_status values={sorted(map(str, statuses))}",
    )

    p0 = [float(r.get("P_deferrable0", 0) or 0) for r in records]
    p1 = [float(r.get("P_deferrable1", 0) or 0) for r in records]
    bad0 = [
        (i, v)
        for i, v in enumerate(p0)
        if not (abs(v) < 1e-6 or abs(v - NONMOD_P) < 1e-3)
    ]
    check(
        "(d) non-modulating slot is 0 or 2000 W in every record",
        not bad0,
        f"off-grid values={bad0[:5]} on_steps={[i for i, v in enumerate(p0) if v > 0]}",
    )
    bad1 = [(i, v) for i, v in enumerate(p1) if v < -1e-6 or v > MOD_P + 1e-3]
    check(
        "(d) modulating slot within [0, 3000] W",
        not bad1,
        f"out-of-range={bad1[:5]} nonzero={[(i, round(v, 1)) for i, v in enumerate(p1) if v > 0]}",
    )
    e0 = sum(p0) * STEP_H
    e1 = sum(p1) * STEP_H
    check(
        "(e) non-modulating energy = 2 slots x 2000 W x 0.5 h",
        abs(e0 - NONMOD_STEPS * NONMOD_P * STEP_H) < TOL_WH,
        f"sum(P0)*dt={e0:.1f} Wh (expected {NONMOD_STEPS * NONMOD_P * STEP_H:.0f} Wh, over-delivery vs 1200 Wh requested)",
    )
    check(
        "(e) modulating energy = 1800 Wh",
        abs(e1 - MOD_WH) < TOL_WH,
        f"sum(P1)*dt={e1:.1f} Wh (expected {MOD_WH:.0f} Wh)",
    )
    print(
        json.dumps(
            {
                "timestamps": [r["timestamp"] for r in records[:10]],
                "P0": p0[:10],
                "P1": [round(v, 1) for v in p1[:10]],
            }
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
