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

1. Write `songs/<slug>/instagram.txt`: one hook line, the language, credits, five to eight hashtags including #NAVAAN. Reels are 9:16 and up to 90 seconds, so use `final_reel_cap.mp4`.
2. Dry run: `python scripts/publish_instagram.py publish <slug> --video-url <https url> --caption-file instagram.txt`. Show the plan to the user.
3. After the gate and the explicit yes: add `--yes`. The script creates the container, polls its status, publishes, and records the permalink in `meta.json`.
4. Delete the temporary public object and the pre-authenticated link afterwards.

The API allows a limited number of API published posts per rolling 24 hours. `python scripts/publish_instagram.py limit` shows current usage. Meta changes API versions and review rules, so confirm them in Meta's documentation before a first live run. If the API cannot be used, give the user the finished file and caption and let them post it in the app.
