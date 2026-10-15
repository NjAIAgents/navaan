---
name: motion-regions
description: Mark what should softly move in each picture of a music video (steam, cloth, flames, leaves, water, clouds) and write motion.json. Use for the motion_plan step, after the shot list is approved.
---

# Motion regions

The video is stitched from still pictures. This step decides which parts of each picture get a gentle looping motion, so the film breathes without looking animated. The engine only moves the areas you mark. Everything else stays exactly as painted. This step only writes `motion.json`. Nothing is rendered and nothing is spent.

1. Read `shots.json` (the pictures the video uses) and `prompt_pack.json` if it exists. Each prompt there has a `motion` hint written by the director who planned the picture, for example "steam from the glass". Treat it as a starting point and check it against the real picture.
2. Look at every picture used in `shots.json` (Read renders images). For each one, decide which of these can credibly move, using fractions of the picture: x from 0 (left) to 1 (right), y from 0 (top) to 1 (bottom):
   - `steam`: a cup, pot, chimney or incense. Draw the polygon over the air just above the source, as tall as the wisps should rise.
   - `sway`: cloth, curtains, a dupatta, hanging washing, hair ribbons, banners. The polygon covers the cloth only. It moves most at its lower free end.
   - `flicker`: a flame, a diya, a lamp, a window glow, a screen. Draw tightly around the light and its glow.
   - `foliage`: leaves on a tree or hedge. Inside it only saturated green pixels move.
   - `water`: a river, a puddle, a canal. Flows left to right.
   - `sky`: clouds. Drifts slowly.
3. Rules for good motion:
   - Few and small. One to three regions per picture, and many pictures with none at all. A picture with nothing that would really move gets `"regions": {}`.
   - Never mark a face, a body, a hand, a sign, text, or a building. Cloth worn by a person is fine, the person is not.
   - Polygons have 4 to 8 points and hug the moving thing. A loose polygon smears the background.
   - Match what is there. Do not add steam to a cold street or flames to a dark window.
4. Write `motion.json` as `{"pictures": {"images/pic_01.png": {"regions": {"steam": [[[0.41, 0.62], [0.47, 0.62], [0.47, 0.40], [0.41, 0.40]]]}, "note": "steam from the tea glass"}, ...}}`. The key is the picture's path exactly as in `shots.json`. Each kind holds a list of polygons, each polygon a list of `[x, y]` points.
5. Check your work: run `python3 <plugin>/scripts/motion_clips.py <slug> --preview`. It prints what is marked per picture and writes copies with the areas drawn in `.cache/motion_preview/`. Read a few previews (at least every picture where you marked steam, sway or flicker). If a polygon misses the thing or covers too much, correct `motion.json` and run the preview again. Two rounds at most.
6. Print one line: how many pictures move, how many stay still. Do not approve gates and do not render.

If the user turned motion off in Settings the step is not run at all.
