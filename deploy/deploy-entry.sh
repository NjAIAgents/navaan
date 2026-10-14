#!/usr/bin/env bash
# Author: Navjyot Nishant
# Created: 2026-10-14
# Last updated: 2026-10-14
# Description: the only thing the pipeline's SSH key may run (forced command in authorized_keys). Installed by an admin at /opt/navaan/bin/deploy-entry.
#   ssh navaan-deploy@host ping                 -> channel check, prints the deployed commit
#   ssh navaan-deploy@host "deploy <sha>"       -> reads the source tar on stdin and releases it through deploy-run (sudo)
set -euo pipefail
cmd="${SSH_ORIGINAL_COMMAND:-}"
case "$cmd" in
  ping) echo "navaan deploy channel ok; deployed commit: $(cat /opt/navaan/DEPLOYED 2>/dev/null || echo none)"; exit 0 ;;
  deploy\ *) sha="${cmd#deploy }"; [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { echo "bad commit sha" >&2; exit 2; }
             exec sudo /opt/navaan/bin/deploy-run "$sha" ;;
  *) echo "unknown command" >&2; exit 2 ;;
esac
