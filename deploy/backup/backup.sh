#!/usr/bin/env bash
# Author: Navjyot Nishant
# Created: 2026-10-13
# Last updated: 2026-10-14
# Description: nightly backup of the NAVAAN data folder: local copy always, OCI bucket when it is reachable. 14 days kept.
#
# Run as root (the data folder belongs to the container user). Cron: /etc/cron.d/navaan-backup.
#   NAVAAN_DATA              default /opt/navaan/data
#   NAVAAN_BACKUP_LOCAL      default /opt/navaan/backups   (local copies, NAVAAN_BACKUP_KEEP_LOCAL of them, default 7)
#   NAVAAN_BACKUP_BUCKET     OCI bucket name; unset = local only
#   NAVAAN_BACKUP_KEEP       days kept in the bucket, default 14
#   NAVAAN_BACKUP_DRY=1      build the archive in a temp dir, print name and size, keep and upload nothing
# The OCI CLI is used when installed, else the official container ghcr.io/oracle/oci-cli with --auth instance_principal
# (needs a policy that lets this instance write objects in the bucket). Exit 3 = local copy made, upload failed.
# analytics.db is copied with SQLite's online backup so the archive is consistent while the portal runs. Secrets are not in the data folder.
# Restore: deploy/README.md.
set -euo pipefail
DATA="${NAVAAN_DATA:-/opt/navaan/data}"; LOCAL="${NAVAAN_BACKUP_LOCAL:-/opt/navaan/backups}"; KEEP="${NAVAAN_BACKUP_KEEP:-14}"; KEEP_LOCAL="${NAVAAN_BACKUP_KEEP_LOCAL:-7}"
BUCKET="${NAVAAN_BACKUP_BUCKET:-}"; PREFIX="navaan-backup/"; DRY="${NAVAAN_BACKUP_DRY:-0}"
[ -d "$DATA" ] || { echo "backup: $DATA not found" >&2; exit 2; }
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
name="navaan-data-$stamp.tar.gz"; arc="$tmp/$name"
tar -C "$tmp" -czf "$arc" navaan-data
echo "backup: $name $(du -h "$arc" | cut -f1)"
[ "$DRY" = "1" ] && { echo "backup: dry run, nothing kept or uploaded"; exit 0; }

# 1. local copy, newest KEEP_LOCAL kept
install -d -m 700 "$LOCAL"; install -m 600 "$arc" "$LOCAL/$name"
ls -1t "$LOCAL"/navaan-data-*.tar.gz | tail -n +"$((KEEP_LOCAL + 1))" | xargs -r rm -f
echo "backup: local copy in $LOCAL"

# 2. bucket
[ -n "$BUCKET" ] || { echo "backup: NAVAAN_BACKUP_BUCKET not set, local only"; exit 0; }
if command -v oci >/dev/null; then
  oci_() { oci "$@"; }; farc="$arc"
else
  oci_() { docker run --rm -v "$tmp:/work:ro" ghcr.io/oracle/oci-cli:latest "$@"; }; farc="/work/$name"
fi
if ! oci_ os object put --auth instance_principal --bucket-name "$BUCKET" --file "$farc" --name "$PREFIX$name" --force >/dev/null 2>"$tmp/oci.err"; then
  echo "backup: UPLOAD FAILED (is there a policy for this instance on bucket $BUCKET?): $(grep -m1 -E '"(code|message)"' "$tmp/oci.err" | tr -s ' ')" >&2; exit 3
fi
echo "backup: uploaded to $BUCKET/$PREFIX$name"
# retention: delete archives older than KEEP days (names carry the UTC stamp)
oci_ os object list --auth instance_principal --bucket-name "$BUCKET" --prefix "$PREFIX" --all --query 'data[].name' 2>/dev/null \
| python3 -c '
import json, sys, datetime
keep = int(sys.argv[1]); cut = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=keep)
raw = sys.stdin.read().strip()
for n in (json.loads(raw) if raw else []):
    try: t = datetime.datetime.strptime(n.rsplit("-", 1)[1].split(".")[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=datetime.timezone.utc)
    except (ValueError, IndexError): continue
    if t < cut: print(n)
' "$KEEP" | while read -r old; do
  oci_ os object delete --auth instance_principal --bucket-name "$BUCKET" --object-name "$old" --force >/dev/null && echo "backup: removed $old"
done
