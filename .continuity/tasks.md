# Tasks

Append-only, oldest first. Status transitions in place; a finished task stays
here rather than being deleted.

## Task: song-003 flow-visuals step

```
captured_at: 2026-10-12T03:53:57Z
category: task
status: blocked
updated_at: 2026-10-12T04:15:59Z
```

Flow account navjyotnishant@gmail.com has 0 credits (refreshes daily 4:55 pm), checked 2026-10-12T04:16Z. Wrote songs/song-003/needs_you.txt (UI banner); no clips or cover generated, nothing spent. A wakeup is scheduled to recheck; if the 15 min wait ends with no change, add a meta.json history entry and stop. Delete needs_you.txt once credits are available. navaan.config.json is still missing (run artist-setup).

## Task: song-003 captions step

```
captured_at: 2026-10-12T04:36:56Z
category: task
status: blocked
updated_at: 2026-10-12T04:38:30Z
```

Attempt 3 of caption-sync still blocked, same as attempt 2. meta.json has no approval for the one-time download (onnxruntime/librosa/scipy/numpy, UVR Voc FT, sherpa-onnx Whisper small int8), and final_16x9.mp4 / final_reel_sync.mp4 are absent because video-build has not run. History entry added. Needs user: approve the download or point to existing models (NAVAAN_WORK, NAVAAN_VOC_MODEL, NAVAAN_WHISPER_DIR), run video-build, then re-run captions. Shell permissions blocked env and python import checks this turn.
