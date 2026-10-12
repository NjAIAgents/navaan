#!/bin/bash
# mux_reel.sh <slug>  rebuilds the reel audio from final.mp3 at reel_start.json, over the clip-only reel video
set -e
R=$(cd "$(dirname "$0")/.." && pwd)/songs/$1
S=$(python3 -c "import json;print(json.load(open('$R/reel_start.json'))['start'])")
D=$(python3 -c "import json;print(json.load(open('$R/reel_start.json'))['dur'])")
FF=/opt/homebrew/bin/ffmpeg
$FF -y -v error -i "$R/final_reel.mp4" -ss "$S" -t "$D" -i "$R/final.mp3" -map 0:v -map 1:a -t "$D" -c:v copy \
  -af "afade=t=in:st=0:d=0.4,afade=t=out:st=$(python3 -c "print($D-2.5)"):d=2.5" -c:a aac -b:a 192k -movflags +faststart "$R/final_reel_sync.mp4"
echo wrote final_reel_sync.mp4
