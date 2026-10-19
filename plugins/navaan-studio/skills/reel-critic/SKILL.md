---
name: reel-critic
description: Look at a rendered reel (stills and sound facts) and judge it against its plan and a short rubric, then save critique.json for the person approving the final cut. Use for the critique step of a reel item. Advises only; never edits the plan.
author: Navjyot Nishant
---

# Reel critic

You judge `final_reel_9x16.mp4` before a person approves it at the `media` gate. You advise; you never change `edl.json`, `quote.json` or the video. If something is wrong the person presses Request changes with your note, and the earlier steps run again.

## Look
1. Read `edl.json`, `quote.json`, `render_report.json`, `audio.json`, `copy_options.json`.
2. Take stills of the render into `.cache/critique/` (create it), at 0.4 s, 1.5 s, the start of each quote line, the middle, and 0.5 s before the end:
   `ffmpeg -y -v error -ss <t> -i final_reel_9x16.mp4 -frames:v 1 -vf scale=540:-2 .cache/critique/c_<t>.jpg`
   Then Read every still.
3. Sound: `ffmpeg -i final_reel_9x16.mp4 -vn -af volumedetect -f null -` and read the mean and peak volume.

## Rubric (each is pass or fix, with the time it concerns)
- Hook: is the first second visually strong and is the hook text (if any) readable at once?
- Words: is every quote line fully readable (size, contrast against the footage), spelled as in `quote.json`, inside the frame, clear of the bottom fifth?
- Framing: is the subject cut off or off-centre at any still? Is a zoom too strong or a crop wrong?
- Pace: any stretch that looks dead or repeated; does the length suit the content (15 to 45 s)?
- Look: exposure and colour natural, no heavy banding, the grade not overdone.
- Sound: mean volume between about -24 and -12 dB, no clipping (peak under -1 dB), music not louder than the voice, ambient noise not distracting.

## Write critique.json
`{"verdict": "pass|fix", "summary": "two plain sentences", "checks": [{"name": "hook", "ok": true, "at": 0.4, "note": "..."}], "fixes": ["one concrete change per line, in plain words, naming the step that would make it: edit plan (direct step), quote, or render"], "checked_at": "ISO time"}`
`fix` only for real problems a viewer would notice; taste is `pass` with a note. Print the verdict and the fixes, then stop. Do not approve the gate and do not publish.
