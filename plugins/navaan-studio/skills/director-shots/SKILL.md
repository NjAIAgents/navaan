---
name: director-shots
description: Write the director's shot list (shots.json) for a music video made from the user's own pictures. One shot per lyric section, each with a picture, camera move and scene note, timed to the song. Use for the shots step.
---

# Director's shot list

The video is stitched locally from the user's pictures in `images/` with slow camera moves and cross fades. No Flow, no credits. This step only writes `shots.json`. The user then reads it in the portal, edits it if they want, and approves it before anything renders.

1. Run `python3 <plugin>/scripts/shots_prep.py <slug> --draft`. It writes `shots_context.json` (sections with estimated times, song length, the pictures, the user's camera and scene overrides) and a first `shots.json`.
2. Read `shots_context.json`, `lyrics.txt`, `style.txt` and `title.txt`. Look at every picture in `images/` (Read renders images).
3. Improve `shots.json` as a director would:
   - One shot per lyric section as the base. Long sections (over about 22 s) split into two or three shots so the picture changes. Keep every shot at least 6 s.
   - Match picture to meaning: the line's mood, place and light decide which picture fits. Use every picture at least once when there are enough shots. Reuse a picture for a returning chorus.
   - Camera for each shot: `push_in` (closeness, confession, rising feeling), `pull_out` (release, distance, ending), `pan_left` or `pan_right` (travel, memory), `tilt_up` (hope), `tilt_down` (weight, sorrow), `drift` (ambient, calm), `hold` (a still beat). Do not use the same move twice in a row. Close on `pull_out` or `drift`.
   - `focus` is `[x, y]` as fractions of the picture (0 to 1) that a push or pull aims at, for example a face or a window. Default `[0.5, 0.5]`.
   - `scene`: one plain sentence saying what the viewer should feel or notice in this shot. `lyric`: the first line or two of the section, so the user can recognise it.
   - If the context has a `plan`, the camera operator already chose a move and focus for each picture. Keep them unless looking at the picture shows a better move, and never repeat one move twice in a row.
   - If `camera_override` or `scene_override` in the context is not empty, it is the user's instruction for the whole video. Follow it over your own taste.
4. Timing: `start` and `end` in seconds, the first shot starts at 0, each shot ends where the next begins, the last ends at the song duration. If `timing_source` says estimated, say so in `notes`, because the user may need to nudge the times.
5. Layout `static` has no shot list. If `visuals.json` says static, write nothing and say so.
6. Write `shots.json` as `{"duration": ..., "shots": [{"id", "label", "start", "end", "image", "camera", "focus", "scene", "lyric"}], "notes": "..."}` and print one line: how many shots, which pictures, anything uncertain. Do not approve gates and do not render.

   Standing rules: if `<local_dir>/standing_rules.json` exists (next to the songs folder, written when the user presses Implement on a recommendation), apply every rule for this account whose category is format, hook or packaging, and say which ones you applied.

   Send line: if `<local_dir>/standing_rules.json` has a rule for this account in the category engagement that asks for a reason to send the video ("send this to someone who..."), also write `send_line.txt` in the item's folder: ONE short line, under 70 characters, that names who this song is for, in the language of the lyrics (for example "Send this to someone far from home"). The renderer draws it on the last seconds of the video. If there is no such rule, do not write the file.
