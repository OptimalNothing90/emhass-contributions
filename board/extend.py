#!/usr/bin/env python3
"""
Extend EMHASS AI agents board with contributor-focused items:
- Update AG-7 (AGENTS.md) body with explicit Limits & Gotchas section
- Add AG-onboarding (Contributor AI-Coder doc)
- Add AG-pr-readiness (Pre-PR Guard Skill)
- Add AG-B1 (Public Skills Plugin distribution)
- Sync items.json
"""
import json
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_FILE = Path(__file__).parent / "2026-04-28-emhass-board-migration-items.json"
PROJECT_ID = "PVT_kwHOAfZrVs4BV1jU"
AG7_DRAFT_ID = "DI_lAHOAfZrVs4BV1jUzgKbxAY"


def gh(args, stdin=None):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True, encoding="utf-8", input=stdin)
    if r.returncode != 0:
        raise RuntimeError(f"gh failed: {r.stderr}")
    return r.stdout


def update_draft(draft_id: str, body: str) -> None:
    q = '''mutation($body: String!) {
      updateProjectV2DraftIssue(input: {
        draftIssueId: "''' + draft_id + '''"
        body: $body
      }) { draftIssue { id title } }
    }'''
    out = gh(["api", "graphql", "-f", f"query={q}", "-f", f"body={body}"])
    print(f"  updated {json.loads(out)['data']['updateProjectV2DraftIssue']['draftIssue']['title']}")


def add_draft_with_fields(title, body, fields, option_ids, field_ids):
    body_esc = body.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    title_esc = title.replace("\\", "\\\\").replace('"', '\\"')
    q = f'''mutation {{
      addProjectV2DraftIssue(input: {{
        projectId: "{PROJECT_ID}"
        title: "{title_esc}"
        body: "{body_esc}"
      }}) {{ projectItem {{ id }} }}
    }}'''
    out = gh(["api", "graphql", "-f", f"query={q}"])
    item_id = json.loads(out)["data"]["addProjectV2DraftIssue"]["projectItem"]["id"]
    for fname, fval in fields.items():
        fq = f'''mutation {{
          updateProjectV2ItemFieldValue(input: {{
            projectId: "{PROJECT_ID}"
            itemId: "{item_id}"
            fieldId: "{field_ids[fname]}"
            value: {{ singleSelectOptionId: "{option_ids[fname][fval]}" }}
          }}) {{ projectV2Item {{ id }} }}
        }}'''
        gh(["api", "graphql", "-f", f"query={fq}"])
    print(f"  created [{item_id}] {title}")
    return item_id


with DATA_FILE.open(encoding="utf-8") as f:
    data = json.load(f)
field_ids = data["_meta"]["field_ids"]
option_ids = data["_meta"]["option_ids"]

AG7_BODY = '''Top-level `AGENTS.md` at repo root — vendor-neutral rules consumed by Claude Code, Cursor, Aider, Copilot, Codex. Workflow-Demo gate cleared via #808 reply 2026-04-27 (David: "rich in concrete examples, that was what was needed").

## Section 1 — Canonical commands
- Build / install / dev setup (per `pyproject.toml`)
- Test: `pytest tests/`
- Lint: ruff (when AM-5 lands; until then, document current process)
- Docs build: Sphinx (per `docs/conf.py`)
- Container build: Docker / Podman (per `Dockerfile`)

## Section 2 — Stage map
Reference Meisterplan §11 stage entry points:
- input_data: `command_line.py:939`
- pv_forecast: `command_line.py:697`
- load_forecast: `command_line.py:754`
- lp_build: `optimization.py:2496`
- solve: `optimization.py:2635`
- publish: `command_line.py:2351`

## Section 3 — Don't-touch rules
- `action_logs.txt` format: `web_server.py:135` parses `split(" ", 1)[0] == "ERROR"`. Format break = error-detection break.
- `utils.get_logger`: handler-proliferation guard pending (U-4). Don't add ad-hoc handlers.
- Two parallel logging subsystems (CLI `utils.get_logger` + Web `app.logger`). Logging changes touch both or land in neither.
- `param_definitions.json`: structured surface, additive changes only (track via AC-2a/AC-2b/AC-2-fix).

## Section 4 — Maintainer scope corridors
Per Discussion #808 + Issue #789:
- **Threat model**: code-injection, NOT auth-bypass / data-leakage. Endpoints reading in-memory state are OK; FS/DB/shell-out is not.
- **EMHASS = MILP optimiser** (#789). EVCC, OCPP, vehicle APIs, charger modulation = OUT of core.
- **Glue layer is agnostic** — Node-RED / MQTT / HA / Automations equivalent. Don't wire HA-specific paths into core.
- **Zero-config default not break** — add-on must continue to work with default configuration after every change.

## Section 5 — Limits & Gotchas (read this if you are an AI coder or working with one)

**AI coders find code locations and produce candidate changes. Domain experts decide whether something is a bug or design.** Empirical evidence from 2026-04-26 schema audit: 8 candidate findings → 4 confirmed bugs (PR-able), 4 needed maintainer judgment (issue-first). Skipping the human-in-the-loop step produces ~50% noise.

**Issue-first triggers** — file an issue (NOT a PR) when:
- Behavior changes in any visible way (output values, log format, error messages)
- A magic constant or sentinel might be intentional ("=0 means no constraint?", "negative value treated as disabled?")
- A condition looks wrong but might encode a domain convention you don't know (AC vs DC stack power, charge vs discharge sign conventions)
- Code touches optimization.py, retrieve_hass.py, or forecast.py beyond ~3 lines

**Always verify before claiming done:**
- Sign conventions (P_grid > 0 means import? export? — check; don't assume)
- Units in the wild (HA scales SOC ×100; CSV uses 0..1 — different)
- Test reproducer present for any behavior-change PR
- Container/UI smoke-test (`docker compose up` + browser config page) if schema or web_server.py changed

**Do not refactor without an issue:**
- Restructuring `optimization.py` (3000+ LOC) without architecture-RFC issue → maintainer reject
- Renaming public API params → breaks downstream consumers; needs migration path
- Adding new dependencies → coordinate via issue first

**Things AI tools commonly hallucinate or get wrong here:**
- Confusing `param_definitions.json` (GUI hint metadata) with `config_defaults.json` (authoritative defaults)
- Inventing solver / CVXPY APIs that do not exist in the pinned version
- Suggesting Pydantic v2 patterns when the codebase is still v1 (or vice versa — check `pyproject.toml`)
- Flagging the `if not handlers` guard in get_logger as missing without checking if the file is already imported elsewhere

**Token / context limits** — large files (`optimization.py`, `command_line.py`) exceed comfortable context for many models. Use `repomix` (npx repomix) for full-repo context if your tool supports it; otherwise scope your reading to specific functions.

## Section 6 — Conventions
- Documentation style: Soft Diátaxis (https://diataxis.fr/) — tutorials / how-to / reference / explanation, pragmatically not strictly four-quadrant. See `docs/study_cases/` for the worked example.
- Commit messages: prefix with type (`fix`, `docs`, `feat`, `chore`) per recent maintainer practice.
- Account hygiene: contributors using personal+org GH accounts should switch with `gh auth switch` before push and back afterward.

## Section 7 — Where to find more
- `llms.txt` (Sphinx-generated) — top-level routing manifest for LLMs
- `docs/study_cases/` — Diátaxis-soft worked examples per persona
- `docs/superpowers/specs/` (in OptimalNothing90/loxonesmarthome) — design specs that fed concrete PRs (visible audit trail)
- Project board: https://github.com/users/davidusb-geek/projects/2 — coordination + scope corridors visible per card

## Sequencing
- Open issue first explaining the AGENTS.md proposal with a draft outline (this body's section list).
- After maintainer green-light, PR the file.
- Mention `repomix` as on-demand tool, not committed artefact.
- Cross-link from `docs/study_cases/index.md` and `CONTRIBUTING.md` if it exists.

Coordinate with AC-5 (llms.txt extension) and AG-onboarding (human-facing contributor doc) — same #808 Layer-1 deliverable theme.'''

NEW_ITEMS = [
    {
        "id": "AG-onboarding",
        "title": "AG-onboarding: AI-coder contributor onboarding doc",
        "body": '''Human-facing companion to AG-7 AGENTS.md. Where AGENTS.md instructs the **agent**, this doc instructs the **contributor driving the agent**. Different audience, different concerns.

Lives at: `docs/contributing/ai-coders.md` (or section in `CONTRIBUTING.md` if one exists).

Structure:

1. **How to use Claude Code / Cursor / Aider with this codebase**
   - Recommended skills (link to public plugin once AG-B1 ships)
   - `repomix` for full-repo context loading
   - Setup snippets — Python venv, ruff config, pytest invocation
   - When to use which agent (refactor vs review vs explain)

2. **Decision tree: issue-first vs PR-direct**
   - Visible question flow chart (1 page)
   - Examples: U-1 → issue-first; U-3 → PR-direct; AC-2a → issue-first then PR

3. **What AI WONT tell you about EMHASS**
   - Sign conventions (P_grid, P_batt) — verify in code
   - HA scaling traps (SOC ×100 vs 0..1)
   - MILP infeasibility — symptom often hides actual constraint that's wrong
   - Carnot model has implicit assumptions (no defrost cycle modeling, etc.)
   - Thermal battery `q_input_start=0` infeasibility landmine (was PR #785)
   - Two parallel logger subsystems (CLI + Web) — touch both or none

4. **Self-check before opening a PR**
   - Did I file an issue first if behavior changes?
   - Did I run pytest locally?
   - Did I check sign conventions?
   - Is my PR scoped to ONE concern?
   - Did I link the issue?
   - Did I write a reproducer if behavior-change?
   - Did I check maintainer-scope-corridors? (#808/#789 quick-link)

5. **How to know when you do NOT know**
   - Red flags that mean stop and ask:
     - "AI says this is a bug but I cant explain why in my own words"
     - "I cant tell what unit this number is in"
     - "I dont know which subsystem owns this"
   - In those cases: file an issue with the question; do NOT PR.

6. **Where to find help**
   - GitHub Discussions
   - Issue templates (link)
   - This board (link with read-only view URL)

Tone: friendly, factual, NOT condescending. Assumes contributor is competent but new to EMHASS specifics. Length: ~1500 words target, keep readable.

Sequencing: depends on AG-7 being merged first (this doc references AGENTS.md sections). Issue-first per usual.

Coordinate with AC-5 (Sphinx llms-full.txt) — possibly add a contributor-onboarding entry there too.''',
        "Status": "Ideas",
        "Category": "B: End-User-Ops",
        "Phase": "Phase 1.5",
        "Priority": "P1",
        "Effort": "M",
        "Scope": "Upstream",
    },
    {
        "id": "AG-pr-readiness",
        "title": "AG-pr-readiness: Pre-PR guard skill (local + future plugin)",
        "body": '''Local Claude Code skill that runs before `gh pr create`. Checks the in-flight changes against AGENTS.md conventions and maintainer-scope-corridors. Fails loud if something is missing.

Lives at: `.claude/skills/emhass-pr-readiness/SKILL.md` (loxonesmarthome local). Public plugin variant covered by AG-B1 if uptake justifies it.

Checks (initial set — extend over time):
- Behavior-change detected (code outside `tests/`, `docs/`, comments-only) → require linked issue in branch description or commit body
- Test files touched if `optimization.py`, `forecast.py`, or `command_line.py` modified beyond ~3 lines
- `action_logs.txt` format contract not broken (regex check on any logger format string change)
- `param_definitions.json` changes additive only (no key removals, no type changes for existing keys)
- Maintainer-corridor checks:
  - No `import home_assistant`-style hard dependency added
  - No EVCC / OCPP / charger code in core directories
  - No new shell-out calls (subprocess) in web_server.py or command_line.py
  - No new endpoints under `/action/*` without security note
- Branch name follows convention (`fix/`, `feat/`, `docs/`, `chore/`)
- Commit messages follow maintainer prefix convention
- Account check: `gh auth status | grep "Active.*OptimalNothing90"` before push

Output format:
```
[OK]    test coverage present
[OK]    branch name fix/xyz
[WARN]  no linked issue in branch description (consider issue-first)
[FAIL]  param_definitions.json: key removed (`set_use_legacy_solver`) — additive only
```

Effort:
- Skill writeup: S
- Check logic (Python helpers in skill references): M
- CI variant (GitHub Action) for after-PR-open: M (separate item if needed)

Sequencing: after AG-7 AGENTS.md merged (skill reads from it). Issue-first if going public; can run local-only first, then promote to AG-B1 plugin if useful.

Out of scope:
- Linting / type-checking — handled by AM-5 DevX-stack (ruff, mypy)
- Test-coverage % calculation — separate concern
- Auto-fix attempts — only diagnose, do not modify code''',
        "Status": "Ideas",
        "Category": "B: End-User-Ops",
        "Phase": "Phase 5",
        "Priority": "P2",
        "Effort": "M",
        "Scope": "Local",
    },
    {
        "id": "AG-B1",
        "title": "AG-B1: Public skill plugin distribution (anonymized variants)",
        "body": '''Anonymized public variants of local AG-1 / AG-2 / AG-3 skills, distributed via Claude Code Plugin Marketplace. From Meisterplan §3.3 B.2.

Goal: lower barrier for ANY EMHASS end-user to use AI-assisted troubleshooting / config-validation / plan-explanation, without needing the OptimalNothing90 local Loxone/Tibber/EVCC stack.

Skills to publish (in order of readiness):
1. **emhass-troubleshoot-public** — anonymized AG-1 (deployed locally 2026-04-27). Reads action_logs.txt + last-run banner + (optionally) /api/last-run JSON. Removes Loxone/Tibber/Influx-specific paths. Generic.
2. **emhass-config-validate-public** — depends on AC-2a (unit field) + AC-2b (runtime params). Pre-push schema check. Until AC-2a merges: skip.
3. **emhass-plan-explain-public** — depends on AC-1 (plan-output schema doc) being committed. Until AC-1 merges: skip.

Distribution:
- Repo: separate from EMHASS-main (to keep vendor-format files out of upstream repo per #808 reply scope clarification)
- Likely name: `OptimalNothing90/claude-code-emhass-plugin` or community-suggested
- Manifest: Claude Code plugin format (YAML + skill markdown)
- Installation: `claude code plugin install <repo>` (per Plugin Marketplace docs once available)

Coordination:
- Do NOT touch davidusb-geek/emhass repo for this — vendor-Format files would bloat upstream per Meisterplan §1.5 repo-strategy.
- Mention in AGENTS.md (AG-7) Section 7 once first skill is published.
- Mention in AG-onboarding doc once published.

Sequencing:
- After AG-7 + AG-onboarding merged (so users discover the plugin via AGENTS.md)
- AC-3 (/api/last-run) ideally available so emhass-troubleshoot-public has structured input not just log-tail

Effort: M per skill (anonymization + testing on a non-personal setup), so 3 × M total. Initial only emhass-troubleshoot, then more after dependent items ship.

Out of scope:
- Cursor / Copilot variants — separate plugin per IDE if appetite
- AG-4 (anomaly), AG-5 (calibrate) — too coupled to specific Carnot model + InfluxDB schema; less generic-able''',
        "Status": "Ideas",
        "Category": "B: End-User-Ops",
        "Phase": "Phase 5",
        "Priority": "P2",
        "Effort": "M",
        "Scope": "Local",
    },
]

print("=== Updating AG-7 body with Limits & Gotchas section ===")
update_draft(AG7_DRAFT_ID, AG7_BODY)

print("\n=== Adding new cards ===")
new_ids = {}
for item in NEW_ITEMS:
    print(f"{item['id']}:")
    fields = {k: item[k] for k in ("Status", "Category", "Phase", "Priority", "Effort", "Scope")}
    new_ids[item["id"]] = add_draft_with_fields(item["title"], item["body"], fields, option_ids, field_ids)

print("\n=== Sync items.json ===")
existing = {it["id"]: it for it in data["items"]}
existing["AG-7"]["body"] = AG7_BODY
print("  AG-7 body updated")

# Insert new items after AG-7 in the JSON
ag7_idx = next(i for i, it in enumerate(data["items"]) if it["id"] == "AG-7")
for new in reversed(NEW_ITEMS):
    json_entry = {"id": new["id"], "title": new["title"], "type": "draft", "body": new["body"],
                  "Status": new["Status"], "Category": new["Category"], "Phase": new["Phase"],
                  "Priority": new["Priority"], "Effort": new["Effort"], "Scope": new["Scope"]}
    data["items"].insert(ag7_idx + 1, json_entry)
    print(f"  added {new['id']} to items.json")

with DATA_FILE.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print(f"  items.json: {len(data['items'])} items total")

print("\n=== Done ===")
