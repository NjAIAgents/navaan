---
name: lyrics
description: Write song lyrics and a Suno style prompt for NAVAAN in Hindi, Maithili, English or Hinglish. Use for a new song idea, a lyrics revision, or a language adaptation.
---

# Lyrics and style

Inputs: the user's idea or `songs/<slug>/brief.md`, plus `style-notes.md`.

0. Read `navaan.config.json` (languages, genres, moods, voice, things to avoid, palette, motifs, Suno model, credit policy) and follow it. Run artist-setup if it is missing.
1. Confirm language, mood, tempo feel, voice (male, female, duet), and whether there is a rap or bridge. Ask once, in one short question, only for what is missing.
2. Write `lyrics.txt` with section tags on their own lines, for example `[Verse 1]`, `[Chorus]`, `[Rap]`, `[Bridge]`. Keep lines singable. Chorus lines run about 6 seconds, verse lines 3 to 4 seconds when sung.
3. Write `style.txt`: genre, mood, tempo, instruments, vocal type, language. Keep it under 120 characters when Suno limits it, and avoid artist names.
4. Write `title.txt` and, for multi language releases, `title_hindi.txt` or `title_maithili.txt`.
5. If lyrics are rewritten later, keep the old file (for example `lyrics_maithili_v3.txt`) and mark which file is the one actually sung in `meta.json` under `sung_lyrics`. The caption aligner reads that file.
6. Show the lyrics and style to the user. This is gate one. Allow at most three revision loops, then summarize the disagreement and ask for a decision.
7. On approval set `state` to `lyrics_ok`.

Quality bar: no filler repeats, rhymes in the sung language not in transliteration, no lines that Suno cannot pronounce. Avoid words listed in `style-notes.md`.
