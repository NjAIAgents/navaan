---
name: instagram-caption
description: Write the Instagram Reel caption for a finished song, personalized from its lyrics. Use for the instagram_caption step, and again when the user asks for a rewrite.
---

# Instagram caption

Write `songs/<slug>/instagram.txt`, personalized to this song. Do not reuse a template or the wording of an earlier caption.

1. Read `lyrics.txt`, `brief.md` and `title.txt` (theme, mood, language, any story the user told you). If `caption_feedback.txt` exists, read it, apply exactly what the user asked for, then delete `caption_feedback.txt`. The previous draft is in `instagram.prev.txt`.
2. Write a caption that could only belong to this song:
   - Hook (first line, inside the first 125 characters, since only those show before "more"): built from the song's own words or core feeling. A specific question fans can answer in the comments, a quoted line, or one honest sentence about what the song is about. Keep the lyric in its own script. Vary the shape from song to song.
   - Body: one or two short lines in NAVAAN's voice about the feeling or the story behind the song. Plain, warm, no hype, no filler.
   - Call to action: one, matched to the song (tag someone, share with someone, comment a line). Put the full song link in the caption itself, never "link in bio" (the bio has no link). Read `published.youtube_items[0].url` from `songs/<slug>/meta.json`, the full video and not the Short, and write it on its own line above the hashtags as `Full song on YouTube: <url>`. The caption step runs after go_public, so the URL exists. If meta has no full video URL yet, leave the YouTube line out and say so in your final message.
   - Hashtags: five at most, specific to this song's language, mood and theme, always including #NAVAAN. No generic #Reels or #fyp.
     If `<local_dir>/hashtags.json` exists (next to the songs folder, written by the analytics analysis), take up to two tags from `suggested.music` that are not `in_use` and fit this song's language and mood, and prefer the top entries of `own.music` by `avg_views` for the rest. Say in your final message which suggested tags you used.
   - Whole caption 100 to 300 characters. No AI or tool credit line, Instagram does not require one.
3. Save the file, print the caption in your final message, and stop. Do not approve the `instagram_caption` gate and do not publish. The orchestrator prints the caption for the user. The user approves it, edits it, or asks for a rewrite with `navaan.py caption <slug> --feedback "..."`. Any edit after approval clears the approval, so the caption that posts is always the one the user approved.

   Standing rules: if `<local_dir>/standing_rules.json` exists (next to the songs folder, written when the user presses Implement on a recommendation), apply every rule for this account whose category is caption, hook, hashtags, engagement, packaging or format, and say which ones you applied.
