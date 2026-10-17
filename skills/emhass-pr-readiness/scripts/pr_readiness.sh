#!/usr/bin/env bash
# Mechanical pre-PR checks for a davidusb-geek/emhass fork checkout.
#
#   bash pr_readiness.sh [--base <ref>] [--full-tests | --no-tests]
#
# Run from anywhere inside the checkout, on the branch you intend to push.
# Prints [OK] / [WARN] / [FAIL] lines; exit 1 on any FAIL, 2 when not in an
# EMHASS checkout. Diagnoses only - never modifies the tree.
set -u

BASE=""
TESTS="changed"
for arg in "$@"; do
  case "$arg" in
    --base=*) BASE="${arg#--base=}" ;;
    --base) shift_base=1 ;;
    --full-tests) TESTS="full" ;;
    --no-tests) TESTS="none" ;;
    -h|--help)
      sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
      echo "  --base <ref>    diff base (default: origin/master, else master)"
      echo "  --full-tests    run the whole pytest suite"
      echo "  --no-tests      skip pytest"
      exit 0 ;;
    *) if [ "${shift_base:-0}" = 1 ]; then BASE="$arg"; shift_base=0; fi ;;
  esac
done

fail=0
ok()   { printf '[OK]    %s\n' "$*"; }
warn() { printf '[WARN]  %s\n' "$*"; }
bad()  { printf '[FAIL]  %s\n' "$*"; fail=1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "[FAIL]  not inside a git checkout"; exit 2; }
cd "$ROOT" || exit 2
if [ ! -f src/emhass/__init__.py ] || ! grep -q '^name = "emhass"' pyproject.toml 2>/dev/null; then
  echo "[FAIL]  $ROOT is not an EMHASS checkout (expected src/emhass and pyproject name=emhass)"
  exit 2
fi

PY="${PYTHON:-python}"
command -v "$PY" >/dev/null 2>&1 || PY=python3
if command -v uvx >/dev/null 2>&1; then RUFF="uvx ruff"; elif command -v ruff >/dev/null 2>&1; then RUFF="ruff"; else RUFF=""; fi

# ---- base and changed files
if [ -z "$BASE" ]; then
  if git rev-parse --verify -q origin/master >/dev/null; then BASE=origin/master; else BASE=master; fi
fi
MERGE_BASE="$(git merge-base "$BASE" HEAD 2>/dev/null)" || { bad "cannot resolve diff base '$BASE' (fetch upstream or pass --base)"; MERGE_BASE=HEAD; }
CHANGED="$(git diff --name-only "$MERGE_BASE" HEAD; git diff --name-only HEAD)"
CHANGED="$(printf '%s\n' "$CHANGED" | sed '/^$/d' | sort -u)"
changed() { printf '%s\n' "$CHANGED" | grep -qx "$1"; }
changed_match() { printf '%s\n' "$CHANGED" | grep -qE "$1"; }
if [ -z "$CHANGED" ]; then
  warn "no changes relative to $BASE"
else
  ok "$(printf '%s\n' "$CHANGED" | wc -l | tr -d ' ') file(s) changed vs $BASE"
fi

# ---- branch name
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
case "$BRANCH" in
  fix/*|feat/*|docs/*|chore/*) ok "branch name $BRANCH" ;;
  master|main) warn "on $BRANCH: open PRs from a topic branch (fix/ feat/ docs/ chore/)" ;;
  *) warn "branch name $BRANCH does not use the fix/ feat/ docs/ chore/ prefix" ;;
esac

# ---- commit prefixes
NONCONF="$(git log --format=%s "$MERGE_BASE"..HEAD 2>/dev/null | grep -vE '^(fix|feat|docs|chore)(\(|:| )' || true)"
if [ -n "$NONCONF" ]; then warn "commit subject(s) without fix/feat/docs/chore prefix:"; printf '        %s\n' $'\n'"$NONCONF" | sed '/^ *$/d'; else ok "commit prefixes"; fi

# ---- ruff
if [ -n "$RUFF" ]; then
  # --no-fix: pyproject sets fix = true, and this script must never touch the tree
  if $RUFF check --no-fix . >/tmp/pr_ruff.$$ 2>&1; then ok "ruff check"; else bad "ruff check (see below)"; grep -vE '^(Downloading|Downloaded|Installed) ' /tmp/pr_ruff.$$ | sed 's/^/        /' | head -40; fi
  if $RUFF format --check . >/tmp/pr_ruff.$$ 2>&1; then ok "ruff format --check"; else bad "ruff format --check: run 'ruff format .'"; sed 's/^/        /' /tmp/pr_ruff.$$ | head -20; fi
  rm -f /tmp/pr_ruff.$$
else
  warn "ruff not found (install uv, or 'pip install ruff'); CI will run it"
fi

# ---- param_definitions.json additive-only + companion files
PD=src/emhass/static/data/param_definitions.json
if changed "$PD"; then
  git show "$MERGE_BASE:$PD" >/tmp/pr_pd_old.$$ 2>/dev/null || echo '{}' >/tmp/pr_pd_old.$$
  "$PY" -I "$HERE/check_param_definitions.py" /tmp/pr_pd_old.$$ "$PD"; rc=$?
  [ $rc -eq 1 ] && fail=1
  rm -f /tmp/pr_pd_old.$$
  if "$PY" - "$MERGE_BASE" "$PD" <<'EOF'
import json, subprocess, sys
base, path = sys.argv[1:]
old = json.loads(subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True, encoding="utf-8").stdout or "{}")
new = json.load(open(path, encoding="utf-8"))
flat = lambda d: {k for p in d.values() if isinstance(p, dict) for k in p}
sys.exit(0 if flat(new) - flat(old) else 1)
EOF
  then
    changed src/emhass/data/config_defaults.json || bad "param added but src/emhass/data/config_defaults.json unchanged (four-step workflow, docs/develop.md)"
    changed src/emhass/data/associations.csv || bad "param added but src/emhass/data/associations.csv unchanged (four-step workflow, docs/develop.md)"
    changed_match '^tests/' || warn "param added without a test (cache-key coverage: a value change must change the key)"
  fi
else
  ok "param_definitions.json untouched"
fi

# ---- openapi.json drift
if changed_match '^(src/emhass/static/data/(param_definitions|runtime_params)\.json|docs/api/.*\.schema\.json|scripts/generate_openapi\.py)$'; then
  if [ -f scripts/generate_openapi.py ]; then
    "$PY" - <<'EOF'
import json, sys
sys.path.insert(0, "scripts")
try:
    import generate_openapi as gen
    fresh = gen.generate()
except ImportError as exc:
    print(f"        ({exc})")
    sys.exit(3)
committed = json.load(open("src/emhass/static/openapi.json", encoding="utf-8"))
sys.exit(0 if committed == fresh else 1)
EOF
    case $? in
      0) ok "openapi.json matches the schema sources" ;;
      3) warn "cannot regenerate openapi.json: emhass not importable in this Python (uv sync --extra test, or pip install -e .)" ;;
      *) bad "openapi.json stale: run 'python scripts/generate_openapi.py' and commit" ;;
    esac
  else
    warn "schema changed but scripts/generate_openapi.py missing (older EMHASS?)"
  fi
else
  ok "no schema source changed; openapi.json not affected"
fi

# ---- CHANGELOG
if changed CHANGELOG.md; then bad "CHANGELOG.md edited: the maintainer generates it at release (scripts/generate_changelog.py)"; else ok "CHANGELOG.md untouched"; fi

# ---- privacy lint on the added lines of the diff
ADDED="$( { git diff "$MERGE_BASE" HEAD; git diff HEAD; } | grep '^+' | grep -v '^+++' )"
PRIV='(192\.168\.[0-9]+\.[0-9]+|10\.[0-9]+\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+|100\.[0-9]+\.[0-9]+\.[0-9]+|Bearer [A-Za-z0-9._-]{20,}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(de|com|net|org)|/mnt/user/|homeassistant\.local|\.ts\.net|loxone|node-red|tibber|evcc)'
HITS="$(printf '%s\n' "$ADDED" | grep -iE "$PRIV" | grep -vE '^\+\s*#' | head -10 || true)"
if [ -n "$HITS" ]; then warn "possible private reference(s) in added lines:"; printf '%s\n' "$HITS" | sed 's/^/        /'; else ok "privacy lint (no private IPs, tokens, personal hosts or stack names in added lines)"; fi

# ---- behaviour change without tests
for mod in optimization forecast retrieve_hass; do
  if changed "src/emhass/$mod.py"; then
    n="$(git diff --numstat "$MERGE_BASE" HEAD -- "src/emhass/$mod.py" | awk '{print $1+$2}')"
    if [ "${n:-0}" -gt 3 ] && ! changed_match '^tests/'; then
      warn "src/emhass/$mod.py changed ${n} lines without a test file (AGENTS.md §5: issue first + reproducer test)"
    fi
  fi
done
if changed_match '^src/emhass/.*\.py$' && ! changed_match '^tests/'; then warn "source changed, no tests touched"; fi

# ---- action_logs.txt format contract
if changed src/emhass/utils.py || changed src/emhass/web_server.py; then
  if git diff "$MERGE_BASE" HEAD -- src/emhass/utils.py src/emhass/web_server.py | grep -qE '^[-+].*logging\.Formatter\('; then
    bad "logging.Formatter changed: action_logs.txt line format is parsed by web_server (AGENTS.md rule 1)"
  fi
fi

# ---- tests
case "$TESTS" in
  none) warn "tests skipped (--no-tests)" ;;
  full)
    if "$PY" -m pytest tests -q -x >/tmp/pr_py.$$ 2>&1; then ok "pytest tests/ (full)"; else bad "pytest failed"; tail -20 /tmp/pr_py.$$ | sed 's/^/        /'; fi
    rm -f /tmp/pr_py.$$ ;;
  *)
    SEL=""
    for f in $(printf '%s\n' "$CHANGED" | grep -E '^src/emhass/[a-z_]+\.py$' | sed -E 's#src/emhass/([a-z_]+)\.py#\1#'); do
      [ -f "tests/test_$f.py" ] && SEL="$SEL tests/test_$f.py"
    done
    for f in $(printf '%s\n' "$CHANGED" | grep -E '^tests/test_[a-z_0-9]+\.py$'); do SEL="$SEL $f"; done
    changed_match 'param_definitions|runtime_params|openapi|generate_openapi' && [ -f tests/test_openapi.py ] && SEL="$SEL tests/test_openapi.py"
    SEL="$(printf '%s\n' $SEL | sort -u | tr '\n' ' ')"
    if [ -z "${SEL// /}" ]; then
      warn "no matching tests/test_<module>.py for the changed files; run --full-tests before pushing"
    elif "$PY" -m pytest $SEL -q -x >/tmp/pr_py.$$ 2>&1; then
      ok "pytest $SEL"
    else
      bad "pytest $SEL failed"; tail -20 /tmp/pr_py.$$ | sed 's/^/        /'
    fi
    rm -f /tmp/pr_py.$$ ;;
esac

# ---- account
if command -v gh >/dev/null 2>&1; then
  ACC="$(gh auth status 2>&1 | grep -oE 'account [A-Za-z0-9_-]+' | head -1 | cut -d' ' -f2)"
  FORK="$(git remote get-url origin 2>/dev/null | sed -E 's#.*[:/]([^/]+)/[^/]+(\.git)?$#\1#')"
  if [ -n "$ACC" ] && [ -n "$FORK" ] && [ "$ACC" != "$FORK" ]; then warn "gh account '$ACC' differs from fork owner '$FORK'"; else ok "gh account ${ACC:-unknown} / fork owner ${FORK:-unknown}"; fi
fi

echo
if [ $fail -eq 1 ]; then echo "RESULT: FAIL - fix the [FAIL] lines, then open the PR as a draft (gh pr create --draft)"; exit 1; fi
echo "RESULT: OK - walk the judgement checklist in SKILL.md, then gh pr create --draft"
exit 0
