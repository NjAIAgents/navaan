---
name: inspiration-quote
description: Write or pick the quote for an inspiration short and save it as quote.json plus title.txt. Use for the quote step of the inspiration pipeline.
---

# Inspiration quote

Content type `inspiration` is a 7 to 15 second vertical video (longer only with a voice): one quote over a cinematic background. Its first line is on screen from the first frame, so put the strongest line of the quote FIRST, the one that makes someone stay. This step decides the words. Everything after it (originality check, picture, timing) depends on this file, so keep it tight.

1. Read `brief.md` (the idea, and the options block) and `navaan.config.json` (artist voice, default language). If `quote_feedback.txt` exists, apply exactly what it says, then delete it.
2. Choose the path:
   - The user gave their own words: keep them. Fix only typos and obvious breaks unless the brief asks you to tighten them. `kind` is `original`.
   - The user gave only an idea or a theme: write an original line in NAVAAN's voice, plain and warm, specific rather than generic. `kind` is `original`.
   - The user asked for a known quote: use it only if you are certain of the exact words and the real author, and mark `kind` as `attributed` (or `public_domain` for old works). Never invent an author. Never attach a famous name to a line you wrote.
   Tone: very relatable. The line should sound like a thought the viewer had today and never said aloud: an everyday moment, a small honest feeling, specific rather than grand. Prefer "you" or a shared "we" over lecturing. Skip hollow motivation ("believe in yourself") and abstract wisdom.
3. Fit the format: 6 to 28 words, one thought, readable in a few seconds per line. Natural line breaks are chosen later, so write it as normal sentences. Keep a Hindi quote in Devanagari. Keep Hinglish in the script the user wrote it in.
4. Write `quote.json`:
   `{"text": "...", "author": "Name, or empty for an original line", "kind": "original|attributed|public_domain", "language": "hi|en|hinglish", "source": "book, speech or empty", "notes": "one line on why this wording"}`
   `author` for an original line is empty unless the brief names the account or person to credit.
5. Write `title.txt`: a short title for the library, 60 characters at most, no hashtags.
6. Print the quote and the author in your final message, then stop. Do not approve any gate. The user reads and edits the quote at the `quote` gate; any edit after approval asks for a new approval.
