---
name: reel-director
description: Watch the stills of an uploaded video, understand its scenes, suggest quotes that fit them, and plan the edit (cuts, framing, grade, sound, music, text). Use for the direct step of a reel item. Writes scenes.json, copy_options.json, edl.json, quote.json and title.txt.
author: Navjyot Nishant
---

# Reel director

Content type `reel`: the owner's own footage becomes a vertical Instagram reel (1080x1920, 15 to 45 seconds, never over 90). You decide WHAT the reel says and HOW it is cut. ffmpeg carries it out (`reel_render.py`) and a person approves the words (`quote` gate) and the plan (`edit_plan` gate) before anything is rendered. The footage may have NO speech, only the sound of the place: the reel is driven by what you SEE, not by a transcript.

## Read first
`brief.md` (the idea and the options block), `probe.json` (size, length, source size), `frames.json` and every still in `frames/` (use Read on each image: each carries its time `t=` in the corner), `scenes_auto.json` (scene-change times), `audio.json` (`has_audio`, `has_speech` is only a guess from the shape of the sound, `silences`, `range_db`), `music_library.json`, and `navaan.config.json` (artist voice, default language). If `quote_feedback.txt` or `edit_feedback.txt` exists, apply exactly what it says, then delete it. Never invent footage you cannot see: every claim about a scene must be visible in a still.

## 1. scenes.json
`{"summary": "two plain sentences", "mood": "calm|joyful|wistful|energetic|...", "segments": [{"start": s, "end": s, "setting": "", "subject": "", "motion": "static|slow|fast|shaky", "light": "", "feeling": "what a viewer feels here", "quality": "good|ok|poor", "use": "hook|body|skip", "frames": ["frames/f03.jpg"]}]}`
Segments follow the scene cuts and the stills (a few seconds each). Mark shaky, dark, blurred or empty stretches `skip`.

## 2. The quote (what fits THESE scenes)
Write 3 options in `copy_options.json`:
`{"language": "en|hi|hinglish", "quotes": [{"id": "a", "lines": ["...", "..."], "kind": "original", "why": "which scene it answers and why it fits", "recommended": true}], "caption_draft": "...", "hashtags": ["..."]}`
Rules: original lines only unless you are certain of the exact words and real author (then `kind` `attributed` and name the author; never attach a famous name to a line you wrote; the originality step checks it on the web). Relatable, specific, warm, one thought, 6 to 28 words in 1 to 3 short lines, strongest line first. Match the language of the brief or the artist's default; Hindi in Devanagari. The quote is also what the narration speaks when a voice is on, so write it to be heard. Let the footage lead: a quiet empty beach asks for a still, slow line; a busy market for a lighter one.
Copy the recommended option into `quote.json` exactly as `inspiration-quote` does: `{"text": "...", "lines": [...], "author": "", "kind": "original", "language": "...", "source": "", "notes": "why it fits"}` and write `title.txt` (60 characters at most).

## 3. edl.json (the edit plan; checked by `reel_edl.py`, a bad plan fails before rendering)
```
{"segments": [{"start": 2.0, "end": 7.5, "crop_x": 0.5, "crop_y": 0.5, "zoom": 1.0, "zoom_to": 1.12},
              {"start": 12.0, "end": 19.0, "crop_x": 0.35, "crop_y": 0.5, "zoom": 1.0, "zoom_to": 1.0}],
 "grade": {"look": "warm", "brightness": 0.02, "contrast": 1.05, "saturation": 1.05, "gamma": 1.0, "vignette": false},
 "stabilize": false,
 "audio": {"policy": "ambient_low", "ambient_level": 0.25, "voice_level": 1.0, "vo_start": 0.4,
           "music": {"slug": "song-001", "file": "final.mp3", "start": 40, "level": 0.35, "fade_in": 1.0, "fade_out": 1.5}},
 "text": [{"text": "Some places feel like a pause", "start": 0.3, "end": 2.6, "pos": "top"}],
 "quote": {"start": 3.0, "pos": "mid", "font": "serif"},
 "thumb_t": 1.5}
```
That is a complete, valid plan (a real one has your own numbers). Allowed values: `grade.look` is one of `natural`, `warm`, `cool`, `cinematic`, `vivid`, `mono`; `audio.policy` is one of `keep`, `ambient_low`, `denoise`, `mute`; `pos` is one of `top`, `mid`, `low`; `quote.font` is `serif` or `sans`. Leave `audio.music` out (or `null`) for no music.
- `segments`: kept stretches of the footage in PLAY order, source seconds, not overlapping each other. Open with the strongest visual (movement, a face, a striking frame): you may move it to the front. Drop `skip` stretches. Total 15 to 45 s, never longer than the footage; a footage under 6 s is used whole. With a narration the reel must be at least `0.4 + (characters of the quote)/12 + 2` seconds.
- `crop_x`, `crop_y`: where the 9:16 window sits in the footage, 0 = left/top edge, 1 = right/bottom. For a landscape source the window is `ih*9/16` wide; to centre it on a subject seen at horizontal fraction p of the still: `crop_x = (p*iw - ow/2)/(iw - ow)` with `ow = ih*9/16`, clamped 0 to 1. A source that is already vertical needs 0.5. `zoom` to `zoom_to` (1.0 to 1.6) is a slow punch in or out: use it on static, calm stretches, at most 1.25 here, and never on shaky ones.
- `grade`: choose from what the stills show (underexposed: brightness up to +0.1, flat: contrast 1.08 to 1.15, dull: saturation 1.1). Small moves; `stabilize` true only for shaky handheld stretches.
- `audio.policy`: no sound or only wind, traffic or crowd noise: `ambient_low` (kept quietly, level 0.15 to 0.35) or `denoise`, `mute` if it is harsh. Real speech in the footage (`has_speech` true with medium or high confidence): `keep`, and never cut inside speech: cut only at `silences`. Never cut mid-word. With a narration voice, keep ambient low (0.15 to 0.25).
- `audio.music`: pick ONE track from `music_library.json` whose style, title and lyric lines suit the mood (or none when the list is empty). Only listed tracks are allowed. For a long full song start near 20 to 35 percent into it, else 0; you cannot hear it, so say that in `copy_options.json` `notes`. If `own_upload` is not null the owner's own track is used instead: leave `music` as it is. Level 0.3 to 0.45 without a voice, 0.25 to 0.35 with one.
- `text`: at most one short hook line at the start (4 to 8 words, a curiosity or the feeling, not a title) at `top`, ending before the quote starts, plus optional callouts. `quote.start`: when the first quote line appears, after the hook, in the calmest stretch; `pos` `mid` or `low` (the bottom fifth belongs to the app's buttons, never use it).
- `thumb_t`: the cleanest, most inviting second of the reel.

## Finish
Print what you chose (the recommended quote, the arc of the cuts, the music or why none) in a few lines, then stop. Do not approve any gate, publish or spend credits. If you truly need a human decision (a language, which of two moods), write `question.json` as the runner describes and stop instead of guessing.
