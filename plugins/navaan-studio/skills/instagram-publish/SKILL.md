---
name: instagram-publish
description: Publish an Instagram Reel through the official Instagram Graph API. Use only after the publish_instagram gate is approved and the user said yes.
---

# Instagram publish

Official route: the Instagram Graph API content publishing flow in `scripts/publish_instagram.py`. Do not scrape or use unofficial private APIs.

## One time, done by the user

1. Make the Instagram account a professional account (Business or Creator).
2. Create a Meta developer app with the content publishing permission (`instagram_business_content_publish` for Instagram Login, or `instagram_content_publish` for Facebook Login) and generate an access token.
3. Put `NAVAAN_IG_USER_ID` and `NAVAAN_IG_TOKEN` in the shell environment. Never in the project and never in chat. Optional: `NAVAAN_IG_HOST` and `NAVAAN_IG_API_VERSION`.
4. The API fetches the video from a public https URL. Use an OCI bucket (`storage.cloud_provider` oci in the profile) and `scripts/oci_public_url.sh <file>` to get a temporary pre-authenticated link, or host the file another way.

## Every reel

1. Write `songs/<slug>/instagram.txt` yourself, personalized to this song. Do not reuse a template or the wording of an earlier caption. Read `lyrics.txt` and the song brief first (theme, mood, language, any story the user told you), then write a caption that could only belong to this song:
   - Hook (first line, inside the first 125 characters, since only those show before "more"): built from the song's own words or core feeling. A specific question fans can answer in the comments, a quoted line, or one honest sentence about what the song is about. Keep the lyric in its own script. Vary the shape from song to song.
   - Body: one or two short lines in NAVAAN's voice about the feeling or the story behind the song. Plain, warm, no hype, no filler.
   - Call to action: one, matched to the song (tag someone, share with someone, comment a line). End with "Full song on YouTube, link in bio." only if the full video is already published.
   - Hashtags: five at most, specific to this song's language, mood and theme, always including #NAVAAN. No generic #Reels or #fyp.
   - Whole caption 100 to 300 characters. No AI or tool credit line, Instagram does not require one.
   - Show the user the caption with the dry run and apply edits before `--yes`. The API cannot edit a caption after publishing.
   - Reference only, for the first song (song-003): hook "Who is your तेरे होने से? Tag them." Do not copy this shape for other songs.

   Reels are 9:16 and up to 90 seconds, so use `final_reel_sync.mp4` (the tuned reel) when it exists, otherwise `short.mp4` (the Short downloaded from YouTube Studio). Keep any on-screen text in the band 500 to 1400 px from the bottom of a 1080x1920 frame. The API cannot edit a caption after publishing, so get the caption right before `--yes`.
2. Dry run: `python scripts/publish_instagram.py publish <slug> --video-url <https url> --caption-file instagram.txt`. Show the plan to the user.
3. After the gate and the explicit yes: add `--yes`. The script creates the container, polls its status, publishes, and records the permalink in `meta.json`.
4. Delete the temporary public object and the pre-authenticated link afterwards.

The API allows a limited number of API published posts per rolling 24 hours. `python scripts/publish_instagram.py limit` shows current usage. Meta changes API versions and review rules, so confirm them in Meta's documentation before a first live run. If the API cannot be used, give the user the finished file and caption and let them post it in the app.
