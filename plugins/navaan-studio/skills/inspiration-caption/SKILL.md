---
name: inspiration-caption
description: Write the Instagram Reel caption for an inspiration short from its quote. Use for the instagram_caption step, and again when the user asks for a rewrite.
---

# Instagram caption for an inspiration short

Write `instagram.txt`. The caption is reviewed and approved by the user, and any edit after approval clears the approval.

1. Read `quote.json`, `originality.json`, `brief.md`. If `caption_feedback.txt` exists, apply exactly what it says, then delete it. The previous draft is in `instagram.prev.txt`.
2. Write the caption:
   - Hook in the first 125 characters, since only those show before "more": the quote itself, or one honest line about what it asks of the viewer. Keep the quote in its own script.
   - Credit line when the quote has an author: `Quote by <author>.` using only the author confirmed in `originality.json`. If the verdict is `clear` and the line is original, no credit line.
   - One short line of context or a question the viewer can answer in the comments. One call to action (save, share with someone who needs it, or comment).
   - At most five hashtags, specific to the theme and language. No `#fyp`, no `#reels`.
   - 100 to 280 characters in total. No AI or tool credit line.
3. Save the file, print the caption, and stop. Do not approve the gate and do not publish.
