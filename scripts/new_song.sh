#!/usr/bin/env bash
set -euo pipefail
SLUG="${1:?usage: new_song.sh <slug>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ -e "$ROOT/songs/$SLUG" ] && { echo "exists: $SLUG"; exit 1; }
cp -R "$ROOT/songs/_template" "$ROOT/songs/$SLUG"
sed -i '' "s/\"slug\": \"\"/\"slug\": \"$SLUG\"/" "$ROOT/songs/$SLUG/meta.json"
echo "created songs/$SLUG"
