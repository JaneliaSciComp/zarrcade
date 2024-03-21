#!/bin/bash -euo pipefail
source /opt/conda/etc/profile.d/conda.sh
conda activate ngffbrowse
cd /app/ngffbrowse || exit

# Set variables for uvicorn
WORKERS="${WORKERS:=1}"
HOST="${HOST:=0.0.0.0}"
PORT="${PORT:=8000}"

# Export variables for ngffbrowse
export DATA_URL="${DATA_URL:=/data}"

set -x
uvicorn ngffbrowse.serve:app --access-log \
    --workers $WORKERS --host $HOST --port $PORT \
    --forwarded-allow-ips='*' --proxy-headers \
    --ssl-keyfile "$KEY_FILE" --ssl-certfile "$CERT_FILE" "$@"