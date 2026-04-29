#!/bin/bash
# emhass-contributions production entrypoint.
#
# Wraps upstream EMHASS to ensure prototypes/ is on PYTHONPATH and importable
# before gunicorn forks workers. Mirrors upstream's data-init behavior (see
# upstream/Dockerfile ENTRYPOINT) so a vanilla launch is preserved when no
# prototype flags are enabled.
set -e

# Make prototypes/ importable to the EMHASS Python interpreter (uv-managed venv).
export PYTHONPATH="/opt/emhass-contrib:${PYTHONPATH:-}"

# Eager-import prototypes module so registration code (if any) runs before
# gunicorn forks workers. Errors here MUST NOT crash the container — log and
# continue with vanilla EMHASS behavior.
uv run --frozen python -c "
import sys, traceback
try:
    import prototypes  # noqa: F401
    print('[contrib-entrypoint] prototypes module imported')
except Exception:
    print('[contrib-entrypoint] WARNING: prototypes import failed; running vanilla EMHASS', file=sys.stderr)
    traceback.print_exc()
" || true

# --- Below mirrors upstream's tini ENTRYPOINT (kept in sync with upstream/Dockerfile) ---
if [ ! -f /data/long_train_data.pkl ]; then
    echo "Initializing data: Copying default PKL file..."
    cp /app/data/long_train_data.pkl /data/
fi
if [ ! -f /data/opt_res_latest.csv ]; then
    echo "Initializing data: Copying default CSV file..."
    cp /app/data/opt_res_latest.csv /data/
fi

WORKER_CLASS=${WORKER_CLASS:-uvicorn.workers.UvicornWorker}
PORT=${PORT:-5000}
IP=${IP:-0.0.0.0}

exec uv run --frozen gunicorn emhass.web_server:app -c gunicorn.conf.py -k "$WORKER_CLASS"
