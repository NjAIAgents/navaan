---
name: aha-script
description: Write the narrated script of an Aha-lorithm short (hook, explanation, the aha) as beats, each with its spoken line, its short on-screen caption and one picture prompt, saved as quote.json plus title.txt. Use for the script step of the aha pipeline.
---

# Aha-lorithm script

Content type `aha` is a 20 to 25 second vertical YouTube Short for The Aha-lorithm (@TheAhalorithm): AI explained in seconds. One misconception, one clear explanation, one memorable insight. ElevenLabs reads the spoken lines from the first frame (a calm, natural narrator, about 140 words a minute), each beat has its own picture, and the renderer draws the beat's caption in the safe area. Quiet ambient music sits far under the voice, drops back while the aha line lands, and the end card shows "The Aha-lorithm · AI explained in seconds".

1. Read `brief.md` and `navaan.config.json`. If `quote_feedback.txt` exists, apply exactly what it says, then delete it. The brief starts the short in one of three ways:
   - **The owner's own narration** (a hook and/or the spoken text): keep their words exactly. Only split them into beats, write the captions and the picture prompts. Fix nothing but typos.
   - **An idea or a topic**: write the script from it.
   - **Nothing** (empty idea): pick a topic yourself, an AI misconception or habit most people get wrong, useful today. Read `title.txt` of the other `aha-*` items first and do not repeat a topic.
2. Beats, one spoken sentence each (6 to 9 beats, 45 to 60 words in all, so it lands inside 25 seconds):
   - **Hook** (beat 1, 0 to 3 s): 4 to 9 words that stop the scroll. A surprising claim. Never a greeting, never "In this video".
   - **Explanation** (the middle beats): why it is true, in plain words a 15-year-old follows. One idea per beat.
   - **The aha** (one beat near the end): the takeaway in 4 to 8 words the viewer will repeat. Then at most one beat on what to do.
   Write for the ear: short words, no lists, no parentheses, no abbreviations the voice would spell out.
3. Captions: for each beat a SHORT on-screen caption, 2 to 6 words, that sharpens the spoken line rather than repeating it in full (spoken "That's what makes it dangerous." → caption `Confident *≠ correct*`). Mark the important phrase with asterisks; it is drawn in muted gold, the rest in white. Use marks on at most 4 beats in the whole short, always on the aha.
4. Facts: say only what you can back with a reliable source; the next step checks every claim on the web. No invented numbers, studies or quotes. An example of an AI mistake must be clearly illustrative ("it might say..."), never a claim that a named product said it.
5. Pictures: one prompt per beat, 20 to 80 words: a cinematic, mostly abstract image of the beat's idea (a gold neural network forming in darkness, a crystal ball with a fine crack, one bright path among many, a magnifying glass over a source document). One look across the beats: near-black backgrounds, luminous gold with small touches of cool blue. People only in silhouette or from behind; no real or famous person, no brand logo. Never ask for words, letters, numbers or readable screens: the renderer adds the text. Keep the middle of the frame calm enough for a caption.
6. Write `quote.json`:
   `{"text": "the spoken lines joined with spaces", "lines": ["spoken line of beat 1", "..."], "captions": ["caption of beat 1 with *marks*", "..."], "pictures": ["prompt for beat 1", "..."], "aha": <index of the aha beat, from 0>, "author": "", "kind": "original", "language": "en", "sources": ["URLs that back the facts"], "notes": "one line on the angle"}`
   `lines`, `captions` and `pictures` have the same length. `lines` carry no asterisks.
7. Write `title.txt`: the hook as a title, 60 characters at most, no hashtags.
8. Print the beats (spoken line, caption) in your final message, then stop. Do not approve any gate. The owner reads and edits the script at the `quote` gate.
