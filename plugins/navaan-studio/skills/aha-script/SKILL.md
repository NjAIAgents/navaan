---
name: aha-script
description: Write the narrated script of an Aha-lorithm short (hook, explanation, the aha) as beats, each with its spoken line, its short on-screen caption and one picture prompt, saved as quote.json plus title.txt. Use for the script step of the aha pipeline.
---

# Aha-lorithm script

Content type `aha` is a 20 to 25 second vertical YouTube Short for The Aha-lorithm (@TheAhalorithm): AI explained in seconds. One misconception, one clear explanation, one memorable insight. ElevenLabs reads the spoken lines from the first frame (a calm, natural narrator, about 120 to 130 words a minute), each beat has its own picture, and the renderer draws the beat's caption in the safe area. Quiet ambient music sits far under the voice, drops back while the aha line lands, and the end card shows "The Aha-lorithm · AI explained in seconds".

1. Read `brief.md` and `navaan.config.json`. If `quote_feedback.txt` exists, apply exactly what it says, then delete it. The brief starts the short in one of three ways:
   - **The owner's own narration** (a hook and/or the spoken text): keep their words exactly. Only split them into beats, write the captions and the picture prompts. Fix nothing but typos.
   - **An idea or a topic**: write the script from it.
   - **Nothing** (empty idea): pick a topic yourself, an AI misconception or habit most people get wrong, useful today. Read `title.txt` of the other `aha-*` items first and do not repeat a topic.
2. Beats, one spoken sentence each (6 to 9 beats, 45 to 60 words in all, so it lands inside 25 seconds):
   - **Hook** (beat 1, 0 to 3 s): 4 to 9 words that stop the scroll. A surprising claim. Never a greeting, never "In this video".
   - **Explanation** (the middle beats): why it is true, in plain words a 15-year-old follows. One idea per beat.
   - **The aha** (one beat near the end): the takeaway in 4 to 8 words the viewer will repeat. Then at most one beat on what to do.
   Write for the ear: short words, no lists, no parentheses, no abbreviations the voice would spell out.
3. Captions: for each beat a SHORT on-screen caption, 2 to 6 words, that sharpens the spoken line rather than repeating it in full (spoken "That's what makes it dangerous." → caption `Confident *≠ correct*`). Mark the important phrase with asterisks; it is drawn in muted gold, the rest in white. Use marks on at most 4 beats in the whole short, always on the aha.
4. Facts: say only what you can back with a reliable source; the next step checks every claim on the web. No invented numbers, studies or quotes. An example of an AI mistake must be clearly illustrative ("it might say..."), never a claim that a named product said it.
5. Pictures: one prompt per beat that is shown by a picture (see step 7: a beat shown by a scene treatment gets an empty prompt `""`, and nothing is spent on it), 20 to 80 words: a cinematic, mostly abstract image of the beat's idea (a gold neural network forming in darkness, a crystal ball with a fine crack, one bright path among many, a magnifying glass over a source document). One look across the beats: near-black backgrounds, luminous gold with small touches of cool blue. People only in silhouette or from behind; no real or famous person, no brand logo. Never ask for words, letters, numbers or readable screens: the renderer adds the text. Keep the middle of the frame calm enough for a caption.
6. Write `quote.json`:
   `{"text": "the spoken lines joined with spaces", "lines": ["spoken line of beat 1", "..."], "captions": ["caption of beat 1 with *marks*", "..."], "pictures": ["prompt for beat 1", "..."], "aha": <index of the aha beat, from 0>, "author": "", "kind": "original", "language": "en", "sources": ["URLs that back the facts"], "notes": "one line on the angle"}`
   `lines`, `captions` and `pictures` have the same length. `lines` carry no asterisks.
7. Visual plan, `visual_plan.json` (optional, but use it when a beat is better shown than pictured). Beat 1 always keeps its picture (the hook is drawn over it; it is also the thumbnail). Any other beat may be shown by one scene treatment instead of a picture; the aha beat keeps its glow either way. Pick the treatment that makes that beat's idea visible, and use few of them (usually 2 to 4 beats, never all), so the short has rhythm:
   - `hook` (beat 1 only): the words come in one by one over the picture. `data` is empty. Mark words with `*asterisks*` in the caption.
   - `compare`: two things side by side. `{"left": {"title": "Confidence", "text": "How it sounds"}, "right": {"title": "Evidence", "text": "Why it holds"}, "sign": "≠"}` (titles up to 18 characters, texts up to 24)
   - `chat`: a question and an answer typed out. `{"question": "...", "answer": "...", "tags": ["sounds sure", "verified?"]}` (question 40, answer 110 characters, at most 2 tags). Clearly illustrative, never what a named product said.
   - `flow`: a chain of steps. `{"nodes": ["Your question", "Patterns it has seen", "A plausible answer", "Your check"]}` (2 to 5, 28 characters each; the last one is the point)
   - `checklist`: `{"items": ["Check the source", "Check the date"]}` (1 to 5, 28 characters)
   - `timeline`: `{"steps": [{"head": "Ask", "sub": "You pose the question"}, ...]}` (2 to 5; head 14, sub 34 characters)
   - `strike`: a word crossed out, the better one underlined. `{"wrong": "Confidence", "right": "Evidence", "rest": "is what makes it true."}` (wrong 10, right 9 characters)
   - `bars`: an illustration of more and less, never a measurement: `{"rows": [{"label": "Feels certain", "fill": 0.9}, {"label": "Checked", "fill": 0.3}]}` (2 to 4 rows, fill 0 to 1, no numbers in the labels)
   - Figures: `stat` `{"value": 87, "unit": "%", "label": "...", "source": "https://..."}`, `ring` `{"value": 87, "label": "...", "source": "..."}` and `chart` `{"series": [{"label": "...", "points": [0.2, 0.4, 0.9]}], "xlabels": [...], "source": "..."}` need a real `source` URL you have read that states the number. No source, no figure: use a different treatment or a picture. Never `sample`: that label is for previews and a real short refuses it.
   Format: `{"beats": [{"line": 1, "treatment": "compare", "data": {...}}, ...]}` where `line` counts from 0 and each line has at most one treatment. The same beat's `lines` entry stays the spoken sentence and `captions` entry is the title drawn above the scene (keep it under about 44 characters so it fits in two lines). Run `python3 <plugin>/scripts/visuals_plan.py <slug>` and fix every problem it prints before you finish: approving the script approves this plan with it, and a plan that fails is refused.
8. Write `title.txt`: the hook as a title, 60 characters at most, no hashtags.
9. Print the beats (spoken line, caption, and the treatment if it has one) in your final message, then stop. Do not approve any gate. The owner reads and edits the script at the `quote` gate.
