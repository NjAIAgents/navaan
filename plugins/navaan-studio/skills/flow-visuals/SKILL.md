---
name: flow-visuals
description: Create cover art and short visual clips for a NAVAAN song in Google Flow through the browser. Use after the song is accepted.
---

# Cover art and Flow clips

Videos are built only from Flow clips. Do not use the default Suno cover unless the user asks.

0. Read `navaan.config.json` (languages, genres, moods, voice, things to avoid, palette, motifs, Suno model, credit policy) and follow it. Run artist-setup if it is missing.
1. Read the lyrics and `style.txt`. Write a visual brief: five scenes (for example a diya, a moon over a river, hands, a window, a field) with one consistent look. Save it as `scenes/` text files.
2. Open Flow in the browser. Generating spends credits: only do it when the credits gate is approved and the user said yes in chat, then generate the five clips. Name them `c1_<word>.mp4` to `c5_<word>.mp4` in `songs/<slug>/clips/`.
3. Cover art: take one strong frame from a clip (`cover_flow.jpg`), then make `cover_1x1.png`, `cover_16x9.png` and `thumb_16x9.jpg`. Keep the song title large and legible in the native script.
4. Show previews to the user and record approval in `meta.json`.

Large files fail the sandbox bridge above about 1.5 MB, so do all file work on the user's computer and only send small previews to chat.
