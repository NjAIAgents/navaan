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

setup, config, verify, new-song, import-suno, pipeline, status, next, run, lyrics, suno, visuals, captions, video, youtube, instagram, publish, archive, analytics, collect, recommend, approve, studio. In Claude Code they are namespaced, for example `/navaan-studio:new-song song-003`. In Codex use the skills by name instead (for example `$navaan-pipeline`).

## Scripts

navaan.py (orchestrator and UI), setup_profile.py, storage.py, upload_cloud.py, new_song.py, clipvideo.py, caption_clips.py, tag_mp3.py, sep.py, asr.py, align.py, publish_youtube.py, publish_instagram.py, oci_public_url.sh. Shared helpers in navaan_common.py. Environment: NAVAAN_ROOT, NAVAAN_FONT, NAVAAN_FFMPEG, NAVAAN_WORK, NAVAAN_VOC_MODEL, NAVAAN_WHISPER_DIR, NAVAAN_CLAUDE_CMD.

## Status

Tested here: profile setup (interactive and from file), orchestrator planning and gates, web UI endpoints and token checks, video and caption rendering on a synthetic song, tagging, caption alignment, vocal separation. Not tested live: YouTube upload, Instagram publish and OCI link creation (they need your credentials), the Cursor and Codex installs, and `claude -p` steps.

## Song already made on Suno

`python scripts/navaan.py import <suno-link> [slug]` brings in a song you already generated: title, lyrics, style, model, audio and cover are read from the Suno page with Claude in Chrome (no credits spent), saved in the song folder, and the pipeline continues from the listen gate. In the web UI paste the link in the Import box. In chat use the import-suno command.


## Redo a step

Use the Redo button on any finished or failed step in the web UI, or run `navaan.py redo <slug> <step> [--run]`. Only that step runs; later steps are untouched. Old files go to `_prev/` in the song folder and come back if the rerun fails. A credit spending step asks for its credits approval again. Publish, archive and Instagram steps cannot be redone from here.


## Captions are off by default

Lyric captions over the video are switched off. The pipeline skips the Measure lyric timing step and the caption burn, and the video step only renders `final_16x9.mp4`, `final_reel_sync.mp4` and the tagged mp3. YouTube uploads `final_reel_sync.mp4`. To turn captions back on, set `captions.enabled` to true in the profile (the tools need a one time download and the render is slow).


## Lyrics on the Instagram reel

Songs made from your own pictures get the lyrics burned onto the vertical reel, because Instagram's own Lyrics button and API cannot do it for audio that is not in its music library. The Measure lyric timing step (Whisper on the server, one time tool download behind the `captions_setup` gate) writes `caption_cues.json`, then the video step writes `final_reel_9x16_cap.mp4` next to the clean `final_reel_9x16.mp4`. Instagram posts the captioned file when it exists. The YouTube Short and the full video stay clean, viewers use CC there. Set `captions.reel` to false in the profile to skip the step.

## Narration you already made

The New inspiration short dialog has two optional pickers: the narration audio and its subtitle file (.srt). When both are chosen the portal saves them as `voiceover.<ext>` and `voiceover.srt` in the item's folder and sets the brief to `voiceover: file` and `music: none`, so the video follows the voice line by line. The dialog opened from the Library creates songs, the one opened from the Inspiration page creates inspiration shorts; they no longer share one window.

## No captions, no separate Short by default

YouTube makes captions and Shorts itself, so the pipeline renders only the full 16:9 video and uploads that. Set `video.make_reel` to true for a vertical reel (Instagram needs it) and `captions.enabled` to true to burn lyrics in.

## Analytics and growth advice

Portal: Analytics page (collector data) with a Recommendations panel. The page has an Instagram and a YouTube tab (switch at the top). YouTube shows subscribers, views, watch hours, subscribers gained, a videos table split into videos and Shorts with average viewed percent and subscribers per 1,000 views, retention curves, traffic sources, audience and comments waiting, plus the same recommendations panel. Each song or short has a Performance tab with its own Instagram and YouTube numbers (views, reach or watch time, comparison with your other posts of the same kind, comments waiting, findings), and the Library shows views per item on both. Posts and videos link to songs automatically through `published.instagram`, `published.youtube_items` and `published.youtube_short`; link one by hand from the tab if you posted outside NAVAAN. YouTube setup: Collect now works with your publishing sign-in; for watch time, retention, traffic and audience run `python3 plugins/navaan-studio/scripts/yt_collect.py auth` once (read only). YouTube does not expose impressions or click through rate to any API, so those stay in Studio. Chat or schedule: `/navaan-studio:collect instagram|youtube|all` pulls numbers into the local database, `/navaan-studio:recommend youtube music --collect` (or `instagram`) collects, analyses, researches the market and stores sourced, organic growth recommendations. Both are read only towards Instagram and YouTube and safe to run unattended. Scheduling: make a Claude scheduled task on the computer that holds your workspace with one of those prompts, for example weekly.

Best time to publish on YouTube: the YouTube tab has a card per channel with the best hours and weekdays for full videos and for Shorts, and five slots for the next week. YouTube has no public number for when your viewers are online, so `besttime.py` blends three signals and drops any that is missing: how your own videos did by publish hour and weekday (views per day, share watched and subscribers per 1,000 views against your median, needs 8 videos older than a week per kind), the countries your viewers come from with listening assumed to peak in local evenings (an assumption, the card says so), and when your Instagram followers are online. Subscriber and notification traffic tells how much timing matters at all. Videos are posted an hour before the peak, Shorts at the peak. Click a slot to schedule a song: Schedule publishing now has a YouTube time next to the Reel time (leave it on Auto for 15 minutes before the Reel), and the video and its Short go public together at that time. API: `GET /api/besttime?type=music&platform=youtube`, CLI: `python3 -c "import besttime,json;print(json.dumps(besttime.for_label_youtube('music'),indent=1))"` from `scripts/`.

Schedule suggestion in the pipeline: a song that is not on Instagram yet shows the suggested publishing times on its Pipeline tab, computed from the same timing analysis (best YouTube slot for the full video, then the best Instagram slot 5 minutes to 12 hours after it, else an hour after). "Use these times" saves the schedule, "Other time" opens the picker. The suggestion is computed when you look at it and never stored, and it approves nothing: `go_public`, `instagram_caption` and `publish_instagram` stay yours. CLI: `navaan.py schedule <slug> --suggest` prints it, `--accept` saves it. `navaan.py run` prints a one line tip before `publish_youtube` and `go_public` when no schedule is set. API: `GET /api/schedule/suggest?slug=`, `POST /api/schedule/accept`.

Automatic refresh: the Analytics page has an Automatic refresh card (both tabs). Switch it on, pick every day, 2 days, 3 days, week or 2 weeks and an hour in your time, and the portal collects Instagram and YouTube, re-runs the analysis and, if you tick it, asks Claude for market research, so the best times and recommendations keep learning without a Claude scheduled task. It runs while the portal is open and a missed run starts when you next open it. Settings are in `analytics_auto.json` next to the songs folder, API `GET|POST /api/analytics/auto`, `POST /api/analytics/auto/run`.

CLI: `python3 scripts/ig_collect.py collect|status|link|peers|mention`, `python3 scripts/yt_collect.py collect|status|link|auth`, `python3 scripts/ig_reco.py [--platform youtube] analyze|pack|note|add|list|status|outcomes`.
