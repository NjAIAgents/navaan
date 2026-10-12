#!/usr/bin/env bash
# usage: upload.sh <slug>   (uses your local OCI CLI profile)
set -euo pipefail
SLUG="${1:?usage: upload.sh <slug>}"
BUCKET="${NAVAAN_BUCKET:-navaan}"
D="$(cd "$(dirname "$0")/.." && pwd)/songs/$SLUG"
[ -d "$D" ] || { echo "no such song: $SLUG"; exit 1; }
NS="$(oci os ns get --query data --raw-output)"
oci os object bulk-upload -ns "$NS" -bn "$BUCKET" --src-dir "$D" --object-prefix "songs/$SLUG/" --overwrite
