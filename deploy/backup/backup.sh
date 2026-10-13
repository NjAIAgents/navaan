#!/usr/bin/env bash
# Author: Navjyot Nishant
# Created: 2026-10-13
# Last updated: 2026-10-13
# Description: nightly backup of the NAVAAN data folder to the OCI bucket, 14 days kept.
#
# Run on the VM (cron or a systemd timer) as a user that may read /opt/navaan/data and use the bucket through instance principals.
#   NAVAAN_BACKUP_BUCKET   required, bucket name
#   NAVAAN_DATA            default /opt/navaan/data
#   NAVAAN_BACKUP_KEEP     default 14 (days)
#   NAVAAN_BACKUP_DRY=1    build the archive in a temp dir, print its name and size, upload nothing, delete nothing
# analytics.db is copied with SQLite's online backup so the archive is consistent while the portal runs. Secrets are not in the data folder.
# Restore: deploy/README.md.
set -euo pipefail
DATA="${NAVAAN_DATA:-/opt/navaan/data}"; KEEP="${NAVAAN_BACKUP_KEEP:-14}"; PREFIX="navaan-backup/"
[ -d "$DATA" ] || { echo "backup: $DATA not found" >&2; exit 2; }
if [ "${NAVAAN_BACKUP_DRY:-0}" != "1" ]; then
  : "${NAVAAN_BACKUP_BUCKET:?set NAVAAN_BACKUP_BUCKET}"
  command -v oci >/dev/null || { echo "backup: the oci CLI is not installed" >&2; exit 2; }
fi
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
stamp="$(date -u +%Y%m%dT%H%M%SZ)"; stage="$tmp/navaan-data"; mkdir -p "$stage"
tar -C "$DATA" --exclude='state/analytics.db*' -cf - . | tar -C "$stage" -xf -
if [ -f "$DATA/state/analytics.db" ]; then
  mkdir -p "$stage/state"
  python3 - "$DATA/state/analytics.db" "$stage/state/analytics.db" <<'PY'
import sqlite3, sys
s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()
PY
fi
arc="$tmp/navaan-data-$stamp.tar.gz"
tar -C "$tmp" -czf "$arc" navaan-data
echo "backup: $(basename "$arc") $(du -h "$arc" | cut -f1)"
[ "${NAVAAN_BACKUP_DRY:-0}" = "1" ] && { echo "backup: dry run, nothing uploaded"; exit 0; }
oci os object put --auth instance_principal --bucket-name "$NAVAAN_BACKUP_BUCKET" --file "$arc" --name "$PREFIX$(basename "$arc")" --force >/dev/null
echo "backup: uploaded"
# retention: delete archives older than KEEP days (names carry the UTC stamp)
oci os object list --auth instance_principal --bucket-name "$NAVAAN_BACKUP_BUCKET" --prefix "$PREFIX" --all --query 'data[].name' 2>/dev/null \
| python3 -c '
import json, sys, datetime
keep = int(sys.argv[1]); cut = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=keep)
raw = sys.stdin.read().strip()
for n in (json.loads(raw) if raw else []):
    try: t = datetime.datetime.strptime(n.rsplit("-", 1)[1].split(".")[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.timezone.utc)
    except (ValueError, IndexError): continue
    if t < cut: print(n)
' "$KEEP" | while read -r old; do
  oci os object delete --auth instance_principal --bucket-name "$NAVAAN_BACKUP_BUCKET" --object-name "$old" --force >/dev/null && echo "backup: removed $old"
done
