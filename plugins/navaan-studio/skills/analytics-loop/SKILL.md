---
name: analytics-loop
description: Read channel analytics after publishing and propose re-edits for the next release. Use a few days after a song is published.
---

# Analytics and re-edit loop

1. Pull numbers with the API where possible: `python scripts/publish_youtube.py stats <videoId> ...` gives views, likes and comments. For retention curves, click through rate and traffic sources, open YouTube Studio analytics in the browser. For Instagram use the app insights or the Graph API insights the user has access to.
2. Record the date, numbers and sources in `songs/<slug>/analytics.md`.
3. Compare Shorts against full videos and Hindi against Maithili. Say what the data supports and what it does not. Small numbers are noise.
4. Propose at most three changes: title or thumbnail test, a new reel window, caption style, upload time, or the next song's theme. Each proposal names the file it changes.
5. Any change that touches a public video, including delete and re-upload, needs the user's explicit yes first. Save decisions in `navaan.config.json` through artist-setup (for channel level choices) so the lyricist and visual director use them.
