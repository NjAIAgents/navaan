---
name: reel-director
description: Watch the stills of an uploaded video, understand its scenes, suggest quotes that fit them, and plan the edit (cuts, framing, grade, sound, music, text). Use for the direct step of a reel item. Writes scenes.json, copy_options.json, edl.json, quote.json and title.txt.
author: Navjyot Nishant
---

# Reel director

Content type `reel`: the owner's own footage becomes a vertical Instagram reel (1080x1920, 15 to 45 seconds, never over 90). You decide WHAT the reel says and HOW it is cut. ffmpeg carries it out (`reel_render.py`) and a person approves the words (`quote` gate) and the plan (`edit_plan` gate) before anything is rendered. The footage may have NO speech, only the sound of the place: the reel is driven by what you SEE, not by a transcript.

## Read first
`brief.md` (the idea and the options block; its `- narrate:` line says whether a voice will be added: `eleven` means an ElevenLabs voice speaks the quote, `file` means an uploaded voice, `none` means no voice), `probe.json` (size, length, source size), `frames.json` and every still in `frames/` (use Read on each image: each carries its time `t=` in the corner), `scenes_auto.json` (scene-change times), `audio.json` (`has_audio`, `has_speech` is only a guess from the shape of the sound, `silences`, `range_db`), `music_library.json`, and `navaan.config.json` (artist voice, default language). If `quote_feedback.txt` or `edit_feedback.txt` exists, apply exactly what it says, then delete it. Never invent footage you cannot see: every claim about a scene must be visible in a still.

## 1. scenes.json
`{"summary": "two plain sentences", "mood": "calm|joyful|wistful|energetic|...", "segments": [{"start": s, "end": s, "setting": "", "subject": "", "motion": "static|slow|fast|shaky", "light": "", "feeling": "what a viewer feels here", "quality": "good|ok|poor", "use": "hook|body|skip", "frames": ["frames/f03.jpg"]}]}`
Segments follow the scene cuts and the stills (a few seconds each). Mark shaky, dark, blurred or empty stretches `skip`.

## 2. The quote (what fits THESE scenes)
Write 3 options in `copy_options.json`:
`{"language": "en|hi|hinglish", "quotes": [{"id": "a", "lines": ["...", "..."], "kind": "original", "why": "which scene it answers and why it fits", "recommended": true}], "caption_draft": "...", "hashtags": ["..."]}`
Rules: original lines only unless you are certain of the exact words and real author (then `kind` `attributed` and name the author; never attach a famous name to a line you wrote; the originality step checks it on the web). Relatable, specific, warm, one thought, 6 to 28 words in 1 to 3 short lines, strongest line first. Match the language of the brief or the artist's default; Hindi in Devanagari. The quote is also what the narration speaks when a voice is on, so write it to be heard. Let the footage lead: a quiet empty beach asks for a still, slow line; a busy market for a lighter one.
**Look at the stills for words already in the picture.** Footage often has the quote or a title burned in (a caption, a watermark). If a still shows the quote, or nearly the same words, already on screen, the reel must not draw it a second time: set `quote.show` to false in the plan (the voice still speaks it) and say so in `copy_options.json` `notes`. Then `quote.json` holds exactly the words the footage shows, so the voice matches. Never draw rendered text over a person's face or over text that is already there.
Copy the recommended option into `quote.json` exactly as `inspiration-quote` does: `{"text": "...", "lines": [...], "author": "", "kind": "original", "language": "...", "source": "", "notes": "why it fits"}` and write `title.txt` (60 characters at most).

## 3. edl.json (the edit plan; checked by `reel_edl.py`, a bad plan fails before rendering)
```
{"segments": [{"start": 2.0, "end": 7.5, "crop_x": 0.5, "crop_y": 0.5, "zoom": 1.0, "zoom_to": 1.12},
              {"start": 12.0, "end": 19.0, "crop_x": 0.35, "crop_y": 0.5, "zoom": 1.0, "zoom_to": 1.0}],
 "intro": {"seconds": 1.5},
 "outro": {"seconds": 3.0, "handle": true, "credit": true},
 "grade": {"look": "warm", "brightness": 0.02, "contrast": 1.05, "saturation": 1.05, "gamma": 1.0, "vignette": false},
 "stabilize": false,
 "audio": {"policy": "ambient_low", "ambient_level": 0.25, "voice_level": 1.0, "vo_start": 1.9,
           "music": {"slug": "song-001", "file": "final.mp3", "start": 40, "level": 0.35, "fade_in": 1.0, "fade_out": 1.5}},
 "text": [{"text": "Some places feel like a pause", "start": 0.3, "end": 2.6, "pos": "top"}],
 "quote": {"start": 4.0, "pos": "low", "font": "serif", "show": true},
 "thumb_t": 3.0}
```
That is a complete, valid plan (a real one has your own numbers). Allowed values: `grade.look` is one of `natural`, `warm`, `cool`, `cinematic`, `vivid`, `mono`; `audio.policy` is one of `keep`, `ambient_low`, `denoise`, `mute`; `pos` is one of `top`, `mid`, `low`; `quote.font` is `serif` or `sans`. Leave `audio.music` out (or `null`) for no music.
- `segments`: kept stretches of the footage in PLAY order, source seconds, not overlapping each other. Open with the strongest visual (movement, a face, a striking frame): you may move it to the front. Drop `skip` stretches. Total 15 to 45 s, never longer than the footage; a footage under 6 s is used whole. With a narration the reel must be at least `0.4 + (characters of the quote)/12 + 2` seconds.
- `intro` and `outro`: the first and the last frame held, so a short clip can carry a hook line and a credit. `intro.seconds` (0 to 3) holds the first frame before the footage plays (the hook `text` goes over it); `outro.seconds` (0 to 6) holds the last frame, dimmed, with the account handle and the music credit drawn over it (`handle` and `credit` switch each off). Footage under 15 s: use an intro of 1 to 2 s and an end card of 3 s. All times in `text`, `quote` and `audio.vo_start` are reel time, intro included; `vo_start` defaults to the intro plus 0.4 s, and the reel is held longer by itself when the voice outlasts it. Total length including both: 3 to 90 s.
- `crop_x`, `crop_y`: where the 9:16 window sits in the footage, 0 = left/top edge, 1 = right/bottom. For a landscape source the window is `ih*9/16` wide; to centre it on a subject seen at horizontal fraction p of the still: `crop_x = (p*iw - ow/2)/(iw - ow)` with `ow = ih*9/16`, clamped 0 to 1. A source that is already vertical needs 0.5. `zoom` to `zoom_to` (1.0 to 1.6) is a slow punch in or out: use it on static, calm stretches, at most 1.25 here, and never on shaky ones.
- `grade`: choose from what the stills show (underexposed: brightness up to +0.1, flat: contrast 1.08 to 1.15, dull: saturation 1.1). Small moves; `stabilize` true only for shaky handheld stretches.
- `audio.policy`: no sound or only wind, traffic or crowd noise: `ambient_low` (kept quietly, level 0.15 to 0.35) or `denoise`, `mute` if it is harsh. Real speech in the footage with NO voice added: `keep`, and never cut inside speech: cut only at `silences`. Never cut mid-word. **When a voice is added (`narrate` is `eleven` or `file`), the footage's own sound stays and steps back by itself while the voice speaks.** The owner supplies footage with background music or ambience and no narration, so do not mute it because `has_speech` is true: that guess is fooled by music. Use `keep` for a music bed (level 1.0 is fine, it is ducked under the voice), `ambient_low` (0.15 to 0.25) for plain ambience, and `mute` only if the sound is harsh or is clearly someone talking over the picture (then say so in `copy_options.json` `notes`).
- `audio.music`: pick ONE track from `music_library.json` whose style, title and lyric lines suit the mood (or none when the list is empty). Only listed tracks are allowed. For a long full song start near 20 to 35 percent into it, else 0; you cannot hear it, so say that in `copy_options.json` `notes`. If `own_upload` is not null the owner's own track is used instead: leave `music` as it is. Level 0.3 to 0.45 without a voice, 0.25 to 0.35 with one.
- `text`: at most one short hook line at the start (4 to 8 words, a curiosity or the feeling, not a title) at `top`, ending before the quote starts, plus optional callouts. `quote.start`: when the first quote line appears, after the hook and the intro, in the calmest stretch (ignored when a voice times the lines); `pos` `mid` or `low`, placed clear of faces and of any text already in the picture (the bottom fifth belongs to the app's buttons, never use it).
- `thumb_t`: the cleanest, most inviting second of the reel.

## Finish
Print what you chose (the recommended quote, the arc of the cuts, the music or why none) in a few lines, then stop. Do not approve any gate, publish or spend credits. If you truly need a human decision (a language, which of two moods), write `question.json` as the runner describes and stop instead of guessing.
