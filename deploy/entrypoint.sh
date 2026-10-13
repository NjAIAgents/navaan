#!/bin/sh
# Author: Navjyot Nishant
# Created: 2026-10-13
# Last updated: 2026-10-13
# Description: container start: pull secrets from Vault, keep them in step, then run the NAVAAN portal.
set -eu
CFG="$HOME/.config/navaan"
if [ -n "${NAVAAN_VAULT_ADDR:-}" ] && [ -r "${NAVAAN_VAULT_ROLE_ID_FILE:-/nonexistent}" ]; then
  [ -f /gate/htpasswd ] && export NAVAAN_GATE_FILE=/gate/htpasswd   # the shared password hash, written in place for nginx
  ( while true; do python3 /home/navaan/vault_sync.py watch; echo "secrets: watcher stopped, restarting"; sleep 15; done ) &
  i=0
  while [ "$i" -lt "${NAVAAN_VAULT_WAIT:-60}" ]; do
    grep -q '"status": "ok"' "$CFG/secrets.status" 2>/dev/null && break
    sleep 1; i=$((i + 1))
  done
  grep -q '"status": "ok"' "$CFG/secrets.status" 2>/dev/null || echo "secrets: not ready after ${NAVAAN_VAULT_WAIT:-60}s, starting the portal anyway (it shows 'secrets waiting')"
else
  echo "secrets: Vault not configured, running without it"
fi
# The Claude credential (claude.env) is read by the portal each time it starts a Claude step, so a late or renewed token needs no restart.
exec python3 /home/navaan/plugin/scripts/navaan.py serve
