#!/bin/sh
# emhass-contributions production entrypoint
# Wraps upstream EMHASS to ensure prototypes/ is on PYTHONPATH and importable.
# Actual feature gating happens via prototypes/flags.py reading contrib-flags.yaml,
# not via env vars or this script.

set -e

# Ensure prototypes/ is importable
export PYTHONPATH="/opt/emhass-contrib:${PYTHONPATH:-}"

# Eager-import prototypes module so any registration code runs
# before EMHASS starts serving traffic. Errors here should NOT crash
# the container — log and continue with vanilla EMHASS.
python -c "
import logging, sys, traceback
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(name)s: %(message)s')
try:
    import prototypes
    print('[contrib-entrypoint] prototypes module imported')
except Exception:
    print('[contrib-entrypoint] WARNING: prototypes import failed; running vanilla EMHASS', file=sys.stderr)
    traceback.print_exc()
" || true

# Hand off to upstream's entrypoint or the EMHASS web server
exec python -m emhass.web_server "$@"
