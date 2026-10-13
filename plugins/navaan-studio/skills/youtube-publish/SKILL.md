---
name: youtube-publish
description: Publish a finished video or Short to YouTube with the official Data API, or through YouTube Studio when the API is not set up. Use only after the publish_youtube gate is approved and the user said yes.
---

# YouTube publish

Preferred path: the official YouTube Data API v3 through `scripts/publish_youtube.py`. Fallback: YouTube Studio in the browser.

## API path

One time, done by the user, never by an agent: enable YouTube Data API v3 in Google Cloud, create an OAuth client of type Desktop app, save its JSON as `~/.config/navaan/youtube_client_secret.json`, and run any upload once so the browser consent screen stores a token in `~/.config/navaan/youtube_token.json`. Install `google-api-python-client` and `google-auth-oauthlib`.

Every upload:

1. The `youtube_meta` step writes `youtube.json` (skill youtube-meta). Pass it with `--meta youtube.json`; the pipeline does. A metadata JSON in the song folder (a per language file also works) with `title`, `description`, `tags`, `language`, and optional `playlist`. Use the profile for credit text, hashtags, playlists and the AI disclosure. Shorts keep `#Shorts` in the title.
2. Dry run, which sends nothing: `python scripts/publish_youtube.py upload <slug> --file final_reel_cap.mp4 --meta tags.json`. Show the printed payload to the user.
3. Get the user's explicit yes for this exact file, title and privacy, and make sure the gate is approved (`python scripts/navaan.py approve <slug> publish_youtube`, done by the user).
4. Send it: add `--yes`. Default privacy is private so the user can check the upload first. Add `--privacy public`, or `--privacy private --publish-at 2026-10-20T15:00:00Z` to schedule.
5. The script sets the altered or synthetic content flag from the profile (`containsSyntheticMedia`), marks made for kids from the profile, adds the thumbnail and playlist when given, and records the URL in `meta.json`.
6. To fix title, description, tags or thumbnail of an uploaded video: `python scripts/publish_youtube.py update <slug> <videoId> --meta youtube.json --thumbnail thumb_16x9.jpg` (dry run first, `--yes` after the user approves).
7. To change privacy later: `python scripts/publish_youtube.py privacy <slug> <videoId> public --yes`. Same rules.

Quota and review rules for API projects change. Check the YouTube Data API quota page and the API Services audit requirements before relying on bulk uploads. If YouTube restricts uploads from an unaudited project, tell the user and use the Studio fallback.

## Studio fallback

Never click Publish without a fresh explicit yes. Check the filename in the Filename field (a `_cap` file), then title, description, tags, language, playlist, AI disclosure under Show more, not made for kids. The user attaches big files in the upload dialog. Click inside the title box before select all. The Publish button appears only after Public is selected. A video of 1 minute or less gets a `/shorts/` link.

YouTube cannot swap the video file of an existing upload. A fix means a new upload and, with a separate explicit yes, deleting the old one.
