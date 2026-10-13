---
name: youtube-meta
description: Write the YouTube metadata (title, description, tags, language) for a finished song into youtube.json. Use for the youtube_meta step, before the video is uploaded.
---

# YouTube metadata

Write `songs/<slug>/youtube.json`. The upload reads it, so a missing or thin file means a video with no description and no tags. Write it fresh for this song, not from an earlier song's wording.

1. Read `title.txt`, `lyrics.txt`, `brief.md`, `style.txt`, `tags.json` and `navaan.config.json` (artist name, `publish.credit_text`, `publish.default_hashtags`, `publish.youtube_handle`, `publish.playlists`). If `youtube_feedback.txt` exists, apply exactly what it says, then delete it.
2. JSON keys:
   - `title`: the song title in its own script, romanized alias after a pipe only when the native title is not Latin. 100 characters at most. No `#Shorts`.
   - `language`: `hi`, `en`, `mai` and so on.
   - `description`, in this order:
     1. Hook in the first 125 characters (this is all search and the feed show): one honest line about the song, or a lyric line in its own script.
     2. Two or three short lines about the story and feeling, plain, warm, no hype.
     3. Credit text from the profile, then genre and mood in one line.
     4. `Lyrics` heading, then the sung lyrics from `lyrics.txt` with every `[Section]` line removed and blank lines kept between stanzas.
     5. Last line: up to five hashtags, always the profile defaults first, then ones specific to this song (language, mood, theme). No generic `#viral` or `#fyp`.
   - `tags`: 8 to 15 search tags, each under 30 characters, 450 characters in total at most: the song title and its romanized spelling, artist, language plus genre, mood, theme words, and what a listener would search for. No tag that misdescribes the song.
   - `playlist`: only when the profile maps this song's language to a playlist.
3. Description stays under 4500 bytes. No angle brackets (YouTube rejects them). Use `\u` escapes or UTF-8, valid JSON either way.
4. Save the file, print the title, hook, tags and hashtags in the final message, and stop. Do not approve any gate and do not upload. The user reads the payload at the `publish_youtube` gate and can ask for a rewrite with a `youtube_feedback.txt` note.

   Standing rules: if `<local_dir>/standing_rules.json` exists (next to the songs folder, written when the user presses Implement on a recommendation), apply every rule for this account whose category is caption, hook, hashtags, engagement, packaging or format, and say which ones you applied.
