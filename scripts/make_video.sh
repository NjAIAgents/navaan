#!/usr/bin/env bash
# usage: make_video.sh <slug> [reel_start_seconds] [reel_length_seconds]
set -euo pipefail
SLUG="${1:?usage: make_video.sh <slug> [start] [length]}"
START="${2:-0}"; LEN="${3:-60}"
D="$(cd "$(dirname "$0")/.." && pwd)/songs/$SLUG"
ffmpeg -y -loop 1 -framerate 2 -i "$D/cover_16x9.png" -i "$D/final.mp3" \
  -vf "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2" \
  -c:v libx264 -tune stillimage -pix_fmt yuv420p -c:a aac -b:a 192k -shortest -movflags +faststart "$D/video.mp4"
ffmpeg -y -loop 1 -framerate 2 -i "$D/cover_1x1.png" -ss "$START" -t "$LEN" -i "$D/final.mp3" \
  -vf "scale=1080:1080,pad=1080:1920:0:420:black" \
  -c:v libx264 -tune stillimage -pix_fmt yuv420p -c:a aac -b:a 192k -t "$LEN" -movflags +faststart "$D/reel.mp4"
