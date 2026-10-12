# navaan-studio

One plugin for Claude Code, Cursor and Codex. Shared core: `skills/`, `agents/`, `scripts/`, `AGENTS.md`. Thin adapters: `.claude-plugin/`, `.cursor-plugin/`, `.codex-plugin/`.

## Install

Claude Code: `/plugin marketplace add <path or repo of navaan>` then `/plugin install navaan-studio@navaan`.
Cursor: add the repository as a plugin marketplace (reads `.cursor-plugin/marketplace.json`), then install navaan-studio.
Codex: add the repository as a marketplace (reads `.agents/plugins/marketplace.json`), then install navaan-studio.

## Quick start

1. `pip install pillow numpy` and install ffmpeg. For caption timing also `pip install onnxruntime librosa scipy`. For the APIs `pip install google-api-python-client google-auth-oauthlib`.
2. From the folder where you start your workspace (not inside the plugin or its repository, since songs are exported there by default): `python plugins/navaan-studio/scripts/navaan.py init` creates `navaan.config.json` (artist profile).
3. End to end: `python plugins/navaan-studio/scripts/navaan.py start song-003 a song about monsoon longing`. It runs every step and waits at each gate for your approval. Or step by step: `new`, `status`, `next song-003`, `run song-003`.
4. `python plugins/navaan-studio/scripts/navaan.py serve` opens the local web UI at http://127.0.0.1:8765.
5. In your agent: "start a new NAVAAN song about ..." or `/navaan-studio:new-song`.

## Commands (Claude Code and Cursor)

setup, config, verify, new-song, import-suno, pipeline, status, next, run, lyrics, suno, visuals, captions, video, youtube, instagram, publish, archive, analytics, approve, studio. In Claude Code they are namespaced, for example `/navaan-studio:new-song song-003`. In Codex use the skills by name instead (for example `$navaan-pipeline`).

## Scripts

navaan.py (orchestrator and UI), setup_profile.py, storage.py, upload_cloud.py, new_song.py, clipvideo.py, caption_clips.py, tag_mp3.py, sep.py, asr.py, align.py, publish_youtube.py, publish_instagram.py, oci_public_url.sh. Shared helpers in navaan_common.py. Environment: NAVAAN_ROOT, NAVAAN_FONT, NAVAAN_FFMPEG, NAVAAN_WORK, NAVAAN_VOC_MODEL, NAVAAN_WHISPER_DIR, NAVAAN_CLAUDE_CMD.

## Status

Tested here: profile setup (interactive and from file), orchestrator planning and gates, web UI endpoints and token checks, video and caption rendering on a synthetic song, tagging, caption alignment, vocal separation. Not tested live: YouTube upload, Instagram publish and OCI link creation (they need your credentials), the Cursor and Codex installs, and `claude -p` steps.

## Song already made on Suno

`python scripts/navaan.py import <suno-link> [slug]` brings in a song you already generated: title, lyrics, style, model, audio and cover are read from the Suno page with Claude in Chrome (no credits spent), saved in the song folder, and the pipeline continues from the listen gate. In the web UI paste the link in the Import box. In chat use the import-suno command.


## Redo a step

Use the Redo button on any finished or failed step in the web UI, or run `navaan.py redo <slug> <step> [--run]`. Old files go to `_prev/` in the song folder. Approvals around the step are revoked. Publish, archive and Instagram steps cannot be redone from here.
