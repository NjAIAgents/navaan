---
name: inspiration-meta
description: Write the YouTube Shorts title, description and tags for an inspiration short into youtube.json. Use for the youtube_meta step of the inspiration pipeline.
---

# YouTube Shorts metadata for an inspiration short

Write `youtube.json`. The upload reads it. YouTube treats a vertical video of 60 seconds or less as a Short, so the description needs `#Shorts`.

1. Read `quote.json`, `title.txt`, `originality.json`, `brief.md` and `navaan.config.json` (`accounts.inspiration`, `publish.default_hashtags`). If `youtube_feedback.txt` exists, apply it, then delete it.
2. JSON keys:
   - `title`: 60 characters at most. The quote's hook or a plain description of the feeling, in the quote's own script. No hashtags, no clickbait, no claim the video does not keep.
   - `language`: `hi`, `en` and so on.
   - `description`: line 1 is the quote itself or its core line. If the quote has an author, add `Quote by <author>.` as line 2 (the verified author from `originality.json`, never a different one). One short line in a warm, plain voice. Last line: up to five hashtags, `#Shorts` first, then specific ones.
   - `tags`: 6 to 12 search tags, each under 30 characters: the theme, the language, the mood, `shorts`. Nothing that misdescribes the video.
3. No angle brackets. Valid JSON, UTF-8 or `\u` escapes.
4. Print the title and hashtags and stop. Do not approve a gate and do not upload.
