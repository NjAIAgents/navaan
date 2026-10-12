---
name: video-build
description: Build the full 16:9 video and the vertical reel from Flow clips and the final mp3. Use after clips and audio exist.
---

# Video build

Run on the user's computer, where ffmpeg lives. The scripts find ffmpeg on PATH, with `/opt/homebrew/bin` as a fallback. Run them from the project folder or set `NAVAAN_ROOT`.

1. Optional `songs/<slug>/story.json` fixes the scene order and pan: `{"scenes": [{"clip": "c1_scene.mp4", "at": 0.0, "pan": [0.3, 0.5]}]}`. Without it the clips are used in name order, evenly spaced.
2. Choose the reel window with the caption-aligner (strongest 54 to 60 seconds, usually chorus and rap) and save `reel_start.json` as `{"start": 52.0, "dur": 54.5}`. The default is start 30 and 60 seconds, or the profile's Short length.
3. `python scripts/clipvideo.py <slug> 16x9` writes `final_16x9.mp4`. `python scripts/clipvideo.py <slug> reel` writes `final_reel_sync.mp4` with the audio window cut from `final.mp3`.
4. Captions come from the caption-sync skill, then `python scripts/caption_clips.py <slug> 16x9` and `... reel` write `final_16x9_cap.mp4` and `final_reel_cap.mp4`. Only `_cap` files are uploaded.
5. `python scripts/tag_mp3.py <slug>` writes `final_tagged.mp3` using the profile and `tags.json`.
6. `python scripts/navaan.py run <slug>` does steps 3 to 5 in order with retries and logs in `songs/<slug>/logs/`.
7. Make low resolution previews for chat. Never send full files through a size limited bridge. The web UI plays the full files locally.

Captions need a Devanagari capable font. The script tries Kohinoor on macOS and Noto Sans Devanagari on Linux. Set `captions.font_path` in the profile or `NAVAAN_FONT` otherwise. Set the state to `media_ready` only after the user approves the previews through the media gate.
