---
name: youtube-short
description: After the full video is on YouTube, make a Short from it in YouTube Studio, then download the Short as short.mp4 for Instagram. Use only after the publish_short gate is approved.
---

# YouTube Short from the uploaded video

Runs after `publish_youtube`. The agent uses Claude in Chrome on the user's own signed in Studio. The user handles login and CAPTCHA.

1. Read `meta.json` for `published.youtube_items` and take the full video id. Stop if there is none.
2. Open `https://studio.youtube.com/video/<fullId>/clips` (left menu: Clips & Shorts) and click Create clip or Short, then choose the Short option. There is no Edit into a Short item in the three dot menu. If the button is missing, tell the user and stop.
3. Pick the clip: use the chorus or the strongest hook, 30 to 60 seconds. If `reel_start.json` exists use its start. Do not add lyric captions.
4. Save the Short. Title: native script title, language and style, `#Shorts`. Description: one line hook, credits, hashtags, link to the full video. AI disclosure Yes, not made for kids. Visibility stays private until the user says public (gate `publish_short` covers making it public; ask in chat before clicking Public).
5. The new Short is listed on the same Clips & Shorts page. Open it, note its id, then Options (top right of Video details), Download (confirmed present on the full video page). The file lands in `~/Downloads`. Move it to `<song folder>/short.mp4` with `mv`.
6. Check with `ffprobe` that `short.mp4` is vertical (height greater than width), under 90 seconds, h264. If it is not vertical, tell the user and do not use it for Instagram.
7. Record in `meta.json`: `published.youtube_short = {"id": ..., "url": "https://youtube.com/shorts/<id>", "privacy": ...}` and add a history line. Never write approvals.

Instagram step then uses `short.mp4` automatically when it exists (otherwise the optional separate reel). Posting to Instagram still needs the `publish_instagram` gate and a public video URL from the cloud bucket.

Checked live 2026-10-12: Clips & Shorts page with Create clip or Short, and Options with Download, both exist. Not yet run: the clip editor itself and Download on a clip made Short. If it does not, the user downloads it by hand and saves it as `short.mp4`.
