---
name: caption-sync
description: Measure when each lyric line is sung and burn synced captions into the video. Use whenever captions are missing, estimated, or out of sync.
---

# Caption sync

Estimated timing is always wrong. Measure it.

Pipeline: separate vocals, transcribe windows, align lyric lines, render.

The orchestrator now runs the measuring step as a script, with no agent: `python scripts/captions_run.py <slug>` writes `caption_cues.json` and `reel_start.json`. The one time install is `python scripts/setup_captions.py --yes`, and it runs only after the human approves the `captions_setup` gate (about 700 MB from GitHub releases and PyPI, kept in `~/.cache/navaan`, outside the plugin and the repo). `setup_captions.py --check` says what is missing. Do not download anything yourself. Rendering the captions onto the videos belongs to the video step. The manual steps below are for tuning a song by hand, for example to pin a line.


1. Setup once (needs network to GitHub releases and PyPI): `pip install onnxruntime librosa scipy numpy`. Get the UVR MDX Voc FT onnx model from the TRvlvr model repo release and the sherpa-onnx Whisper small int8 package from the k2-fsa release. Hugging Face may be blocked, so do not depend on it. Ask the user before downloading.
2. Make a mono copy of `final.mp3` and run `python scripts/sep.py <tag> <audio>`. It writes `<tag>_voc.npy`.
3. Hindi ASR: `python scripts/asr.py <tag> small hi <WORK>/<tag>_hi.json`. Use the small model, because medium is about six times slower with little gain. Use the custom decoder in this script. The stock sherpa decoder drops partial UTF-8 byte tokens for Hindi.
4. For English or rap sections run the same script with `en` and save `<tag>_asren.json`. English windows are the most reliable anchors.
5. Align: `python scripts/align.py <tag> songs/<slug>/<sung lyrics file> songs/<slug>/caption_cues.json '<pins>'`. Pins force a line start or end into a time window, for example `{"28":[139.5,141.5],"35:e":[165.0,167.8]}`. Add pins from the English ASR for the rap start and end. Check the printed table: lines of about 6 s in choruses, 3 to 4 s in verses, low emission cost.
6. Render: `python scripts/caption_clips.py <slug> 16x9` and `... reel` (needs `final_16x9.mp4` and `final_reel_sync.mp4` from the video-build skill first). Cues become Pillow overlays with 0.4 s fades, starting 0.1 s early and ending 0.35 s late, clipped before the next cue.
7. Spot check three timestamps per song by extracting short audio and frames, then show the user previews. Accuracy is good, not perfect, on sung Hindi and Maithili.

Environment variables: `NAVAAN_WORK`, `NAVAAN_VOC_MODEL`, `NAVAAN_WHISPER_DIR`. Use `nohup` and a script file for long jobs, and never `pkill -f` a pattern that matches your own shell command.
