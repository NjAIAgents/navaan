#!/usr/bin/env bash
# Author: Navjyot Nishant
# Created: 2026-10-14
# Last updated: 2026-10-14
# Description: production release of NAVAAN on the VM: receive the source as a tar on stdin, build, roll out, smoke test, roll back on failure.
#
# Installed by an admin at /opt/navaan/bin/deploy-run (root:root, 755) and run through sudo by deploy-entry.sh. It is NOT replaced by the pipeline itself:
# the pipeline can only change what this script builds, never the script. Reinstall it by hand after editing it (deploy/README.md, Release pipeline).
#   usage: git archive HEAD .claude-plugin plugins deploy .dockerignore | sudo /opt/navaan/bin/deploy-run <40 hex commit sha>
set -euo pipefail
SHA="${1:-}"; [[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "deploy: need the 40 character commit sha" >&2; exit 2; }
REPO=/opt/navaan/repo; INBOX=/opt/navaan/incoming; LOG=/var/log/navaan-deploy.log; URL="${NAVAAN_URL:-https://navaan.njlabs.dev}"
exec 9>/var/lock/navaan-deploy.lock; flock -n 9 || { echo "deploy: another deploy is running" >&2; exit 3; }
exec > >(tee -a "$LOG") 2>&1
echo "== $(date -u +%FT%TZ) deploy $SHA"

# 1. receive and check the source (stdin is a tar; no absolute paths, no ..)
rm -rf "$INBOX"; mkdir -p "$INBOX/x"; cat > "$INBOX/src.tar"
if tar -tf "$INBOX/src.tar" | grep -qE '(^/|(^|/)\.\.(/|$))'; then echo "deploy: unsafe path in the archive" >&2; exit 2; fi
tar -xf "$INBOX/src.tar" -C "$INBOX/x" --no-same-owner --no-same-permissions
for d in .claude-plugin plugins deploy; do [ -d "$INBOX/x/$d" ] || { echo "deploy: archive lacks $d" >&2; exit 2; }; done
for d in .claude-plugin plugins deploy; do rsync -a --delete "$INBOX/x/$d/" "$REPO/$d/"; done
[ -f "$INBOX/x/.dockerignore" ] && cp "$INBOX/x/.dockerignore" "$REPO/.dockerignore"
rm -rf "$INBOX"
cd "$REPO"

# 2. build: a failed build stops here and the running container is untouched
if docker image inspect navaan:local >/dev/null 2>&1; then docker tag navaan:local navaan:previous; fi
nice -n 10 docker build -f deploy/Dockerfile -t navaan:local .

# 3. roll out and wait for healthy, then smoke test through nginx
healthy() { for _ in $(seq 40); do [ "$(docker inspect navaan --format '{{.State.Health.Status}}' 2>/dev/null)" = healthy ] && return 0; sleep 3; done; return 1; }
smoke() { for _ in $(seq 10); do curl -fsS -m 8 "$URL/auth/state" | grep -q '"state"' && return 0; sleep 3; done; return 1; }
docker compose -f deploy/compose.yml up -d
if healthy && smoke; then
  echo "$SHA" > /opt/navaan/DEPLOYED; docker image prune -f >/dev/null
  echo "deploy: ok $SHA"; exit 0
fi

# 4. roll back to the previous image
echo "deploy: FAILED health or smoke test, rolling back" >&2
if docker image inspect navaan:previous >/dev/null 2>&1; then
  docker tag navaan:previous navaan:local; docker compose -f deploy/compose.yml up -d
  if healthy && smoke; then echo "deploy: rolled back to the previous image, site is up" >&2; else echo "deploy: ROLLBACK ALSO FAILED, look at the VM" >&2; fi
else echo "deploy: no previous image to roll back to" >&2; fi
exit 1
