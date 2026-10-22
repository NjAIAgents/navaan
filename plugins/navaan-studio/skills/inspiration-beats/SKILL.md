---
name: inspiration-beats
description: Plan the pictures of an inspiration short made with "a picture per beat": group the quote's lines into beats and write one scene prompt per beat plus one look for the whole short, saved as picture_plan.json. Use for the beat_plan step. Spends nothing.
author: Navjyot Nishant
---

# Inspiration pictures, one per beat

An inspiration short normally has one background picture. With `- pictures: beats` in `brief.md` it has a few pictures instead, and the picture changes where the thought changes. This step plans them and spends nothing; the pictures are made after the owner approves the price.

1. Read `quote.json` (`lines`, `language`), `brief.md`, `navaan.config.json` (palette and motifs, if the profile has them) and `style-notes.md` if present. If `picture_feedback.txt` exists, apply exactly what it says, then delete it.
2. Beats. Group the lines, in order, into **2 to 6 beats, always fewer beats than lines** (a script of 5 lines takes 3 or 4). A beat is one thought: lines that say the same thing from two sides stay together; a turn ("But", "Instead", "So") starts a new beat. Every line belongs to exactly one beat and a beat is whole lines. Each beat has at least 5 words in all, so its picture stays up long enough to be seen. The last line (the closing) keeps the last beat's picture to the end of the short, so give the closing its own beat only when it is a turn.
3. `look`: one art direction, 15 to 40 words, chosen for THIS short and used for every picture so they belong together: the medium, the palette, the mood, the light. This channel is moody and photographic and quiet (dusk, rain, empty rooms, long shadows, soft grain), not illustrated and not anime. Vary the palette and the place from short to short.
4. One prompt per beat, 20 to 80 words: a concrete scene taken from what the beat says, not a literal picture of its words. People only in silhouette or from behind, no real or famous person, no brand logo. Never ask for words, letters, numbers or readable screens: the renderer draws the words. Keep the middle of the frame calm (a plain wall, sky, water, shadow) because the line sits there. Before writing, list each beat's subject and framing and make sure no two beats share a subject or a composition: alternate wide, close and overhead shots and change the main subject.
5. Write `picture_plan.json`:
   `{"look": "the short's art direction", "beats": [{"lines": [0, 1], "prompt": "the scene of beat 1"}, {"lines": [2], "prompt": "..."}]}`
   `lines` count from 0 and cover every line once, in order.
6. Run `python3 <plugin>/scripts/beat_plan.py <slug> --check` and fix every problem it prints until it says `ok`. Print the plan in a few lines (each beat, which lines, its scene in five words) and stop. Do not make any picture, do not open a browser, do not approve gates.
