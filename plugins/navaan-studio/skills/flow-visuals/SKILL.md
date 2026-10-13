---
name: flow-visuals
description: Create cover art and the visuals for a NAVAAN song in Google Flow within a small credit budget (20 by default). Default is a living scene, a moving wallpaper that shows the song's person, place and nature; an abstract loop and a full story video are the other modes. Use after the song is accepted.
---

# Cover art and Flow clips

Videos are built only from Flow clips. Do not use the default Suno cover unless the user asks.

Three modes, set by `visual.mode` in the profile. The credit cap `visual.flow_credit_budget` (20 by default) holds in every mode and is never exceeded.
- `scene` (default): a living scene, a moving wallpaper. One or two short clips that show what the song is about: a person, a place, nature, a time of day, in slow ambient motion. It is not a plot and it does not follow the song's length shot by shot. The builder loops it to fill the song. Read "The living scene" below.
- `loop`: one or two short abstract clips (light, texture, reflections), looped. Read "The loop look" below.
- `story` (opt in only): a full music video, a shot for each part of the lyrics. It needs hundreds of credits, so use it only when the profile sets `visual.mode` to `story` and a budget that pays for it. Read "The story video" below.

## What Flow TV is, and what it is not

Flow TV is Google's free viewing channel of clips made with Veo. You cannot generate there, but each clip shows the exact prompt that made it. Use it only for look inspiration: browse it, note the visual style and prompt wording the user likes, and write your own prompt for this song. Do not copy a clip's prompt or imitate a specific creator's work. Generation happens in the Flow studio, and it spends credits.

## Budget first

1. Read `navaan.config.json`: `visual.mode` (default scene), `visual.look`, `visual.palette`, `visual.motifs`, `visual.flow_model` (lite, fast or quality), `visual.flow_credit_budget`, `visual.scene_count` (scene and loop modes), plus things to avoid. Run artist-setup if the file is missing.
2. Open Flow, pick the model and read the credit cost Flow shows on the Generate button. Do not trust a remembered number: prices change. As of late 2026, public sources list Veo 3.1 Lite at 10 credits for a 4, 6 or 8 second clip, Fast at 20 and Quality at 100 (about half on Ultra plans). Pass these as a hint only.
3. Work out how many generations fit: `floor(budget / cost shown)`. In story mode the plan also needs the character reference images and a few regenerates, so count them. If that is zero, stop and tell the user the budget is too low for the chosen model, with the cost you saw. Never go over the budget. Each regenerate also counts.
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

## The living scene (visual.mode scene)

The goal: a moving wallpaper that a viewer reads as this song in two seconds, made with one or two clips. Think of a cinematic still that breathes: wind in a scarf, birds crossing a sunset, mist lifting off a lake, leaves moving over a quiet figure. The full video is the song playing over this scene, so the scene sets the feeling and the lyrics carry the story.

Budget rules (they come first):
- Count `floor(visual.flow_credit_budget / credit cost shown on the Generate button)`. At Lite (10 credits) and a budget of 20 that is two clips, and no spare for a regenerate or for reference images. At Fast (20) it is one clip. Do not make reference images, extra angles or test clips: every generation counts.
- Plan the exact number of clips before you open the Generate button, write it in `scenes/plan.md` (model, cost per clip, clips, total, budget) and tell the user. Never go over the budget.
- Use clip 1 for the hero scene. If budget remains, clip 2 is the same place and person in a changed moment (golden hour to dusk, wide to closer, eyes open to looking away), with the same wording for the person and place so they match. The builder cross fades from clip 1 to clip 2 at the start of the second half or at the first chorus (`at`).

How to design the scene from the lyrics:
1. Read `lyrics.txt`, `title.txt`, `style.txt` and `brief.md`. Pick the one moment that carries the song and quote the lyric line behind it in `scenes/prompt.txt`.
2. Choose the elements, each from the lyrics or the song's feeling:
   - Person (optional): one figure, seen from behind, in profile, in silhouette or at a medium distance, in a still or slow pose (standing at a railing, sitting on steps, holding a scarf, looking at the horizon). Describe age, hair and clothing exactly. Keep faces away from close ups to avoid the uncanny look.
   - Place: a specific real feeling place that fits the song's language and culture (a Mithila courtyard or village lane for a Maithili song, a hill station, a river ghat, a rooftop over a city, a garden, a mountain road, a train window). Not a generic backdrop.
   - Nature in motion: birds, sunrise or sunset light, clouds, mist, water, leaves, grass, dust in light.
   - Time of day and palette: from the mood and `visual.palette`.
3. Motion must survive a loop that plays forward then backward. Use gentle ambient motion (swaying, drifting, flowing, flickering, a slow camera push or drift). Avoid actions that look wrong in reverse: walking, driving, pouring, speaking, anything with text or a countdown.
4. Write each clip prompt in these blocks, in this order (adapted from a public Flow tutorial's master prompt, trimmed for a wallpaper with no dialogue):
   1. Scene type: one line, for example "slow cinematic living wallpaper, no cuts".
   2. Subject and appearance: the person described once in fixed words (age, hair, skin tone, clothing, pose). Reuse the same words in clip 2.
   3. Setting and light: place, time of day, weather, palette, one light source named.
   4. Action: only slow ambient motion (wind, birds, mist, water, leaves, a slow breath or head turn). Give the motion a start and an end state that look alike so it loops.
   5. Camera: exactly one primary camera idea, such as a slow push in, a slow lateral drift or a locked frame with parallax. Movement must serve the mood.
   6. Mood: two or three words.
   7. Audio: say "no dialogue, no music, ambient only". The song replaces the audio and the builder drops the clip's sound.
   8. Negatives and continuity: no text, no captions, no logos, no watermark, no lip-sync, no cuts, no fast motion, no crowds, natural anatomy, and for clip 2 the same person, clothing and place as clip 1.
   Scene changes only on a real shift (place, time of day, emotion). The two clips are one such shift, never a timer.
   Image first (optional, saves credits): a still fixes the person, place and light, so the clip is right on the first try and you avoid paid regenerates. If the user has put `songs/<slug>/refs/first_frame.png` (made in any free image tool), use it as the start frame of clip 1 in Flow and describe only the motion in the prompt. Do not make an image in Flow if that costs credits, do not sign in to other tools, and do not wait for a still that is not there: without one, use text to video.
5. Keep the channel varied. Read other songs' `scenes/` folders and `meta.json` and list the person, place and nature already used. Choose a different combination. Clichés (candle, flame, moon, rain on a window, hands) only if the lyrics are literally about them. Profile `visual.motifs` are optional hints, use at most one.
6. Before generating, show the user the scene, the lyric line behind it and the plan in chat. Save the prompt or prompts in `scenes/prompt.txt`.

After generation, write `story.json`: `{"scenes": [{"clip": "c1_<word>.mp4", "at": 0.0}, {"clip": "c2_<word>.mp4", "at": 0.5}]}` (one scene if one clip). Do not set `"story": true`, so the builder boomerangs and cross fades the clips. The cover is a frame taken from clip 1, which costs no credits.

## The loop look (visual.mode loop)

The loop brief is a very modern clip that aligns with the lyrics. Both parts are required, with or without a profile. If `visual.look` is missing, the default look is modern and contemporary, never traditional.

Modern means: current urban or minimal settings and abstract light, such as a rooftop or empty street at night with soft bokeh, glass and reflections, minimal architecture, a long exposure light trail, macro texture, flowing liquid light or smoke, a clean studio with one practical light, a train window at dusk. Treat these as a vocabulary only, and pick what the lyrics call for. Do not use traditional or folk props (diya, clay pots, marigold, temple, incense, rangoli) unless the profile's `visual.look` says so. A palette from the profile or the song's mood still applies.

Old scene files: if `songs/<slug>/scenes/` already holds briefs from an earlier attempt, do not reuse them just because they exist. Check each against these rules and the song's lyrics. Move any that fail into `scenes/_old/` and write new ones before generating.

1. Read this song's own `lyrics.txt`, `title.txt` and `style.txt`. The imagery must come from this song: its title, its strongest lyric lines, its setting and its feeling. Write down the one image or motion that carries it, and quote the lyric line that gave you the idea in `scenes/prompt.txt`.
   - Do not reuse a stock romantic image by habit. A candle, a flame, the moon, rain on a window and hands are clichés unless the lyrics are literally about them.
   - Read every other song's `scenes/` folder and `meta.json` in the songs folder and list the motifs they already used. Pick a different subject and a different setting for this song, so the channel does not look the same from song to song.
   - Profile `visual.motifs` are optional recurring hints, not a checklist. Use at most one, and only if the lyrics support it. The look (palette, camera, light) is what stays consistent across songs, not the subject.
   - Keep it modern: a specific place or object, a slow camera move, shallow depth of field, a controlled palette, soft light, no text, no faces unless the profile allows it.
2. Write the prompt in plain language: subject, motion, camera, light, palette, mood, and what to avoid. Before generating, show the user the subject and the lyric line behind it in chat, and name the motifs you avoided because other songs used them. Save the prompt in `scenes/prompt.txt`. If several clips fit the budget, write one prompt per clip with one consistent look and save each.
3. Scene and loop modes: prefer a seamless loop: ask for a gentle repeating motion that starts and ends in a similar state. The video builder also boomerangs each clip (plays it forward then backward) and cross fades, so even one 8 second clip fills a whole song.

## The story video (visual.mode story)

Opt in only, and only with a budget that pays for it. Direct it like a short film, not a montage of nice pictures. The audience should be able to follow what happens between the people, feel it build through the song, and remember the last image.

### 1. Read the song as a director

Read `lyrics.txt`, `title.txt`, `style.txt` and `brief.md`. Work out the song's sections (intro, verses, chorus, bridge, instrumental, outro) from the lyric markers and the audio length (`ffprobe` on `final.mp3`). If `caption_cues.json` exists use its line times, otherwise estimate each section's start from its share of the lyric lines and say that the timing is an estimate. Note the language and culture of the song (Hindi, Maithili, other) and let it ground the world: a Maithili song belongs in Mithila (courtyards, village lanes, ponds, local architecture, local clothing), a Hindi romantic ballad in real Indian places such as a hill station, a city street, a train, a rooftop, a garden. Avoid generic Bollywood imagery.

### 2. Write the treatment: `scenes/treatment.md`

- One line story: who, what changes, how it ends.
- Emotional arc by section: what the audience should feel in the intro, each verse, the chorus, the climax, the last image.
- Characters: name each lead (usually two, or one) and fix their look in words you will paste into every prompt: age, face and skin tone, hair, build, signature clothing for each part of the timeline. Few characters, always the same. No crowd scenes unless the lyrics need them.
- Locations and time of day: a short list taken from the lyrics and the story (a village lane at dawn, a garden in golden light, a mountain road, a city at night, a rooftop at sunset, a river, birds crossing a sky). Move through them with the song, for example sunrise in the intro and sunset in the final chorus. Show nature and weather where the lyrics call for it.
- Motifs: three to five concrete things that come back (a scarf, a bicycle, a letter, a phone, a bridge) so the video has threads. Quote the lyric line behind each key image. Avoid the clichés the old rule lists (candle, flame, moon, rain on a window, hands) unless the lyrics are literally about them.
- Look: premium Indian indie film, photorealistic live action, natural light, shallow depth of field, subtle film grain, a controlled palette from `visual.palette` or the song's mood. A profile `visual.look` overrides this.
- Channel variety: read other songs' `scenes/treatment.md` and `meta.json` and pick a different story, setting and characters for this song.

### 3. Write the shot list: `scenes/shots.json`

One entry per shot, in song order: `{"id": "c01_door", "at": 0.0, "lyric": "the line it illustrates", "section": "intro", "location": "...", "characters": ["name"], "action": "...", "camera": "...", "light": "...", "prompt": "..."}`.

- Pace to the music. The intro establishes the world with a wide or a landscape. Verses reveal the characters and their situation with medium shots and small intimate moments. The chorus is more open and more emotional: bigger places, movement, the best light. Instrumental breaks carry story or landscape (birds, a road, the city, the sky changing). The strongest image goes to the last chorus or climax. End on one memorable final image.
- Shot length: each Flow clip is 4, 6 or 8 seconds and a shot plays at most as long as its clip. Plan about 4 to 7 seconds per shot, so a 3 minute song needs roughly 30 shots. Slow ballads can use longer shots, fast songs shorter. `at` is the shot's start as a fraction of the song (0 to 1) and the next shot's `at` ends it.
- Reuse to save credits: choruses repeat, so plan one set of chorus shots and reuse the same clips in later choruses with a different `at`. Visual rhyme between choruses is good filmmaking. Keep fresh shots for verses, the bridge and the ending.
- Prompt formula for every shot (Google's own guidance: be specific, not vague): subject and character description, action, composition and shot size, camera movement, environment, lighting and time of day, mood. Describe what happens, not a label. "Two people share a quiet glance, look away, then smile when they think the other isn't watching" beats "romantic scene". "Slow tracking shot behind her as she walks a village lane at dawn, mist, warm rim light, shallow depth of field" beats "cinematic". Paste the fixed character description into each prompt.
- Always add: no text, no captions, no logos, no watermark, no lip-sync, natural restrained expressions, believable anatomy. Do not ask the video model to render lyrics as text, captions are added in editing.
- Keep faces off extreme close ups for long takes. Prefer medium and wide shots, silhouettes, backs of heads, hands on objects and over the shoulder frames for most shots, and use a few close ups where the emotion needs them. These stay consistent and avoid the uncanny look.

### 4. Cost the plan, then ask

Count: shots to generate (after reuse), character reference images, and a spare 10 to 15 percent for failed shots. Multiply by the credit cost Flow shows. Write the plan in `scenes/plan.md`: model, number of fresh clips, reused shots, total credits, budget. Write all three files (`treatment.md`, `shots.json`, `plan.md`) before you spend anything, so the user can read them, and tell the user the one line story and the plan in chat. The credits gate approval authorizes spending up to `visual.flow_credit_budget` and no more.

- If it fits `visual.flow_credit_budget`, go to the credits gate.
- If it does not fit, shrink it in this order: reuse more chorus shots, merge neighbouring shots into longer takes, drop spare shots. Re-cost. Do not drop below one shot per section.
- If it still does not fit, write `needs_you.txt`: `A story video for this song needs about N credits, the budget is B. Raise visual.flow_credit_budget (python3 scripts/setup_profile.py --edit), or set visual.mode to loop.` and stop. Never fall back to a loop silently and never go over the budget.

### 5. Character references first

After the credits gate is approved and the user said yes, make one still image per lead character in Flow (and, if the story needs it, one for the main location), in the chosen look and a neutral light. Save them in `songs/<slug>/refs/` as `name.png`. Check them yourself: the face, age and clothing must match the treatment. Regenerate a reference only within the budget. Use these references as ingredients or frames for every shot that shows the character, so the same person appears throughout, and keep wardrobe changes only where the timeline calls for them.

### 6. Generate the shots

1. Generate shot by shot in song order. Name clips `c01_<word>.mp4`, `c02_<word>.mp4` (zero padded) in `songs/<slug>/clips/`.
2. After the first two shots, stop and check them yourself against the references: same face, same clothes, no warped hands, no text, right mood. If they drift, fix the prompt wording or the reference use before spending more.
3. Record each clip's credits in `meta.json` and keep a running total. Stop at the budget.
4. Save `songs/<slug>/story.json`: `{"story": true, "scenes": [{"clip": "c01_door.mp4", "at": 0.0, "pan": [0.3, 0.5]}, ...]}` in song order, repeating a clip's file name where a shot is reused. Story clips play forward once and are not boomeranged. For the vertical reel, set `pan` per shot to the part of the frame the subject is in (0 left, 1 right).
5. Show the user a few frames or short previews (small files only). If a shot is poor, offer one regenerate only if the budget covers it, and ask first.

## Generate (scene and loop modes)

1. Generate only after the credits gate is approved and the user said yes in chat. Name the results `c1_<word>.mp4`, `c2_<word>.mp4` in `songs/<slug>/clips/`.
2. Record in `meta.json`: model, credits spent per clip, total spent and remaining budget. Show the clip to the user.
3. If the first result is poor, offer one regenerate only if the remaining budget covers it, and ask first.

## Cover art

Take one strong frame from the best clip (in story mode, a frame with the lead character, `cover_flow.jpg`), then make `cover_1x1.png`, `cover_16x9.png` and `thumb_16x9.jpg`. Keep the song title large and legible in the native script. Show previews to the user.

Large files fail the sandbox bridge above about 1.5 MB, so do all file work on the user's computer and only send small previews to chat.
