---
name: analytics-loop
description: Read channel analytics after publishing and propose re-edits for the next release. Use a few days after a song is published.
---

# Analytics and re-edit loop

Instagram and YouTube numbers live in a local database filled by `python3 scripts/ig_collect.py collect` and `python3 scripts/yt_collect.py collect` (command `/navaan-studio:collect instagram|youtube|all`, read only, safe to schedule). What to change next is the growth-advice skill (command `/navaan-studio:recommend instagram|youtube`). The portal Analytics page has an Instagram and a YouTube tab, and each song's Performance tab shows both. Use those first. The steps below are the manual route for per song notes and for what the APIs do not give.

1. Pull numbers with the API where possible: `python scripts/publish_youtube.py stats <videoId> ...` gives views, likes and comments. Retention curves and traffic sources are collected by `yt_collect.py` once its read only analytics sign-in is set up (`python3 scripts/yt_collect.py auth`); click through rate and impressions exist only in YouTube Studio, so open it in the browser for those. For Instagram use the app insights or the Graph API insights the user has access to.
2. Record the date, numbers and sources in `songs/<slug>/analytics.md`.
3. Compare Shorts against full videos and Hindi against Maithili. Say what the data supports and what it does not. Small numbers are noise.
4. Propose at most three changes: title or thumbnail test, a new reel window, caption style, upload time, or the next song's theme. Each proposal names the file it changes.
5. Any change that touches a public video, including delete and re-upload, needs the user's explicit yes first. Save decisions in `navaan.config.json` through artist-setup (for channel level choices) so the lyricist and visual director use them.
