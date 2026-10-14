---
name: youtube-short
description: After the full video is on YouTube, make a Short from it in YouTube Studio, then download the Short as short.mp4 for Instagram. Use only after the publish_short gate is approved.
---

# YouTube Short from the uploaded video

Only for songs that use Flow visuals. Songs with their own pictures get the Short from `shots_render.py <slug> --reel` and an API upload, with no browser (see deploy/README.md).

Runs after `publish_youtube`. The agent uses Claude in Chrome on the user's own signed in Studio. The user handles login and CAPTCHA.

1. Read `meta.json` for `published.youtube_items` and take the full video id. Stop if there is none.
2. Open `https://studio.youtube.com/video/<fullId>/clips`, click Create clip or Short, choose New Short. Wait about 10 seconds for the transcript (Hindi auto-transcript works, it has [संगीत] tags).
3. Pick the clip: drag across the transcript lines of the chorus or hook, then click Confirm new selection. The header shows Short duration, which must be 60 sec or less (about 4 lines of transcript is 57 sec). Click Preview Short, then Create draft. Studio opens the upload dialog, saved as private, with a `/shorts/<id>` link. Note the id. Add title and description there if the user wants it kept.
4. Details for the Short. Title: native script title, language and style, `#Shorts`. Description: one line hook, credits, hashtags, link to the full video. AI disclosure Yes, not made for kids. Visibility stays private. Never click Public: the `go_public` step makes the full video and the Short public together, at the end.
5. Wait about 2 minutes for processing (the page shows a draft state and a loading thumbnail). Open `https://studio.youtube.com/video/<shortId>/edit`, Options (three dots top right of Video details), Download. The file lands in `~/Downloads` as `<title>.mp4` (`Untitled video.mp4` for an untitled draft). Move it to `<song folder>/short.mp4` with `mv`.
6. Check with `ffprobe` that `short.mp4` is vertical (height greater than width), under 90 seconds, h264. If it is not vertical, tell the user and do not use it for Instagram.
7. Record in `meta.json`: `published.youtube_short = {"id": ..., "url": "https://youtube.com/shorts/<id>", "privacy": ...}` and add a history line. Never write approvals.

Instagram step then uses `short.mp4` automatically when it exists (otherwise the optional separate reel). Posting to Instagram still needs the `publish_instagram` gate and a public video URL from the cloud bucket.

Tested live 2026-10-12 on song-003: draft Short created private, downloaded as 608x1080 h264, 56 s, then deleted. Instagram Reels accept this shape (vertical, mp4, h264). The run was done by hand in Chrome, the orchestrated step itself has not been run.
