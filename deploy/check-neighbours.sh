#!/usr/bin/env bash
# Author: Navjyot Nishant
# Created: 2026-10-13
# Last updated: 2026-10-13
# Description: before/after snapshot of the other apps on the VM, so adding NAVAAN provably changes nothing for them.
#
#   deploy/check-neighbours.sh https://relayent.ignorelist.com/ https://<engagehub host>/ > /tmp/before.txt
#   ... apply the nginx change ...
#   deploy/check-neighbours.sh <same urls> > /tmp/after.txt; diff /tmp/before.txt /tmp/after.txt   # must be empty
# With no arguments it reads URLs, one per line, from /opt/navaan/neighbours.txt.
# Prints, per URL: HTTP status and the certificate fingerprint and expiry. Then each container's name, image and state (no uptime, so the diff is stable).
set -uo pipefail
urls=("$@")
if [ ${#urls[@]} -eq 0 ] && [ -r /opt/navaan/neighbours.txt ]; then mapfile -t urls < /opt/navaan/neighbours.txt; fi
[ ${#urls[@]} -gt 0 ] || { echo "usage: $0 URL [URL...]   (or list them in /opt/navaan/neighbours.txt)" >&2; exit 2; }
for u in "${urls[@]}"; do
  host="$(printf '%s' "$u" | sed -E 's#^[a-z]+://##; s#[/:].*$##')"
  code="$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$u" || echo ERR)"
  cert="$(echo | openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null | openssl x509 -noout -fingerprint -sha256 -enddate 2>/dev/null | tr '\n' ' ')"
  echo "url $u http $code cert ${cert:-none}"
done
if command -v docker >/dev/null; then
  docker ps -a --format '{{.Names}} {{.Image}} {{.State}}' | grep -v '^navaan ' | sort | sed 's/^/container /'
fi
