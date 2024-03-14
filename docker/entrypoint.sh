#!/bin/bash
source /opt/conda/etc/profile.d/conda.sh
conda activate ngffbrowse
cd /app/ngffbrowse || exit
uvicorn ngffbrowse:serve --access-log --workers 1 --forwarded-allow-ips='*' --proxy-headers --host 0.0.0.0 "$@"

