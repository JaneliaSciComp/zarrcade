#!/bin/bash
source /opt/conda/bin/activate zarrcade
cd /app/zarrcade || exit

# Set variables for uvicorn
WORKERS="${WORKERS:=1}"
HOST="${HOST:=0.0.0.0}"
PORT="${PORT:=8000}"

# Export variables for zarrcade
export DATA_URL="${DATA_URL:=/data}"

set -x
uvicorn zarrcade.serve:app --access-log \
    --workers $WORKERS --host $HOST --port $PORT \
    --forwarded-allow-ips='*' --proxy-headers \
    --ssl-keyfile "$KEY_FILE" --ssl-certfile "$CERT_FILE" "$@"