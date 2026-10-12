#!/usr/bin/env bash
# usage: tag_mp3.sh <slug>  -> songs/<slug>/final_tagged.mp3 (ID3v2.3 + embedded cover_1x1.png)
set -euo pipefail
SLUG="${1:?usage: tag_mp3.sh <slug>}"
D="$(cd "$(dirname "$0")/.." && pwd)/songs/$SLUG"
ARGS=$(python3 - "$D/tags.json" <<'PY'
import json,sys,shlex
t=json.load(open(sys.argv[1]))
m={"title":"title","artist":"artist","album":"album","album_artist":"album_artist","track":"track","genre":"genre","year":"date","composer":"composer","copyright":"copyright","comment":"comment","language":"language"}
print(" ".join("-metadata "+shlex.quote(f"{v}={t[k]}") for k,v in m.items() if t.get(k)))
PY
)
eval ffmpeg -y -loglevel error -i "\"$D/final.mp3\"" -i "\"$D/cover_1x1.png\"" -map 0:a -map 1:v -c copy -id3v2_version 3 \
  -metadata:s:v title=Cover -metadata:s:v comment=\"Cover\(front\)\" $ARGS "\"$D/final_tagged.mp3\""
