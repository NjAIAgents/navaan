---
name: inspiration-qa
description: Look at a rendered inspiration or Aha-lorithm short (stills of the video and the automatic check results) and judge whether a viewer would notice a fault, then save qa.json for the person approving the video. Use for the qa step. Advises only; never edits the video, the plan or a gate.
author: Navjyot Nishant
---

# Inspiration and Aha-lorithm video QA

You judge `final_reel_9x16.mp4` before it is approved at the `media` gate. The automatic checks (`qa_checks.json`: file, black frames, sound, caption sync) have already passed, or this step would not run. What they cannot see is the look, which is your job. You advise; you never change `timing.json`, `quote.json`, the pictures or the video, and you never approve or publish anything.

## Look
1. Read `quote.json`, `timing.json` (the lines with their start times, `scenes` when each beat has its own picture, `visuals` for the caption look), `render_report.json` and `qa_checks.json`.
2. Take about 12 stills into `.cache/qa/` (create it), scaled small:
   `ffmpeg -y -v error -ss <t> -i final_reel_9x16.mp4 -frames:v 1 -vf scale=540:-2 .cache/qa/q_<t>.jpg`
   at 0.5 s, then 0.4 s after the start of every line (so each line is on screen with its words showing), 0.3 s on each side of a picture change when `scenes` exists, and 0.5 s before the end. Read every still.

## Rubric (pass or fix for each, with the time it concerns)
- **Doubled or stacked lines:** are two lines of the quote on screen at once, one drawn over the other, or does the same sentence show twice? This is the fault that matters most.
- **Words:** is every line fully readable (size, contrast against the picture), spelled as in `quote.json`, inside the frame, and clear of the bottom fifth where the phone's controls sit?
- **Text over a subject:** does a caption cover a face or the main subject of the picture for most of its time?
- **Pictures and lines:** with `scenes`, does each picture fit what its line says, and is the picture change on a line, not in the middle of one? Without `scenes`, is the one picture fitting the mood?
- **Look:** exposure and colour natural, no heavy banding or visible artifacts, the pictures of one short sharing one look, nothing that reads as a mistake (a garbled letter shape, a stray logo, a distorted hand or face).
- **End:** the last still shows the handle clearly and no quote line is still on screen.
- **Pace:** a stretch that looks dead or repeated.

`fix` only for a problem a viewer would notice and a person would want changed; taste is `pass` with a note.

## Write qa.json
`{"verdict": "pass|fix", "source": "look", "summary": "two plain sentences", "checks": [{"name": "stacked lines", "ok": true, "at": 12.4, "note": "..."}], "fixes": ["one concrete change per line in plain words, naming what would do it: a different caption look (the brief's `- look:` option), time the narration again, render again, or new pictures (which costs money)"], "notify": "one plain sentence for a chat message: the item, pass or what to fix", "at": "<UTC time>"}`
Print the verdict and the fixes, then stop. Do not approve the gate and do not publish.
