#!/usr/bin/env bash
cd "$(dirname "$0")/.." && export PATH=/opt/homebrew/bin:$PATH
for s in song-001 song-002; do
  .venv/bin/python scripts/animate.py $s reel
  .venv/bin/python scripts/animate.py $s 16x9 captions
done
echo ALLDONE
