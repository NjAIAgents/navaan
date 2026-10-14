---
name: inspiration-visual
description: Create or select the vertical background image for an inspiration short and save it as background.jpg. Use for the background step. Spends Flow credits only when the brief says background generate.
---

# Inspiration background

The renderer animates a still image (slow camera move, typography, transitions), so this step produces one strong 9:16 picture and nothing else. No video clips.

1. Read `quote.json` (meaning and mood), `brief.md` options (`background:`), `navaan.config.json` (palette and motifs, if the profile has them) and `style-notes.md` if present. If `visual_feedback.txt` exists, apply it, then delete it.
2. Choose by the `background:` option:
   - `generate` (default) when the step says the picture is made by OpenAI: write only the prompt to `scenes/background.txt` (rules in item 3), print one line and stop. The portal makes the picture with the OpenAI image API after the credits gate.
   - `generate` (default), Flow: make one image. Use the flow-visuals skill for the browser mechanics (Claude in Chrome, the user's open Flow tab, the Image mode, aspect ratio 9:16). Credits are approved at the `credits` gate before this step runs; generate once, and a second time only if the first is unusable.
   - `library`: pick the best match from `<storage.local_dir>/backgrounds/`. Copy it, do not move it.
   - a file path: copy that file.
3. Prompt rules for a generated image: cinematic, one clear subject or place, soft depth, a calmer area in the middle third where the text will sit, no text, no logos, no watermarks, no recognisable real people, no copyrighted characters. Write the prompt to `scenes/background.txt`. For OpenAI also: say it in plain full sentences, portrait 2:3 frame, keep the subject and any light source in the middle, leave the sky or a calm area for the text, soft and photographic, muted palette, nothing busy.
4. Save the result as `background.jpg` (or `.png`), at least 1080 by 1920, portrait. Crop or scale with ffmpeg if the picture comes out another shape; never stretch it.
5. Print what you made in one line and stop. Do not approve gates and do not spend credits beyond the approval.
