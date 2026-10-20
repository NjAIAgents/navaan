# NAVAAN Studio

NAVAAN is a music channel. This plugin runs the path from idea to published song: lyrics, Suno song, Flow visuals, measured captions, YouTube and Instagram through their official APIs, then an analytics loop.

## Architecture

- Local web UI (`python scripts/navaan.py serve`): create songs, review text and media, approve gates, start steps. Binds to 127.0.0.1 only.
- Python orchestrator (`scripts/navaan.py`): steps, retries, logs, approvals, local state in `songs/<slug>/meta.json`.
- Claude Code, Codex or Cursor as the agent: songwriting, browser steps on Suno and Flow, review, release planning. The orchestrator calls `claude -p` for those steps with an allowlist of tools, since headless runs cannot answer permission prompts (override with NAVAAN_CLAUDE_CMD or NAVAAN_CLAUDE_FLAGS).
- Tools: Suno (browser), ffmpeg (video), YouTube Data API, Instagram Graph API.

## End to end

`python scripts/navaan.py start <slug> <idea>` runs the whole pipeline: lyrics, Suno, visuals, captions, video, archive (this publishes the song to NAVAAN, before YouTube and Instagram), YouTube. It pauses at each human gate and continues when you approve. In the web UI the Run end to end button does the same. Song already made on Suno? `python scripts/navaan.py import <suno-link> [slug]` pulls title, lyrics, style, audio and cover from Suno (no credits spent) and continues from the listen gate. In chat, the pipeline and new-song commands loop on `navaan.py next` and stop at every gate.

## First run

If `navaan.config.json` is missing, run the artist-setup skill (or `python scripts/navaan.py init`). It asks every profile question and writes the config. Then use the navaan-pipeline skill for any song task.

## Commands

setup, config, verify, new-song, pipeline, status, next, run, lyrics, suno, visuals, captions, video, youtube, instagram, publish, archive, analytics, collect, recommend, approve, studio. Each one runs the matching skill or script. `approve` only explains how: agents never approve gates. In this plugin `scripts/` means the plugin's scripts folder (`${CLAUDE_PLUGIN_ROOT}/scripts` in Claude Code); run scripts from the workspace folder.

## Roles

lyricist, suno-operator, visual-director, caption-aligner, publisher, analyst, data-collector, growth-advisor. Instructions live in `agents/`, shared knowledge in `skills/`. Tools that support subagents should delegate. Tools that do not should follow the same skills in order.

## Safety rules

- Gates (lyrics, listen, credits, media, publish_youtube, publish_short, instagram_caption, publish_instagram, cloud_upload, local_cleanup, go_public) are approved only by the user, through the web UI or `navaan.py approve`. Agents never write approvals.
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

Asking the user from a headless step: write `songs/<slug>/question.json` (`{"text": "...", "options": [{"id": "...", "label": "..."}], "allow_text": false}`) and stop. The web portal shows a question card, the user answers there (or with `navaan.py answer <slug> --choice ID`), and the step runs again with the answer in its prompt. Answers are human only, stored in `meta.json`. Never answer for the user.

## Content types

Every item has a `type` in meta.json: `music` (also every older item), `inspiration`, `aha`, `reel`, `explainer` (planned). The type picks the production steps, skills and checks. Gates, approvals, publishing, archive and the portal are shared. Folders are named `song-001`, `insp-001`, `aha-001`, `reel-001`, `expl-001`. Create one with `navaan.py new --type inspiration --idea "..."` or the New button in the portal.

### Inspiration pipeline

quote (gate `quote`) -> originality check on the web (gate `originality`) -> background image -> typography, timing and music -> render -> review (gate `media`) -> upload to YouTube as a Short, private (gate `publish_youtube`) -> Instagram caption (gate) -> go public (gate) -> Instagram Reel (gate) -> archive -> cleanup.

- Output is 1080x1920, 30 fps, 10 to 30 seconds, h264 plus aac. `render_report.json` records the checks.
- The renderer is Remotion (`npm install` once in `plugins/navaan-studio/remotion`) with an ffmpeg and Pillow fallback. The camera move, typography and transitions run from `timing.json`, so output is predictable and uses no generation credits. Only `background: generate` in brief.md uses Flow credits, behind the `credits` gate. Use Flow video clips only when a quote needs genuinely moving footage.
- Options live in brief.md as `- key: value` lines: music (auto, none or a file), voiceover (none or file), background (generate, library or a path), camera, transition, duration.
- Inspiration publishes to its own account. Set `accounts.inspiration` in navaan.config.json (`instagram_handle`, `youtube_channel`, `instagram_env`, `youtube_token`, optional `youtube_client_secret`). The login files must not be the NAVAAN ones. Until then every publish step refuses and posts nothing. `navaan.py account inspiration` shows what is missing.
- Never attach a famous author to a line without the originality check finding two independent sources.
- Own scene video (NAV-126): an inspiration can bring a scene video of its own, added in the New form or on the item's Content tab before its video is rendered (the same `/api/reel/upload` route; `/api/scene/remove` takes it away). The background step (and its picture spend) is replaced by "Prepare the scene video" (`inspire_scene.py`: shrinks the upload to `scene_src.mp4` without sound, deletes the big original after the check). `inspire_prep.py` then fits it to the finished length (the audio plus the end card, so the credit page always ends the short) into `scene_bg.mp4`, and the renderer plays it behind the words with the song's sound (Remotion's `Lyrics` composition, or the ffmpeg fallback). Fit: longer than the short, cut; shorter by 3 s or less, normal speed then the last frame held; shorter by more, slowed at most 1.5 times then the last frame held (`inspiration.scene.small_gap`, `inspiration.scene.max_slow`). Without a scene video nothing changes. The Aha-lorithm never uses one.
- Visual treatments (NAV-130): a short can be drawn with Remotion's capabilities chosen per short, from a library (`remotion/src/treatments/`, composition `VisualShort`). The plan is `visual_plan.json` in the item folder, checked by `scripts/visuals_plan.py` and merged into `timing.json` by `inspire_prep.py`; the renderer draws it over the usual base (`Quote` for an Aha-lorithm short, `Lyrics` for a narrated inspiration) and, if the plan fails to render, makes the plain short instead. The Aha-lorithm may use every scene treatment (hook, compare, bars, stat, chat, flow, chart, checklist, timeline, ring, strike). Inspiration stays simple: one calm caption treatment for the whole short (karaoke, rise, hero), never a scene. A figure on screen needs a `source` or `sample: true` (shown as SAMPLE DATA); the plan check enforces it. Add a treatment in both `scenes.tsx`/`captions.tsx` and `visuals_plan.py` (a test keeps them equal) and a `remotion/samples/<name>.json`; preview with `npx remotion render src/index.ts VisualShort out.mp4 --props=samples/<name>.json`. The Aha-lorithm's plan is written by the `aha-script` skill (a beat shown by a scene needs no generated picture, `picture_beats`; a figure needs a verified `source`, the sample label is for previews and a real short refuses it; `aha-check` verifies the figures) and is approved with the script: the `quote` approval hash covers `visual_plan.json`, and `navaan.set_gate` refuses an unusable plan with the reasons. A narrated inspiration with no plan of its own gets a calm caption chosen from its words (`auto_caption`); `- look: karaoke|rise|hero|plain|auto` in the brief overrides it (NAV-131). `voice_timing.py` times each word and the glow from the narration's own sound: Whisper places phrases, not words, so word starts come from the quiet dips of the voice (NAV-132). Note `visuals.json` is the music videos' own file; the plan is `visual_plan.json`.
- Aha-lorithm script changes (NAV-133): at the `quote` gate the Song page offers "Edit the words" (`/api/aha/edit-script`, same beats: `script_edit.edit`) and "Use my own words" (`/api/aha/replace-script`: writes `quote_feedback.txt` starting `REPLACE:` and redoes the `quote` step, whose outputs include `visual_plan.json`). "Request changes" at that gate now writes the note to `quote_feedback.txt` and redoes the step too (the aha-script and inspiration-quote skills read the file and delete it).
- Aha-lorithm pictures (NAV-136): `quote.json` carries `look`, one art direction per short; `aha_pictures.prompt_for` sends the beat's scene, that look and the technical limits only. No fixed house style.
- Covers (NAV-135): `make_cover.MODERN_LOOK` is the art direction for album prompts (the flow-visuals skill says it in its own words for songs); Latin lettering goes through `make_cover.LATIN` (Inter first; `fonts-inter` is in the Dockerfile). Albums have a `modern` lettering style (default) beside the poster's display fonts.
- Blog posts (NAV-134): the Song page of a blog item has a Posts tab (`BlogPosts.tsx`, `lib/markdown.ts`): a tab per destination file (`devto.md`, `linkedin_article.md`, `linkedin_post.md`), preview, copy buttons, claim markers `[cN]` stripped. The markdown reader escapes everything and keeps only http(s) links.

### Reel pipeline (your own video)

Footage uploaded in the portal (`POST /api/reel/upload`, a raw body streamed to `.cache/raw.<ext>`) -> `ingest` (shrinks it to `source.mp4`, H.264 CRF 24, at most 30 fps, long side at most `reel.proxy.max_long_side`; checks the copy plays to its last second and has the same length; only then deletes the big original unless `reel.keep_original` is true; takes about 8 to 24 stills, scene cuts and sound facts; lists the music) -> `direct` (Claude, skill `reel-director`: reads the stills, writes `scenes.json`, 3 quote options in `copy_options.json`, the chosen one as `quote.json`, and the edit plan `edl.json`; gate `quote`) -> originality check (gate `originality`) -> `edit_check` (`reel_edl.py` validates the plan against the footage and writes `edl_summary.md`; gate `edit_plan`, tied to the hash of `edl.json`) -> optional ElevenLabs narration of the quote (gate `credits`) and its timing -> `render` (`reel_render.py`: plain ffmpeg and Pillow, 1080x1920, 30 fps, 3 to 90 seconds) -> `critique` (Claude, skill `reel-critic`: advice in `critique.json`, never edits the plan; gate `media`) -> Instagram caption (gate) -> Instagram Reel (gate) -> archive -> cleanup. Reels post to Instagram only: set `accounts.reel` (`instagram_handle`, `instagram_env`).

- The footage may have no speech. The director works from what it sees; `audio.json` says whether the sound is speech-like (a guess from its shape, not a transcript) and the plan chooses what happens to it (`keep`, `ambient_low`, `denoise`, `mute`).
- Narration is ElevenLabs by default (`- narrate: eleven` in brief.md, off when no key is saved), `none` skips it (footage, music and on-screen words only), or upload a recorded or Suno-made voice on the Narration card (`file`). The spoken words are the quote.
- Music comes only from audio NAVAAN owns: published `music` items on this machine (`final_tagged.mp3`, `final.mp3`, `reel_audio.mp3`), or the owner's own upload on the Music card (`music_src.*`, which wins). Never a downloaded or third-party track, and not an inspiration's `music.mp3` until its licence is confirmed. `render_report.json` names the track used and the Instagram caption credits it.
- Config in navaan.config.json: `reel.max_upload_mb` (2048), `reel.keep_original` (false), `reel.proxy.max_long_side` (2560), `reel.proxy.crf` (24), `reel.proxy.preset` (veryfast).
- Voice and footage: the footage's own sound (the owner supplies footage with background music or ambience and no narration) is never dropped on a guess: the plan's audio policy decides, and under a voiceover it steps back (ducks) while the voice speaks, like the music. If the footage already shows the quote burned in, the plan sets `quote.show` false: the voice speaks it, it is not drawn twice.
- Intro and end card: the plan's `intro` holds the first frame (hook text over it) and `outro` holds the last frame, dimmed, with the account handle (`accounts.reel.instagram_handle`) and the music credit; a voiceover longer than the footage holds the last frame until it finishes, then the end card comes. All plan times are reel time, intro included.
- Deleting the original is the one irreversible thing the pipeline does on its own, and only after the working copy is verified.

## Instagram and YouTube analytics and growth advice

`scripts/ig_collect.py` and `scripts/yt_collect.py` (read only collectors, SQLite), `scripts/ig_reco.py` and `scripts/yt_reco.py` (rules, evidence pack, recommendation store, `--platform instagram|youtube`) feed the portal's Analytics page, which has an Instagram and a YouTube tab. YouTube uses the publishing sign-in for public counts and comments; watch time, retention, traffic and audience need one read only sign-in, `python3 scripts/yt_collect.py auth`. Impressions and click through rate are not in any YouTube API. `besttime.analyze_youtube` gives the best time to publish for videos and Shorts from your own video results, viewer countries and Instagram followers online (portal YouTube tab and the scheduler use it, `/api/besttime?platform=youtube`). The same work runs from chat or on a schedule:

- `/navaan-studio:collect [instagram|youtube|all] [account]` runs the data-collector role.
- `/navaan-studio:recommend [instagram|youtube] [account] [--collect] [--no-web]` runs the growth-advisor role with the growth-advice skill: rules write findings, Claude researches the market on the web, stores sourced notes and writes at most 6 recommendations that each cite a finding or note.
- Both are headless safe: they never ask questions, never write to Instagram or YouTube, and stop with a plain message on an auth error.
- Organic growth only. Recommendations show in the portal with Done and Dismiss; Done ones are compared with later posts.
- To schedule, create a Claude scheduled task on the computer that holds your workspace, for example weekly, with the prompt `/navaan-studio:recommend music --collect`. In Codex use the growth-advice skill by name.
