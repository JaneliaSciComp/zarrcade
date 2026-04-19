#!/bin/sh
# Resolve the runtime config for the Zarrcade SPA.
#
# - If CONFIG_URL is set, substitute it into index.html so the SPA fetches
#   the config in the browser. (Entirely client-side; nginx just serves the
#   static page.)
# - If a file is bind-mounted at /etc/zarrcade/config.json, copy it over the
#   baked-in config.json. When no CONFIG_FILE is set, /dev/null is mounted
#   there as a placeholder and this step is skipped.
set -e

INDEX=/usr/share/nginx/html/index.html
TARGET=/usr/share/nginx/html/config.json
STAGED=/etc/zarrcade/config.json

if [ -n "${CONFIG_URL:-}" ] && [ -f "${INDEX}" ]; then
    echo "[zarrcade] Injecting CONFIG_URL=${CONFIG_URL} into index.html"
    tmp=$(mktemp)
    CONFIG_URL="${CONFIG_URL}" envsubst '${CONFIG_URL}' < "${INDEX}" > "${tmp}"
    mv "${tmp}" "${INDEX}"
    chmod 644 "${INDEX}"
fi

if [ -f "${STAGED}" ]; then
    echo "[zarrcade] Using mounted config from ${STAGED}"
    cp "${STAGED}" "${TARGET}"
    chmod 644 "${TARGET}"
fi
