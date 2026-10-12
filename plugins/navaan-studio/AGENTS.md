# NAVAAN Studio

NAVAAN is a music channel. This plugin runs the path from idea to published song: lyrics, Suno song, Flow visuals, measured captions, YouTube and Instagram through their official APIs, then an analytics loop.

## Architecture

- Local web UI (`python scripts/navaan.py serve`): create songs, review text and media, approve gates, start steps. Binds to 127.0.0.1 only.
- Python orchestrator (`scripts/navaan.py`): steps, retries, logs, approvals, local state in `songs/<slug>/meta.json`.
- Claude Code, Codex or Cursor as the agent: songwriting, browser steps on Suno and Flow, review, release planning. The orchestrator calls `claude -p` for those steps with an allowlist of tools, since headless runs cannot answer permission prompts (override with NAVAAN_CLAUDE_CMD or NAVAAN_CLAUDE_FLAGS).
- Tools: Suno (browser), ffmpeg (video), YouTube Data API, Instagram Graph API.

## End to end

`python scripts/navaan.py start <slug> <idea>` runs the whole pipeline: lyrics, Suno, visuals, captions, video, YouTube, archive. It pauses at each human gate and continues when you approve. In the web UI the Run end to end button does the same. Song already made on Suno? `python scripts/navaan.py import <suno-link> [slug]` pulls title, lyrics, style, audio and cover from Suno (no credits spent) and continues from the listen gate. In chat, the pipeline and new-song commands loop on `navaan.py next` and stop at every gate.

## First run

If `navaan.config.json` is missing, run the artist-setup skill (or `python scripts/navaan.py init`). It asks every profile question and writes the config. Then use the navaan-pipeline skill for any song task.

## Commands

setup, config, verify, new-song, pipeline, status, next, run, lyrics, suno, visuals, captions, video, youtube, instagram, publish, archive, analytics, approve, studio. Each one runs the matching skill or script. `approve` only explains how: agents never approve gates. In this plugin `scripts/` means the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code); run scripts from the workspace folder.

## Roles

lyricist, suno-operator, visual-director, caption-aligner, publisher, analyst. Instructions live in `agents/`, shared knowledge in `skills/`. Tools that support subagents should delegate. Tools that do not should follow the same skills in order.

## Safety rules

- Gates (lyrics, listen, credits, media, publish_youtube, publish_short, instagram_caption, publish_instagram, cloud_upload) are approved only by the user, through the web UI or `navaan.py approve`. Agents never write approvals.
- Publishing, deleting public content, spending Suno or Flow credits, and sending messages each also need an explicit yes in chat.
- Publish scripts dry run by default and need `--yes` plus the recorded gate.
- Never store passwords, cookies, tokens or API keys in the project. Credentials live in the user's environment or `~/.config/navaan/`.

Storage: the profile asks for a local folder and a cloud location and verifies both. Songs are created and exported in the local folder (`storage.local_dir`), which must be outside the plugin folder and outside the repository that ships it. The folder where you started your workspace is a good choice. A finished song is archived to the cloud bucket (OCI, S3 or GCS) only after the cloud_upload gate is approved: `python scripts/upload_cloud.py <slug>`.

Layout: `<workspace>/navaan.config.json`, `<workspace>/style-notes.md` (generated), `<local_dir>/songs/<slug>/`. The plugin scripts are called by path from the plugin folder.

## Browser tab rule

Reuse the tab the user already has open for a site (Suno, Flow). Never open a second tab for the same site to continue work, and never navigate back to the site's home address, because the account chosen in that tab is part of its address and a fresh tab can fall back to the default account. Read the tab list first, keep the current address, reload in place.


## Redo a finished step

Any finished or failed step except the publish, archive and Instagram steps can be run again. Use the Redo button on the step in the web UI, or `navaan.py redo <slug> <step> [--run]`. The step's current output files are moved to `<song>/_prev/<timestamp>/` and nothing is deleted. Only that step runs. Later steps keep their files and approvals, and the new output replaces the old one. If the rerun fails, the old files are put back. A step that spends credits (visuals) revokes its credits approval and waits for a fresh one. Steps that touch an outside service (YouTube, cloud archive, Instagram) are refused on purpose.


## Captions are off by default

Lyric captions over the video are switched off. The pipeline skips the Measure lyric timing step and the caption burn, and the video step only renders `final_16x9.mp4`, `final_reel_sync.mp4` and the tagged mp3. YouTube uploads `final_reel_sync.mp4`. To turn captions back on, set `captions.enabled` to true in the profile (the tools need a one time download and the render is slow).


## No captions, no separate Short by default

YouTube makes its own captions from the audio and can cut a Short from the full video in its editor, so the pipeline does neither. The video step renders only the full 16:9 video and the tagged mp3, and the YouTube step uploads that full video. To also render a vertical reel (needed for Instagram), set `video.make_reel` to true in the profile. To burn lyrics into the video, set `captions.enabled` to true.
