---
name: flow-visuals
description: Create cover art and a short, modern visual loop for a NAVAAN song in Google Flow that matches the lyrics, within a credit budget. Use after the song is accepted.
---

# Cover art and Flow clips

Videos are built only from Flow clips. Do not use the default Suno cover unless the user asks.

## What Flow TV is, and what it is not

Flow TV is Google's free viewing channel of clips made with Veo. You cannot generate there, but each clip shows the exact prompt that made it. Use it only for look inspiration: browse it, note the visual style and prompt wording the user likes, and write your own prompt for this song. Do not copy a clip's prompt or imitate a specific creator's work. Generation happens in the Flow studio, and it spends credits.

## Budget first

1. Read `navaan.config.json`: `visual.look` (default modern, cinematic), `visual.palette`, `visual.motifs`, `visual.flow_model` (lite, fast or quality), `visual.flow_credit_budget` (default 10), `visual.scene_count` (default 1), plus things to avoid. Run artist-setup if the file is missing.
2. Open Flow, pick the model and read the credit cost Flow shows on the Generate button. Do not trust a remembered number: prices change. As of late 2026, public sources list Veo 3.1 Lite at 10 credits for a 4, 6 or 8 second clip, Fast at 20 and Quality at 100 (about half on Ultra plans). Pass these as a hint only.
3. Work out how many generations fit: `floor(budget / cost shown)`. If that is zero, stop and tell the user the budget is too low for the chosen model, with the cost you saw. Never go over the budget. Each regenerate also counts.
4. Tell the user the plan in chat: model, cost per clip, number of clips, total credits. The credits gate and an explicit yes in chat are both needed before you press Generate.

## One tab, never a new one

The account is tied to the browser tab and its address. Opening a fresh Flow tab or going back to the Flow home address can land on the default account again and undo the user's switch.

1. At the start, list the open tabs. If a Flow tab is already open, use that tab. Open a new tab only when there is no Flow tab at all, and then only once.
2. Do not navigate that tab to a new address. Reload it in place, and for any link you must follow, keep the exact address the tab has now, including any account index such as `/u/1/` or `authuser=1`, and any project path.
3. After the user switches account, read the account and balance from the same tab. Never close it and never replace it.
4. After the account changes, save the tab's full current address in `songs/<slug>/flow_tab.txt` (address only, no cookies or tokens). A retried run is a new session with its own tab group: it must open exactly that address first, not the Flow home page, and then check which account the page shows. If it shows the old account again, write `needs_you.txt` saying the account keeps resetting and suggesting the user sign out of the old Google account in Chrome or use a Chrome profile that only has the account with credits, then wait as above.

## Account and credits check

Flow uses whichever Google account the browser is signed in with by default. Before any generation:

1. Read the credit balance shown in Flow and the account it belongs to (name or email shown in the account menu). Tell the user in chat which account is active.
2. If the balance is below the cost of one clip, or below what the plan needs, do not generate and do not sign in or out yourself. Write `songs/<slug>/needs_you.txt` with one plain sentence, for example: `Flow account <email> has 4 credits, a Lite clip needs 10. Switch the Google account in Flow (account menu, top right) to one with credits.` The web UI shows this file as a banner. Say the same in chat.
3. Wait inside this same run. This step runs headless: there is no timer and nobody wakes you later, so if you end your turn to wait, the run ends, the orchestrator starts a new session, and Chrome opens a brand new tab group on the default account. That is the bug to avoid. Wait with the Bash tool instead: loop `sleep 30`, then in the same tab reload in place (no new tab, no new address) and re-read the account and balance, for up to 15 minutes (30 loops). Never write "pausing until the timer fires". If the user switched accounts, the tab now shows the new one: keep working in that tab and record its full address, including any account index, in `flow_tab.txt`.
4. When the balance covers the plan, delete `needs_you.txt`, tell the user which account you are now using, and continue. The credits gate and the budget still apply to the new account.
5. If 15 minutes pass with no change, leave `needs_you.txt` in place, record the situation in `meta.json` history and stop. The orchestrator will not retry while the file exists.

## The look

1. Read the lyrics and `style.txt`. Pick the single image or motion that carries the song, such as a diya flame, rain on a window or a moon on water. Keep it modern, not stock footage: slow camera move, shallow depth of field, controlled palette from the profile, soft light, no text, no faces unless the profile allows it.
2. Write the prompt in plain language: subject, motion, camera, light, palette, mood, and what to avoid. Save the prompt in `scenes/prompt.txt`. If several clips fit the budget, write one prompt per clip with one consistent look and save each.
3. Prefer a seamless loop: ask for a gentle repeating motion that starts and ends in a similar state. The video builder also boomerangs each clip (plays it forward then backward) and cross fades, so even one 8 second clip fills a whole song.

## Generate

1. Generate only after the credits gate is approved and the user said yes in chat. Name the results `c1_<word>.mp4`, `c2_<word>.mp4` in `songs/<slug>/clips/`.
2. Record in `meta.json`: model, credits spent per clip, total spent and remaining budget. Show the clip to the user.
3. If the first result is poor, offer one regenerate only if the remaining budget covers it, and ask first.

## Cover art

Take one strong frame from the best clip (`cover_flow.jpg`), then make `cover_1x1.png`, `cover_16x9.png` and `thumb_16x9.jpg`. Keep the song title large and legible in the native script. Show previews to the user.

Large files fail the sandbox bridge above about 1.5 MB, so do all file work on the user's computer and only send small previews to chat.
