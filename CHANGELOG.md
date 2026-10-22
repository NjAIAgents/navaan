# Changelog

All notable changes to NAVAAN Studio are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/) (0.y.z until the public listener app exists).
The version lives in `plugins/navaan-studio/.claude-plugin/plugin.json` and is mirrored in `.claude-plugin/marketplace.json` and `plugins/navaan-studio/web/package.json`; a test keeps them and this file in step.
Release steps are in `deploy/README.md` (Releasing). Only changes a person using or running the studio would notice are listed; refactors, tests and docs-only edits are in the git history.

## [Unreleased]

### Fixed
- Settings, AI services, Pictures: with Muse as the picture maker, OpenAI's Model and Quality boxes are hidden (Muse ignores them), instead of listing gpt-image models that do nothing.

## [0.58.3] - 2026-10-22

### Fixed
- The captions and the voice stay in step on a slow narration with long pauses or a hum between lines (NAV-146). On insp-008 and insp-009 a line could light 1.5 to 4.7 s away from where it is spoken, and the last words of a line up to 8 s late, because the lines were cut by letter count and each line's words were spread over its whole slot. A small offline recogniser (Vosk) now hears every word with its own start and end, and its words are matched to your script, so a line starts where its first word is spoken and each word lights up when it is said. It needs a one-time install of the word timing tools (about 40 MB, English only): run `setup_captions.py --vosk --yes`, or approve the captions setup, which now includes it. Without them, or when fewer than half of your words are heard right, the narration is timed exactly as before and the step's log says so. Hindi narrations are timed as before (not tested with the recogniser).

## [0.58.2] - 2026-10-22

### Fixed
- A correct dev.to key was refused with "HTTP 403" when saved in Settings. dev.to rejects the check request before it reads the key unless it names who is asking; the check now does, as the Post buttons already did. The same applies to every key check.
- Settings, AI services, Pictures: the choices now read in words. "Made by: openai" next to "Picture maker: muse" looked like a contradiction; it now reads "Automatic (an image API, chosen below)" and "Muse (Meta, $0.01 a picture)". With Muse chosen, a note says the Model and Quality boxes are not used.

## [0.58.1] - 2026-10-22

### Fixed
- Muse as the picture maker now works for a blog post's pictures too. The blog image step still asked for an OpenAI key and would have sent it to Muse. It now uses the key of the maker chosen in Settings and names it in its message.
- The Muse key box and the Picture maker choice were only on the classic Settings page. The new app's Settings, AI services now has both.

## [0.58.0] - 2026-10-22

### Added
- A second output for an inspiration short: a picture for each thought instead of one background (NAV-145). Tick "A picture for each thought, not one background" on the new-item form (it needs the narration and is off with a scene video). Claude groups the script's lines into a few beats, always fewer than lines, and plans one scene for each, with one look for the whole short and no cost; you approve how many pictures and the price before any picture is made. In the video the picture changes where the voice moves on to the next beat, with a slow push in or out and a dissolve through dark, and the closing line keeps the last picture. The short without the tick is made exactly as before.
- Meta Muse Image as an alternative to OpenAI for automatic pictures. Settings, Pictures and voice has a new "Picture maker" (OpenAI stays the default) and a Muse key row. Muse costs a flat $0.01 a picture, has no quality setting, and works for the inspiration background, the song pictures, the same-faces edits and the vertical recompose. The Muse key is saved without a live check, so a wrong one shows on the first picture.

## [0.57.0] - 2026-10-20

### Added
- Blog posts are finished and posted from the Posts tab (NAV-74, NAV-138, NAV-139, NAV-78).
  - **Humanizer:** after the edit, a step rewrites both drafts so they read like a person wrote them (plainer words, a varied rhythm, no stock phrases). A check then compares the rewrite with the copy it started from: every claim marker, number, link, code block, image and the dev.to front matter must be unchanged, or the run stops and names what moved. The fact check does not run again.
  - **Editor:** each destination's post is shown on a white page you can edit with a toolbar, preview as readers will see it, and save back to its file. The dev.to title, description and tags are fields above the page. The copy buttons copy what you saved.
  - **Images:** a step plans a cover and two to four images around the post's idea, at no cost. The cover (dev.to and LinkedIn sizes) and the figures (a flow, a comparison, a checklist, a timeline, a chart ...) are drawn with Remotion, free, with the post's own words. Only a picture the plan asks for is made with OpenAI, and it waits for your approval with its price. The images are stored in the bucket at permanent public addresses and put into both posts; the cover goes into the dev.to front matter.
  - **Post buttons:** with your dev.to key and LinkedIn token saved in Settings, the Posts tab saves the article on dev.to as a draft and publishes it when you confirm, and posts a short LinkedIn post (written by a new step) with the dev.to article as a link card. LinkedIn has no way to post a long article from outside, so the LinkedIn article stays copy and paste.

## [0.56.5] - 2026-10-20

### Fixed
- A narrated inspiration short no longer prints its lines on top of each other (seen on insp-008). With the "rise" and "hero" caption looks every line after the first landed in the same spot and the earlier lines stayed on screen, so a script of four or five lines became unreadable and the last one of "hero" ran off the bottom. Now one line shows at a time and fades out before the next one appears, as "karaoke" already did. A short that is already made keeps its overlap until it is rendered again from its page.

## [0.56.4] - 2026-10-20

### Changed
- A song no longer gets a poster as a step of its pipeline (NAV-144). The poster was a second picture per song, made with OpenAI before the credits approval, and it only changed the picture in a shared link's preview; the cover now serves there. The credits approval no longer lists it. The Poster card on the Media tab is still there for a song you want one for, and a song that already has a poster keeps showing it in link previews.

## [0.56.3] - 2026-10-20

### Fixed
- The free public site no longer fails with "Request failed (429)" or shows only a letter instead of a cover to a visitor without a session (NAV-143). The server's throttle for visitors without a session was meant for the studio login and counted a normal library page as too many requests; the public site now has its own, much higher limit. The studio hosts keep the strict one.
- A song's new cover now shows in the library and on the public site (NAV-142). The pictures were cached for a year at an address that never changed, so a browser that had the old cover kept showing it. The address now carries the cover's version, so a replaced cover is fetched once. Until you update, a hard reload shows it.

## [0.56.2] - 2026-10-20

### Fixed
- Switching on the standing licence statement in Settings now confirms the songs you have already published, straight away (NAV-141). Before, only a later sync did, so songs published earlier stayed hidden from the public site. The card says which songs were confirmed. A song you marked not allowed, and a draft, are never changed.

## [0.56.1] - 2026-10-20

### Fixed
- The standing licence statement (Settings) is kept across restarts (NAV-140). It was stored where nothing saved it to Vault, so every deploy switched it off and newly published songs stayed hidden from navaan.online as unconfirmed. After this release, switch the statement on once more in Settings.

## [0.56.0] - 2026-10-20

### Added
- A song's cover is made as a step of the pipeline, before the video, in the same modern look as the album cover (one strong graphic subject, flat colour fields, the title and artist drawn by us). It becomes the song's cover: in the mp3, the YouTube thumbnail, Instagram and, once the song is in the bucket, on the site. The step is listed on the credits approval with its price (about 4 cents). A song whose videos were already approved is not sent back to make one.
- Share an album. A published album has a Share button for listeners and a Share card in Studio: the link opens a public page with the album's cover, "Album by NAVAAN", and every song in it that may be heard, each with its own player, free and without a sign in. The preview in chats says "an album by NAVAAN". The link stops working if you stop sharing it or unpublish the album. A song whose licence is not confirmed is not on the page, as everywhere else on the public site, and an album with no such song cannot be shared yet.
- An album's page, in Studio and for listeners, says who it is by (NAVAAN) under the title.
- A Cover card on a song's page (Media tab): the prompt it was made from, which you can change, "Make a new cover" with the cost on the button, "Redraw the title" (free), or "Use my own picture". A new cover replaces the old one everywhere, including the bucket. If the cover is not on the site, the card says so and offers "Save for the site". The mp3's embedded picture follows the next time the video step runs.

### Changed
- A song now goes to NAVAAN first. "Publish to NAVAAN" (the cloud archive, which puts the song on the site) comes right after you approve the video, before the YouTube and Instagram steps, and it no longer waits for Instagram. Before, it was the last step and waited for both YouTube and Instagram, so a song you chose not to post to Instagram never reached NAVAAN. YouTube and Instagram wait for your approval of this step, and clean up is still last. A song already in progress follows the new order from its next step.

### Fixed
- A blog post started from a keyword no longer fails its first step with "No keyword yet". The keyword you typed was written below the template's own empty Idea section, so the pipeline read the empty one. It now goes in the Idea section itself. A blog already started this way works on retry too: the pipeline now reads the first Idea section that has a keyword in it, not only the first section.

## [0.55.1] - 2026-10-20

### Fixed
- The last step of an Aha-lorithm short, "Clean up the local copy", no longer fails with "Instagram is set up but the Reel is not posted yet" (NAV-137). The Aha-lorithm is YouTube-only, and the same waiting is skipped for any item whose Instagram you chose to skip. Music, inspiration and reel items still wait for their Instagram post.

## [0.55.0] - 2026-10-20

### Added
- Aha-lorithm: change the script at its approval (NAV-133). "Edit the words" shows each beat's spoken line and caption as fields; saving keeps the beats, pictures and visual plan and asks for a fresh approval. "Use my own words" takes your script exactly as you write it and has Claude split it into beats and make the captions, picture prompts and visual plan (one Claude call). "Request changes" now really sends your note back and makes the script again; before, the note was only written to the history.
- Blog: the finished post has a Posts tab with one tab per place it goes (NAV-134): dev.to, LinkedIn article, and LinkedIn post once that exists. Each shows the post as it will look and copies it in the format that place takes: markdown with its front matter for dev.to, rich text (headings, bold, lists and links stay) or plain text for LinkedIn, plus the title and tags on their own. The claim markers used by the fact check are removed from everything you copy. If the browser refuses to copy, the text is shown selected.

### Changed
- Song and album covers look modern (NAV-135): the art direction asks for one strong graphic subject or abstract form, flat or soft-gradient colour with fine grain, a limited palette and generous negative space, not painterly or cinematic. The lettering is a clean sans (Inter, installed in the image), set low left with a short gold bar, a lighter shade and a small tracked artist name. Albums get a new "Modern sans" lettering, now the default; the display fonts stay as choices. Existing covers are untouched.
- Aha-lorithm pictures follow their topic (NAV-136): every short gets its own art direction (medium, palette, mood) and every beat a concrete scene from its own sentence, no two alike. The fixed dark-and-gold template that made every picture look the same is gone.

## [0.54.0] - 2026-10-19

### Added
- Shorts drawn the way each one needs (NAV-130, NAV-129, NAV-131, NAV-132). The Aha-lorithm's script can now plan some beats as a scene instead of a picture: a chat that types out, a comparison, a checklist that ticks, a timeline, a counting number, a line chart, a progress ring, a crossed-out word, and a hook whose words come in one by one. A beat shown this way needs no generated picture, so it costs nothing. A number on screen needs a source that is checked, and the plan is approved together with the script, shown in plain words on its approval card. A narrated inspiration stays simple: one calm caption look for the whole short, chosen from its words (the spoken word lights up, words rise out of the dark, or the key words grow), or named with `- look:` in its brief (`plain` keeps the old captions). Each word now appears when the voice says it, and the glow breathes with the voice. A plan that cannot be drawn never stops a short: it is made with its pictures and plain captions instead.

## [0.53.0] - 2026-10-19

### Added
- An album's own cover now shows on the album's tile and page, in Browse, Albums and the listener's album page, instead of its first song's cover (an album without a made cover keeps showing its first song's). A cover you make or load in Studio is saved for the site as it is made, and a listener sees it once the album is published; until then only you see it. If saving it fails, the Cover card says so and offers "Save for the site" (free).

## [0.52.0] - 2026-10-19

### Added
- Inspiration: give a short a scene video of your own (NAV-126). Add it next to the Suno link when you create the short, or on its Content tab before it is rendered. No background picture is made (and nothing is spent on one): your video plays behind the lyric captions with the Suno song's sound, and the credit page still ends the short. If the video is shorter than the song, a small gap holds its last frame; a big gap slows it down (at most 1.5 times) and then holds the last frame. You can remove the scene video before rendering and the background steps come back. Without a scene video, nothing changes.

## [0.51.0] - 2026-10-19

### Added
- Reels, from the first real test (NAV-125): your footage's own sound (its background music or ambience) stays under the ElevenLabs voice and steps back while the voice speaks; give it footage with no narration. When your footage already shows the quote burned in, the quote is spoken but not drawn a second time. A plan can add an intro (the first frame held, with a hook line) and an end card (the last frame held and dimmed, with the account handle and the music credit), which turns a short clip into a complete reel; a voice longer than the footage holds the last frame until it finishes.
- Fixed: with a voiceover, music (or the footage's sound) used to stop when the voice stopped; it now plays to the end of the reel.

## [0.50.0] - 2026-10-19

### Added
- Reels: upload your own video and get an Instagram-ready 9:16 reel. The upload is shrunk to a small working copy and the big original is deleted once the copy is checked. Claude reads the scenes, suggests a quote that fits them (the footage can have no speech at all) and plans the cuts, framing, look, sound and music; you approve the words and the plan before anything is made. The reel can be narrated with ElevenLabs, with a voice you record or make on Suno, or have no voice at all. Music comes only from NAVAAN's own published songs or your own upload. A review of the finished reel sits beside the final-cut approval, and the reel posts to Instagram.

## [0.49.0] - 2026-10-19

### Added
- Studio › Blog, the first part of the blog pipeline (NAV-69, NAV-71). Start a blog post from a keyword, field or area. The pipeline reads what is trending in Hacker News, dev.to and Google Trends, with no keys needed. When Google refuses its rising searches, the day's trending searches are used instead. Claude then searches the web and suggests 5 timely topics, each with why it matters now, an angle and its sources. You pick one, and can reword its title and angle first.
- Blog research and drafts (NAV-72, NAV-73):
  - The picked topic is researched from primary sources into a list of claims, each with its source and quoted evidence, then outlined.
  - Claude writes the dev.to post and a LinkedIn article adapted from it, stating only the listed claims.
  - Every statement is fact-checked against its source. Failing claims go back to the writer twice at most; after that the run stops and names them for you.
  - A reviewer notes what to improve without changing anything, and an editor applies the notes without changing any fact.
  - Your voice, images and publishing to dev.to and LinkedIn come in the next releases.

## [0.48.0] - 2026-10-18

### Added
- Settings › AI services › Spending limits: the most one run may spend on pictures, the pictures planned per song, and the ElevenLabs narration allowed per month can be changed from the new app. Before, only the classic page could change them (NAV-29).
- The song page warns about what no step can fix: the item's own account is not set up (with a link to Settings), there is no artist profile, or YouTube refused the custom thumbnail (with the command that sets it).
- The song's Approvals list shows every approval, and you can give one ahead of its step. Publishing and spending approvals ask first.
- Studio › Analytics has the classic page's analysis back (NAV-29):
  - who the audience is: Instagram cities, countries, age and gender, and the hours followers are online; YouTube traffic sources, viewer countries, age and gender
  - retention curves for your top videos
  - "What seems to work": average views by language, genre, and Shorts against videos, and the share watched
  - the posts and videos tables carry every classic column (likes, comments, average watch, save rate; watch minutes, share viewed, subscribers gained per 1,000 views), sort by any column, and have a views-over-time line per row; YouTube can show videos or Shorts only, and private videos say so
  - every collector run is listed, with what it brought in
  - recommendations show Claude's market sources and whether each one came from Claude or the rules, sort the surest first, report what changed after one was marked done, and show the last Claude run's error if it did not finish
  - a slot in Best time to publish opens the scheduler with that time filled in
  - an empty page says how to start, and YouTube says when only public counts are shown
- A song's page shows how each post and video is doing, as the classic Performance tab did: its rank against the account's other posts and its multiple of their median, the numbers as tiles, views over time, YouTube retention, what the analysis says about it, and the comments waiting for a reply. Posts and videos can be unlinked, and a YouTube video can be linked from the song too.
- The Media tab shows where the song is published (YouTube thumbnails with their privacy and a link into YouTube Studio when private, the Instagram Reel embedded), its files in the cloud archive with one-hour previews, the cover and thumbnail stills, and its pictures. "Make 9:16" and "Try the first 2 pictures" work after the look is chosen too.
- The Songs, Inspiration and Aha-lorithm lists can be searched, filtered to published or in the cloud, grouped by album or status, and shown as a grid. Each row shows its progress, where its files are (local only, in the cloud, bucket out of date, local copy cleaned), a refused YouTube thumbnail, and its views on Instagram and YouTube.
- Approvals lists items whose YouTube thumbnail was refused, and the Studio tile counts them.
- The home dashboard shows how many items are published (and on Instagram), how many are in the cloud (checked, and cleaned here), a bar by stage, and the latest covers.
- Cloud shows the archived count, the objects, the total size and how many are out of date, and the bucket's folder.
- Settings: each YouTube sign-in can also be done from a terminal by pasting the token file, and step-by-step guides cover the Instagram token, the Facebook token for peer data and the first YouTube setup.
- The Text tab edits every text file of an item, not only the usual ones. The account menu shows whether the studio runs on the server and whether the scheduler and the worker are up.

### Changed
- New Aha-lorithm shorts are narrated at the "Calm" pace, a little slower than normal. A short already made keeps its pace; change it on its Narration card and narrate it again.
- "Waiting for you" says plainly whether it needs an account switch or something done on the Mac, without sending you to the classic view. A failed step's "Show the full log" opens the step's log in the new app.
- Aha-lorithm YouTube descriptions are short: the hook line, the follow line, and the hashtags.

### Fixed
- Uploads no longer add "Hear the full song free" to items that are not songs. Aha-lorithm shorts get no NAVAAN line (their own channel); inspiration shorts get "More from NAVAAN: https://navaan.online".

## [0.47.3] - 2026-10-18

### Fixed
- A new channel's sign-ins (The Aha-lorithm's YouTube login) never reached the publishing worker or Vault. The secrets sync knew only the first two accounts' file names, so "Upload to YouTube" kept saying the login was missing, and a restart would have lost it. Every account's login files are now kept in Vault and reach the worker within 30 seconds. After this release, sign in once more for The Aha-lorithm, since the earlier sign-in was never stored in Vault.
- The Aha-lorithm's background music was too quiet to hear on a phone. By default it now sits at 25% (about 12 dB under the voice) instead of 12%, and it still drops back while the aha line plays. Each short can set its own level, from 0 to 60%, with the slider on its Music card. To hear it in a short already made, run its "Plan typography" step and then its render again.

## [0.47.2] - 2026-10-18

### Fixed
- An Aha-lorithm short made before its account was set up ended with a "NAVAAN" mark and no end card. It now ends on the channel's own card, "The Aha-lorithm · AI explained in seconds" with @TheAhalorithm, and an item of another channel never shows NAVAAN's mark. To fix a short already made, run its "Plan typography" step and then its render again; nothing is paid twice.

## [0.47.1] - 2026-10-18

### Fixed
- Redoing a step that is followed by an approval (for example the video, before you approve it) threw the new result away. It put the old files back and called the run failed, because the step read "waiting for approval". The new output is now kept and waits for your approval.

## [0.47.0] - 2026-10-18

### Added
- Sentiment tab under Studio › Analytics (NAV-68). Claude reads every comment on your YouTube and Instagram posts and every message sent from the public site, once each. It marks each one positive, neutral or negative with a confidence and up to three short themes. The tab shows the share of each over the chosen period and day by day, a table per song or short, the themes people keep mentioning, and the five most positive and five most negative comments with a link to the post. "Score new comments" runs in the background (up to 200 a run) and shows how many were scored and roughly what that much Claude use would cost; the automatic analytics refresh scores new comments too. Your own replies are not scored. Hindi, Hinglish and English comments are all read in their own language, and the themes are in English.
- Studio warns when the server's settings disk (the 16 MB memory disk that holds the logins) is 80% full, and says how to find the file that filled it (NAV-54). The rule to keep one-off files out of it is in deploy/README.

## [0.46.3] - 2026-10-18

### Fixed
- Making a clip: if the start and the end were changed quickly one after the other, the start went back to 0. Both points are now kept. This also unblocks the 0.46.2 release, whose deploy check tripped on it.

## [0.46.2] - 2026-10-18

### Fixed
- Studio › Analytics was missing the "Best time to publish" bar chart from the classic page. It is back at the top of the Analytics tab, for Instagram and for YouTube (videos and Shorts). It shows a bar for each hour of the day in Central Time, a score for each weekday, and the next good slots. Peers, the competitor table, now sits right under it instead of below every chart.
- An Aha-lorithm short was rendered with only one picture, no gold captions, no music bed and no channel end card. Its narration sent the video to the lyrics template, which takes one background and the voice. A short with a picture per beat now always uses the scene template. To fix a short already made, run its render step again: nothing is paid for twice.
- The "Make one picture per beat" step showed only the first picture. It now shows every beat's picture.

## [0.46.1] - 2026-10-18

### Fixed
- An Aha-lorithm short stopped at "Plan typography, timing and music" with `TypeError: 'list' object is not callable` whenever it had music. The list of beat pictures had taken the name of the step that finds the music's beats. Run the step again and it goes through.

## [0.46.0] - 2026-10-18

### Added
- Visitors tab under Studio › Analytics (NAV-33). It shows who comes to the public site and what they play: visitors, page views, plays, minutes listened and how many opened the account page, for today and the last 7 and 30 days. It also lists each song, where visitors came from (YouTube, Instagram, WhatsApp, search engines, direct and others) and their device (phone, tablet or computer). Counting is first-party and uses no cookies. A visitor is the same address and browser on the same day, kept only as a code made with a key that is never stored and is replaced every day; no IP address or browser details are kept. Visits of the owner, link previews and crawlers are not counted. Add `?src=yt`, `ig` or `wa` to links you post so visits from YouTube, Instagram and WhatsApp are told apart, since those apps send no referrer. The privacy policy says all this.

## [0.45.0] - 2026-10-18

### Added
- The Aha-lorithm (NAV-67): a second short-form channel, for YouTube Shorts on @TheAhalorithm: AI explained in seconds. It has its own list under Studio (Aha-lorithm) and its own items (aha-001, aha-002 …). A short starts from an idea, from your own narration (kept word for word), or from nothing, in which case Claude picks the topic; never from a Suno link.
- Each short is a narrated scene video of 20 to 25 seconds. Claude writes a script of 6 to 9 beats (hook, explanation, the aha), each with its spoken line, a short on-screen caption and a picture prompt. A fact-check step then checks every claim on the web. After your spend approval, OpenAI makes one picture per beat (about 4 ¢ each; the pictures never contain words). ElevenLabs reads the script at normal speed (narration only). Each beat's picture fades in as its line starts, and the caption appears in bold white in the middle of the screen, with the key phrase in muted gold. A quiet ambient bed from the channel's own music library plays about 20 dB under the voice and drops back while the aha line lands. The end card shows "The Aha-lorithm · AI explained in seconds" and @TheAhalorithm. The YouTube description ends with a follow line and the channel's hashtags.
- The channel publishes only to YouTube: the Short upload and making it public, on the channel's own YouTube account.
- To use it, add the account in Settings › Accounts (type aha, YouTube channel @TheAhalorithm) and sign in to YouTube for it there; it shows only the YouTube rows, since the channel has no Instagram.
- Music for it comes from the `aha_music` folder: `<local_dir>/aha_music`, or `~/.local/share/navaan/aha_music` on the server, which has no local_dir. Put a few quiet ambient tracks there.

### Fixed
- Popups on the song page (Share a clip, Add to playlist, feedback) showed only a strip at the bottom of the screen on a phone. They used the header's class name and inherited its 64-pixel height. They now open in full.
- On a phone the song's cover is centred above its title.
- A song or inspiration already posted to YouTube could not finish without Instagram: there was no way to skip the Reel, and a failed post stayed on the page. Its Instagram lane now has "Don't post to Instagram", which takes the caption and post steps out of that item's pipeline and clears the failed post. "Post to Instagram after all" brings them back.

## [0.44.0] - 2026-10-18

### Changed
- Approvals that came straight after each other are given as one. Approving the YouTube upload also uploads the Short (both stay private). Approving the archive to the cloud bucket also allows the clean-up of the local copy, which still deletes nothing unless every file is checked in the bucket first. Choosing the visuals shows what the pictures and poster will cost and approves that spend in the same click ("Save, approve the spend and continue").
- The picture plan is written in more detail. Each scene is now four to six sentences (about 70 to 120 words) that name the shot and lens, who stands where and faces which way, what the hands and face are doing, at least three things in the place, the light's source, direction and colour, the air and texture, and one telling detail. A long scene is cut before its ending, so the no-lettering and plausibility lines always stay in the prompt.
- The Camera notes and Look notes boxes start with a suggestion to edit instead of being empty: written from the song's style at first, and the art director's own look and camera style once the picture plan exists. Clearing a box still leaves the choice to the camera operator or the art director.
- "No pictures yet? Make them with Gemini or ChatGPT" shows one tab per picture. Each prompt can be changed there and saved to the plan, "Copy this prompt" copies the changed text with the style line, and a "Look and people" tab holds the style line and the people description every prompt shares.
- A button that started a job or a save stays down and shows a thin moving bar along its foot until the work is done, so a second click cannot start it again.

### Fixed
- Pictures no longer show impossible set-ups such as a driver sitting the wrong way behind the wheel or a second face in a window (song-008, picture 2). The story director now has to state where the camera stands, where each person is and which way they face, and to name the driver's side that matches the country of the song for any scene with a car. Each person is in one place only, a reflection shows the person once, and a scene that could not exist in real life is rewritten. Every picture prompt also asks for correct anatomy and hands and for vehicles and furniture built as in real life. This applies to picture plans written from now on: a plan that is already written keeps its prompts until its "Write the picture plan" step is redone or the prompt is edited on the step's page.

## [0.43.0] - 2026-10-18

### Fixed
- An item scheduled to publish no longer says "A step failed" once its publish approvals are given. The run stops at the step that waits for its time, and that is now recorded as finished, with "scheduled: it publishes at the set time".
- The YouTube and Instagram lanes stay on the page under a failure message, so an approval waiting in them can always be given. Before, a failure hid them, and the Approvals page did not list them either.
- A publish approval on a scheduled item says when it goes out ("Post the Reel to Instagram today 6:00 pm CT, as scheduled. Approving now does not post now") instead of "now". The YouTube one no longer says the Reel waits for it.

### Changed
- The item page is simpler to read. Top right it says when the item goes out: the scheduled time in Central Time with a Change button, "When it finishes" with Set a time, or Published. A song shows its cover beside the title (an inspiration its reel's first frame), and the status is in words ("Videos approved") instead of internal names.
- Finished steps fold into one line ("8 done") that opens on a tap. Redo and Restart show on the step you open, and the approval switches inside an opened step, so the list stays short.
- When everything is approved and only the publishing time is left, one "All set" card says when it goes out on each platform, with the YouTube link, instead of lanes with Run buttons.
- The quote and the originality check are shown as text to read (the two lines of the quote; "Clear: no earlier use of these words found" with the links), with the raw file folded under them.
- The spend approval is called "Approve the spend" and shows the price of an inspiration's background picture, as the pictures step already did.
- Lists of songs and inspirations show the next action in words and a pill: Needs you, Scheduled with its time, or Published.
- On a phone the pipeline shows either what needs you or the steps (a Now / Steps switch), and the player and the tab bar join into one block at the bottom.
- Greyer text is a little lighter for contrast, and secondary buttons have an outline, so the three kinds of button (gold, outlined, plain) are easy to tell apart.

## [0.42.0] - 2026-10-18

### Added
- When you start a song or an inspiration (from an idea, from a Suno link, or by importing a Suno song), the form asks when it should be published: when the pipeline finishes, after your approvals (the default), or on a date and time you pick, in US Central Time (CST or CDT, whichever applies that day). A chosen time schedules both YouTube and Instagram for then; the approvals are still yours, and either time can be changed later on the item's Publishing schedule card. A time in the past is refused before anything is created.

## [0.41.1] - 2026-10-18

### Changed
- A clip is chosen on one bar with a handle at each end, instead of two separate sliders. The handles keep the clip 5 to 90 seconds long.
- Share on a clip also puts the caption on the clipboard: the song's name, the link to the full song and the hashtags (#NAVAAN #NewMusic #IndieMusic #NowPlaying), and says to paste it into the post. Instagram and some other apps drop text that is handed to them with a video, so the caption cannot be filled in for you there; WhatsApp and Messages keep it.
- The icons under Play have their word under them (Save, Playlist, Clip, Feedback, Lyrics). Save is a bookmark now, not a heart, so it is not read as a second like next to Feedback.
- Lyrics on a song's page are folded until you press the Lyrics icon; the choice is remembered in this browser.
- Play mode has a Feedback button next to Lyrics, opening the same reactions and message form.
- Someone who is not signed in and presses Save or Playlist gets a sheet that invites them to create an account, with a Create account button, instead of a line of text.

## [0.41.0] - 2026-10-18

### Changed
- A clip is chosen with two sliders, a start and an end, and can be 5 to 90 seconds long (it was 15 or 30). Moving one slider pushes the other so the clip stays inside the song and within those limits; "Start where it is now" takes the playing position as the start, and "Hear this part" plays the song from the start to the end so you hear what will be cut. The song's length is read from its file, so the sliders are there before you press play. A link to a clip made before still works.
- Save, Add to a playlist, Share a clip and "What did you think?" are a row of icons at the top of a song's page, under Play, instead of three cards down the page. Save is a heart you press at once; the others open a sheet. Someone who is not signed in presses the same icons and is told what an account gives.
- The bar at the bottom now shows the time played and the length under its seek bar, not only play mode and the song page.

### Fixed
- Share on a song no longer ends in "forbidden": if the link cannot be made, the song's own page is shared, as a visitor's Share always did. A page that was loaded under an older session now fetches the right token and tries the save again once, instead of every save answering "forbidden" until the page is reloaded.
- A clip starts at the second you chose: it is cut by decoding the song to that point and trimming, which is exact for any file, instead of seeking inside the file, which a file without a seek table can get wrong by seconds. Clips are kept in the cache up to the newest 500.

### Added
- The song page shows where you are in the song: a bar you can drag, with the time played and the length beside it (the full-screen player had this already). The clip card's "start at" time can now be read straight off it.
- Click a lyric line to play from there. Each timed line is a button that shows when it starts ("Play from 1:08"); it works before the song has started (the song starts at that line), while it plays (it jumps) and while it is paused (it jumps and plays). It is offered in the song page and in full-screen play mode, for songs with measured timing, or while the song plays when the line times are only estimated (the page then says a jump may land a little off).

## [0.40.0] - 2026-10-18

### Added
- The YouTube title, description and tags and the Instagram caption can be changed by you. They are editable where you approve them (the "Upload to YouTube" and "Instagram caption" approvals), on each step's page, and the YouTube text also under "Words and settings" on the Content tab. Each shows how much the platform allows (a YouTube title 100 characters, a description 5,000 bytes, tags 500 characters in all, an Instagram caption 2,200 characters), and a text over the limit is refused when you save it, not when it is posted. A changed Instagram caption has to be approved again, since the approval is for the exact words. Once the video is on YouTube its text is changed in YouTube Studio, and the page says so.

### Fixed
- Approve and every other button did nothing on a song or inspiration whose videos were approved, while its run was waiting at the YouTube or Instagram approval. The waiting run counted as "running" and locked the very button it was waiting for. The approvals in the YouTube and Instagram lanes now work while the run waits, the "Running" spinner no longer appears next to the approval it is waiting for, and a button that cannot be pressed is drawn dimmed.

## [0.39.0] - 2026-10-18

### Fixed
- "Write the prompt" under "No pictures yet? Make them with Gemini or ChatGPT" no longer ends in an internal error. Saving edits to the picture plan used to hide the prompt writer from it.

### Changed
- Scheduled posting for YouTube and Instagram is independent. On a song or inspiration you can schedule YouTube, Instagram or both, each with its own time in any order; a platform with no time is left for you to publish, and neither waits for the other. Before, the Reel had to be at least 5 minutes after the YouTube time and waited for the video to be public, and giving only the Reel time made YouTube go public 15 minutes earlier by itself. The suggested times are now each platform's own best slot, and the Schedule screen shows "not scheduled" for a platform you left out. The CLI takes `--at` (Instagram) and `--youtube-at` (YouTube), either or both.

### Added
- Making the poster is a step of a song's pipeline, right after the pictures and behind the same spending approval (which now lists it with its price, about 7 cents). It paints from the prompt saved on the Media tab's Poster card when there is one, else from a prompt written from the song, and it is finished once the poster exists. A song whose videos were already approved is not sent back to make one, so nothing is spent on older songs without you asking; for those the Poster card still makes it.
- A song's poster can be the picture a shared link shows. On the song's Poster card, "Use this poster for share links" puts the poster in the song's bucket folder; from then on the link you share (the song page and a shared clip) previews the poster, in portrait, instead of the square cover, in WhatsApp, Instagram messages and the like. If you make a new poster later, the card says shared links still show the earlier one and offers "Update the poster on share links". It needs the song to be in the bucket already; before that the card says so. The cover is still the cover everywhere else.

## [0.38.1] - 2026-10-18

### Fixed
- The words of a quote video drifted away from the voice (insp-005, the quote made from a Suno song). The step that times each line to the voice was meant to listen to the speech (Whisper) but, on the server, ran in a Python that does not have the speech tools, failed without saying so, and fell back to looking for pauses in the sound. A voice with music under it has no pauses, so every line after the first was placed by guesswork, up to four seconds late. The step now runs itself in the caption tools' Python whenever they are installed, so the lines are placed where they are spoken (on the same audio the first line ends at 5.9 s and the second at 11.0 s, where the guess had 6.9 s and 15.5 s). If it ever has to fall back to pauses again, the step's log now says so plainly. A quote video made before this keeps the old timing until it is made again: its sound files were already cleaned up from the server, so for insp-005 create the inspiration again from the Suno link.

## [0.38.0] - 2026-10-17

### Added
- A failed or stuck song or inspiration can be deleted. The Delete button is on the failure message and on the item's Activity tab; it asks first and says what happens: the item leaves the list and its files are moved to a _deleted folder inside songs (with a note of who deleted it and when), not erased. A published item cannot be deleted from here, and the page says why: take it down from YouTube, Instagram, the bucket and the site first. It is refused while a run is going.

### Added
- "End each Reel with a reason to send it" now reaches the video, not only the caption. When that recommendation is put to work, the quote step (inspirations) and the shot-list step (songs) write one short line naming who it is for ("Send this to someone far from home"). It is drawn in the brand's warm handwritten font and gold, with a short gold rule above it, on the last seconds of the finished video, the inspiration and the song's Reel, whichever way the video was rendered, and the Instagram and caption steps use the same line word for word. Without the rule nothing is written or drawn, and the video is untouched. If drawing it fails the video stays as it was rendered.

### Added
- Licence of new songs can be confirmed for you. In Settings, on the Automation tab, "Licence of new songs" has a switch and a box for your statement in your own words ("every song I publish is made on a paid Suno plan"). With it on, a song you publish is confirmed automatically, so it shows on navaan.online without a manual step; the statement is recorded as the reason and "owner (auto-confirm setting)" as who decided. A song you marked not allowed is never changed, a song that is not published yet is left alone, and it is off until you switch it on.
- A command to find songs with no language (language_backfill.py): it lists them, and with --apply fills in the ones whose lyrics are in Latin letters as English and syncs the site. Devanagari lyrics are left for you, since they could be Hindi, Maithili or another language.

### Fixed
- Share the clip on an iPhone: the clip is now loaded as soon as it is made (and on the shared clip's page as soon as it opens), so pressing Share opens the share sheet straight away. Before, it downloaded the clip after the press, and an iPhone refuses to open the sheet once the press has passed, so it showed "Could not open the share sheet". The button waits, saying so, until the clip is ready, and shares the link if the clip cannot be loaded.

### Changed
- An inspiration video without a voice now follows the "open with the key line" recommendation: its first line is on screen from the first frame (it used to appear after a second), and the video runs 7 to 15 seconds (it ran 10 to 30), as long as the words need within that. A duration written in the brief still wins, up to 30 seconds, and a narrated short still follows its voice. The quote step is told to put the strongest line first, since that line is now the opening.
- Importing a song from Suno now needs only the link. The sound is taken from the video the public Suno page lists (on Suno's own servers, the same file and the same checks as an inspiration's voice: it must decode all the way through, have sound and not be silent, up to ten minutes and 80 MB). An audio file is still accepted and wins when you add one, and it is the way out when the page lists no video or the download fails a check; nothing is created in that case.
- Album names are suggested as titles of a record, not as playlist names: each comes from an image, a line or one idea that runs through the songs, in the language of the songs, with a sentence on that idea. Names that read like a playlist (mix, vibes, hits, best of, collection, a year or "Top 10") are dropped from the suggestions.

### Fixed
- The approval switches on the steps were drawn as huge 44 px ticks. They are small switches now; the tap area is still 44 px.
- A finished publish step no longer says "This step did not save a file you can open here" when it shows where it published, and a finished step says an approval was asked "before it ran" rather than "needs your approval before it runs".

## [0.37.0] - 2026-10-17

### Fixed
- An English song imported from a Suno link had no language, so it did not appear under English on navaan.online (the import left the song's tags empty). The import now fills the language and genre; a song written in Devanagari is left without a language until you say which (Hindi, Maithili or other), instead of getting the placeholder text it used to get.

### Added
- A running step now looks alive. Its chip and its row in the step list show a moving icon, a progress bar fills as the step reports how far it has got (pictures made, the lyrics being timed, the video being joined) or moves when it reports nothing, and under it: how long it has run, which attempt of how many, when it last did anything, and how long it usually takes. The step it names is the one really running (the old text could lag a step behind).
- Opening a step no longer hides what needs you: the approval, the running card or the failure stays at the top and the step opens under it. The right side stays in view while you scroll the list.
- Every click is answered: approve, send back, redo, restart, run, stop, take an approval back, answer, and the approval switches each show a message saying what is being done and then what was done, and say so when nothing started because a run was already going.
- At "Review the videos" the approve and change buttons are above the videos, not below them. The full video, the reel without lyrics and the reel with lyrics sit side by side, each with its name.
- Feedback at the video review asks which video it is about and makes only that one again (the full video, or the reel). For the reel with lyrics you can also move the lyrics earlier or later by up to 10 seconds. The Instagram reel can go without lyrics: choose "Without lyrics" beside the approval while the lyrics are out of sync; the YouTube Short never had lyrics.
- Each step shows its data laid out for reading instead of as JSON: the picture plan (its idea, character, look and every picture's prompt, which you can edit and save), the shot list, which pictures move and where, the captions as a table, and the facts of a finished video. A step that has not run says what it will do and what it spends, and shows a draft where one exists. A step that ran before but must run again says so and when it last ran, and a running step marks the old files as the previous version.
- The approval a step asks for has a switch on the step ("Ask me before it runs"). It is the same setting as Settings, Approvals that approve themselves, so it applies to every song; switching off one that spends, publishes or deletes asks first.
- A publish step shows where it published: the YouTube video, the Short and the Instagram Reel, each with its link and whether it is private or public, and writes them to published.json. The history line of the step carries the links.

### Changed
- YouTube and Instagram are separate lanes once the videos are approved. Each lane has its own next step and its own approvals, they show side by side on the song's page, and neither waits for the other: the Instagram caption can be written and approved, and the Reel posted, before the YouTube video is uploaded or public, and the other way round. Archive and clean up wait until both lanes are finished. The Instagram caption no longer needs the YouTube link; the song's page on navaan.online is added to it instead. A run still does one step at a time, but it carries on with the other lane instead of stopping at an approval the first lane is waiting for.
- Every YouTube description and every Instagram caption now ends with the site address: the song's page on navaan.online for a song, navaan.online for an inspiration. It is added when posting, only if it is not already there.

## [0.36.1] - 2026-10-17

### Fixed
- Release 0.36.0 did not go out: the deploy checks failed because a browser test still expected the old wording of the message shown when you press Create on a new inspiration with nothing typed. Nothing changed in production. The message ("Write the quote or the idea first, or paste a Suno link.") and the test now agree, and the browser and speed checks were run before this release. Everything listed under 0.36.0 ships here.

## [0.36.0] - 2026-10-17

### Changed
- The small mark on every video, the wide one and the reel, now says navaan.online instead of the Instagram handle. A mark set in the profile (video.watermark, or "off") still wins. Videos made before keep the old mark until their video step is redone.

### Added
- The site has a tagline: "Every new sound carries an old emotion." It sits under the Browse heading, on the sign-in page, and in the page description that search results and link previews read.
- A new inspiration can take its voice from a Suno song. Paste the song's Suno link when you create the inspiration: its lyric lines become the quote, its title becomes the title, and the sound is taken from the video file that the public Suno page itself lists (on Suno's own servers, nothing is decrypted and no third-party site is used). The download is checked before anything is created: it must come from Suno's servers, be a video file of a sensible size and length, decode all the way through, have a sound track, and not be silent. A link that fails any check is refused with a sentence and creates nothing. The pipeline then times the lines to that voice, makes the background picture, and renders the reel as usual; the voice already holds the song's music, so no background track is added unless you add one.
- ElevenLabs narration stays as the backup. Without a Suno link an inspiration is narrated by ElevenLabs exactly as before. On a short whose voice came from Suno, the Narration card says so and offers ElevenLabs as the backup, and running "Narrate the quote" again replaces the Suno voice.

## [0.35.1] - 2026-10-17

### Fixed
- English text in a video no longer comes out as boxes. The channel mark ("@navaan_p5l") drawn in the corner of the wide video and the reel, and the lyric captions for an English song, were drawn with the caption font, which on the server is Devanagari only: digits and underscores drew, every Latin letter was the same empty box. Text with Devanagari still uses that font; other text now uses one that has the letters. Long caption lines also wrap to two lines and shrink to fit the frame (they used to run off both edges). Videos made before this keep the boxes until their video step is redone.

## [0.35.0] - 2026-10-17

### Added
- The artist's own singing voice (the profile's "Preferred vocals", `music.voice`: male or female) is used as the singer for the picture directors and the poster when a song's style does not say, so it does not have to be written into every style. A song whose style names the voice still wins; duet, mixed or unset assume nothing.

### Changed
- Importing a song needs BOTH the Suno link and the audio file. The link gives the title, lyrics and style, read from the public Suno page over plain HTTPS (a /s/ share link works) and checked before anything is created, so a private song or one with no lyrics is refused with a sentence; your file gives the sound. Before, either one alone was accepted, and an MP3 on its own produced a song with no lyrics, which broke the captions and let the picture plan invent a story.

## [0.34.0] - 2026-10-17

### Added
- Any step in the pipeline can be opened: click it to see what it said (a prompt, a plan), what it made (pictures, audio, video), its log and its own history, and go back to what needs you. A step that has not run yet opens too and says so.
- Pictures can be opened large: click the poster, the cover, the album cover, a shot's picture or a step's picture to see it full screen; Escape, Close or a click outside closes it.

### Fixed
- A male-voiced song got a poster of a woman, and its picture plan a woman as the main character. The directors are now told who sings (read from the song's style: male, female, or not stated) and not to invent a love interest unless the lyrics are about one. The poster's default prompt shows a lone man or woman seen from behind to match the singer, or no people at all when the singer is not stated. The poster card has "Reset to the suggested prompt", because a prompt saved earlier would otherwise hide the fix. For a song whose plan already has the wrong character, redo "Write the picture plan" (and the pictures).

- A song with no lyrics saved (an imported MP3 has none) now says so up front on the Pipeline tab, and the captions and the picture plan stop at once with a plain sentence ("this song has no lyrics saved, so there is nothing to time. Add the lyrics on the Content tab") instead of crashing deep in the aligner with a divide by zero. A failure whose step printed its own reason now shows that reason, not an empty message.

- The captions step now also makes an English transcript when the lyrics have Latin-script lines (English, or romanised Hindi). The aligner matches those lines against it, but it was never made, so an English song had no speech to line up against.

### Changed
- The shot list approval shows the pictures in order, each with when it is on screen, the camera move and the scene, with the raw JSON folded away under it.
- Steps use real names ("Write the picture plan", "Create the pictures", "Plan the shots", "Plan what moves") instead of internal ones.
- In the steps list only the step whose approval is in front of you is marked "waiting for you"; steps blocked behind it are simply later, so one amber row shows the one thing that needs you.

## [0.33.1] - 2026-10-17

### Changed
- Making a clip: the start is now a slider (with the start and end time beside it, never past the end of the song) instead of a number box. Where the song's length isn't known yet it stays a number box.

## [0.33.0] - 2026-10-17

### Added
- Background music for an inspiration short. The Content tab has a "Background music" card: add your own track (mp3, wav, m4a, aac, flac or ogg, up to 20 MB). ffmpeg trims it to the length of the video, fades it in and out and levels it, and the renderer keeps it quiet under the voice. The track's own name is kept in the item's history so its licence can be checked later. Free tracks, for example from pixabay.com/music under its Content License, work; checking each track's licence is up to you. A video that is already approved keeps its sound until you Redo "Plan the typography".

### Changed
- What an approval asks you to review is now on the approval itself: "Review the videos" plays the finished videos right on the card (no more switching to the Media tab), and "Listen to the song" plays the song. The address carries the file size so the browser never plays an older file of the same name.
- A narration (a recorded or an ElevenLabs voice) no longer switches the background music off, and with a voice `music: auto` now means only your own added track, never a library pick or a generated pad under the voice.

## [0.32.0] - 2026-10-17

### Added
- Visitors can pass a clip on, for sharing and publicity. After making a clip: **Download the clip** (to post from the Instagram app on a phone), **Copy caption** (the song, the link back to the full song and #NAVAAN #NewMusic), and on a computer a line saying how to post it, because only a phone's share sheet can take the video itself. The page a shared clip opens (/c/...) now has **Download the clip** always and **Share this clip** where the browser has a share sheet, so whoever receives a clip can pass it on too. The link preview (video, picture, title) was already there.

## [0.31.0] - 2026-10-17

### Changed
- The item page (a song or an inspiration) is rebuilt so it can be walked. One "now" card says the single thing that needs you (an approval, a question, a failure, or "Next: ..."), never an approval and a "Running" chip side by side. The steps run top to bottom with their name beside each node, their state in words, and Redo on the row. Everything else moved into tabs: Pipeline, Content (quote, lyrics, shot list, narration), Media, Publish, Activity. The tab is kept in the address (?tab=media).
- The credits approval now lists exactly what it spends, from the item's own steps (for an inspiration: OpenAI for the background and ElevenLabs for the voice; Suno only where a song really uses it), instead of always saying "Suno, Flow and OpenAI".
- A failure leads with a sentence in plain words and folds the raw error away under it. A failure that has since been fixed (the step it names now succeeded) no longer shows.
- An item that is only waiting for an approval says that nothing is running.

## [0.30.1] - 2026-10-17

### Added
- The Narration card shows a "Spoken script" field: exactly what ElevenLabs will read, prefilled with the quote plus the tone tags and pauses of the chosen pace. Edit it, Save the script, and run again; the saved script is spoken word for word. "Back to the suggestion" clears it. (The on-screen text is unchanged: tags never appear in the video.)

### Fixed
- Slow narration is now really slower on eleven_v4. Measured on the live service, the [slowly] tag alone changed nothing (a sentence took 5.76 s), while ellipses between phrases did (7.84 s for the same words), so Slow now puts an ellipsis at each phrase break (only where the text does not already pause, and never inside a two-word phrase), besides the tags and the pause between lines. Calm stays tone only.

## [0.30.0] - 2026-10-17

### Fixed
- A run that was waiting at a gate no longer waits forever when the gate is settled another way. Choosing the visuals for an imported song left its run showing "Running: waiting for you: approve gate visuals_mode" for hours (nothing to approve) and blocked a new run until Stop was pressed. The run now notices within 2 seconds and carries on.

### Added
- Share a clip: on a song's page, anyone can pick where a clip starts and make a 15 or 30 second vertical video of the song (the cover, the title, "Hear the full song" and navaan.online over the song's sound). It is shared through the phone's share sheet (Instagram, WhatsApp and the rest) with a link that opens a page playing the clip and leading back to the whole song; where the share sheet cannot take a file the link is shared. Only songs a visitor may play can be clipped, up to 20 clips an hour from one address.
- Album pipeline in Studio > Albums: "New album from songs" lets you pick two or more songs, get five name ideas made from them (a few cents of OpenAI chat), type your own if you prefer, and create the album with the songs in the order you picked. An album's page has a Cover card: square art from a prompt you can read and change (about 4 cents), the NAVAAN mark, the album title and artist drawn over it in a lettering you choose, or use your own picture. The cover is kept in Studio for now; showing it on the public site is the next step.

## [0.29.10] - 2026-10-17

### Changed
- Slow and Calm narration now keep the newer ElevenLabs voice model. On eleven_v4 and v3, which ignore the speed setting, the pace comes from direction tags in the spoken text ([warmly] [softly] [slowly], a pause between lines and after commas); the other models still take the speed setting. This replaces the 0.29.8 switch to the older multilingual v2 model.

## [0.29.9] - 2026-10-16

### Added
- Three more narration voices from your ElevenLabs account, SunoCustom1, SunoCustom2 and SunoCustom3, and SunoCustom1 is now the default voice (Frank and NJ stay in the list). A short or Setting that already names a voice keeps it.

## [0.29.8] - 2026-10-16

### Fixed
- The slow narration pace now works: ElevenLabs' newest models (v4, v3) accept the speed setting but ignore it, so a take with a pace uses a model that obeys it (multilingual v2), and a quote kept as one run of sentences gets a pause after each sentence. A take with no pace (Normal) still uses the model chosen in Settings.

## [0.29.7] - 2026-10-16

### Fixed
- "Stop the run" now says "Stopping…" and cannot be clicked twice while the worker acts on it, and a run waiting for an approval notices the stop within about 2 seconds instead of up to 15.
- An item that is only waiting for an approval (nothing running) now says so and points to Redo, instead of leaving you looking for a Stop button that has nothing to stop.

## [0.29.6] - 2026-10-16

### Fixed
- ElevenLabs narration is no longer rushed: it speaks slowly by default (pace Slow, with a pause between lines) so the voice can match the text on screen. The Narration card has a Pace choice (Slow, Calm, Normal); changing the voice or pace makes the voice again, as long as the video has not been approved. A voice made at the same settings is reused from the cache and costs nothing.

## [0.29.5] - 2026-10-17

### Changed
- The Studio page of a song or inspiration is easier to walk through. Right under the title there is now a progress strip: one chip per pipeline step in order, showing done, the one you are at, a step waiting for your approval, a failed step, and what is still to come (each chip jumps to its row). The Steps list moved up from the bottom of the page to sit straight under the action card, so the steps and what to do next come first and the editors, files and analytics follow.

## [0.29.4] - 2026-10-17

### Fixed
- Retry works after a restart. When a deploy restarted the worker in the middle of a run, the page showed a failure with a Retry button that was switched off (no step was named). It now says Run again and carries on from the next step.

## [0.29.3] - 2026-10-17

### Changed
- Inspiration videos show one line of the quote at a time: each line fades out as the next comes in (the last holds), instead of every new line being added under the one before. A short can keep the old look with `- layout: stack` in its brief.

### Fixed
- A run that is waiting for an approval can be stopped from the page again: the approval now has "A run is waiting" with a Stop the run button beside it, so you can stop it, change something earlier (or redo or restart from a step) and run on, without the classic view.

## [0.29.2] - 2026-10-17

### Changed
- Narrating the quote with ElevenLabs is now a standard step of every inspiration, not an option you have to find: the Steps list shows "Narrate the quote (ElevenLabs)" (before the timing and typography steps) and it runs with Frank unless you pick NJ on the Narration card. The spend is approved first, and a short can still skip it (untick it in the New inspiration dialog, or press Skip narration on the Narration card) to stay music and text only. A short whose video was already approved is not reopened. Without a saved ElevenLabs key the step stops and says how to add it or skip.

## [0.29.1] - 2026-10-17

### Fixed
- An approval a running job is waiting for is now shown. A pipeline step that waits for you (for example "Review the videos" after an inspiration is rendered) used to show only "Running" with a Stop button, so the Approve button was missing and the only way to approve was the classic view. The page now shows the approval, with Approve and Request changes, as soon as the job is waiting for it.

## [0.29.0] - 2026-10-17

### Added
- A mood for each song (dawn, dusk, night or quiet), chosen on the Studio song page. It picks the picture behind the lyrics in full screen play mode (the night picture when none is chosen; the parchment picture on the light theme).

### Changed
- The studio sign in page has the new look: the night picture behind, the NAVAAN logo above the card, gold instead of pink. The logo and the mood pictures are public files so this page can show them before anyone has signed in.

## [0.28.0] - 2026-10-17

### Changed
- Settings is easier to read and traverse. It opens on an At a glance board: every connection with one line on how it is doing, the ones that need you first, each with a Fix button that opens the right place. Below it are four tabs: Accounts, AI services, Automation and Storage. Tokens and keys sit in rows that fold open (Change, Sign in) instead of an always-open box under every line, with plainer wording ("Competitor data" instead of "Peer data (Facebook)").
- The studio sign in page shows the version.
- Narration with ElevenLabs for inspiration shorts: the Narration card has "Narrate the quote with ElevenLabs". It speaks the quote only (not the author), in Frank (default) or NJ, shows about how many seconds it will use and this month's total against the cap, and adds a "Narrate the quote" step to the short that runs after you approve the spend. The lines are then timed to the voice by the existing step. The same text in the same voice is never generated twice.
- A round play button on every song cover in Browse, Library, saved songs and playlists (and on album covers, which play the whole album) plays it without opening the song page. On a mouse it appears when you point at the cover; on a touch screen it is always there; it turns into Pause while that song plays.
- The ElevenLabs audio cache no longer lives in the small config folder.
- Full screen play mode keeps the lyrics folded away until you press Lyrics (the choice is remembered). With them hidden, the cover and controls are centred.

### Changed

### Changed
- The public site's Library is open to visitors: they can browse every song, and Create playlist (or Add to playlist) leads to Create account, which asks what they like (mood, genres, languages) and an optional email for when accounts open. Studio > Analytics > Feedback shows how many asked and what they like.
- The public site no longer offers a Studio sign in: the owner signs in on studio.navaan.online (signed in, Studio and Settings still show on the public site).

## [0.27.0] - 2026-10-17

### Added
- Library and playlists open as a grid of covers by default, with a Grid / List switch (remembered per screen): the Songs tab, your playlists, saved songs and the songs inside a playlist. A playlist's tile shows the cover of its first song. In a playlist's grid you can play or remove a song; changing the order is in the List view.

### Changed
- Full screen play mode uses a wide screen: on desktop the cover, title and controls sit on the left and the lyrics are large on the right, over a soft blur of the cover's colours. Phones keep the stacked layout.

## [0.26.0] - 2026-10-17

### Changed
- The NAVAAN logo (the N made of a sound wave) replaces the plain gradient square: in the sidebar and top bar (the black version on the light theme), as the browser tab and phone home-screen icon, on the shared-link page, and on every poster. It is a low-resolution PNG for now; a larger or SVG original would make the poster crisper.

## [0.25.1] - 2026-10-17

### Fixed
- A shared link (navaan.online/s/...) plays the whole song and no longer says "30 second preview" or asks for a sign in, since the site is free. It has an Open on NAVAAN button to the song's page; the share box in Studio says the same.

## [0.25.0] - 2026-10-17

### Added
- Poster for each song, on the Studio song page under the media: a portrait (2:3) poster made from a prompt that is shown and editable (prefilled from the title, style and lyrics), with the NAVAAN mark, the title and the site drawn over the art by us so the native script is always right. Three lettering styles (bold serif, brush, handwritten; bundled open-licence fonts that cover Hindi and Latin), or use your own picture as the art (free). The button shows the cost (OpenAI images, under the run cap in Settings); "Redraw the title" is free. Using the poster in the player and lists comes next.

## [0.24.1] - 2026-10-17

### Fixed
- Saving an ElevenLabs key now tells you what happened, right under the box, instead of at the top of the page where it was easy to miss. A key that ElevenLabs recognises but that cannot read the account (no "User: read" permission) is now saved with a note rather than refused; a wrong or mis-pasted key says so in plain words.

## [0.24.0] - 2026-10-17

### Added
- Shuffle on the player. A shuffle button sits with Back, Play and Next on the bar (on a phone it is in play mode and on the song page), and albums and playlists have a Shuffle button that turns it on and starts a random song of the list. Every song plays once, in a random order, before any repeats (and the first of the next round is never the song that just played); Back returns to the song before; the choice is remembered.

## [0.23.0] - 2026-10-17

### Added
- Feedback on every song of the public site: thumbs up, thumbs down and "love it" (double thumbs up), counted anonymously per song (a visitor can change their mind or take it back; the choice is remembered in their own browser), and a Send feedback form with an optional email for a reply. A thumbs down invites a word about what to improve. Studio > Analytics has a new Feedback tab: reactions per song (7 days, 30 days or all time) and the messages, with a reply link, and Mark as read. Per address limits and a hidden field keep bots out; the privacy policy says what is kept.

### Changed
- The site opens dark (Midnight Cinema) until someone chooses; "Match my device" is now a choice like the others.

### Fixed
- The player shows the song's picture, not its first letter.

## [0.22.0] - 2026-10-17

### Added
- The free public site. On `navaan.online` nobody has to sign in: Browse, search, album and song pages with lyrics that follow the song, and playing the whole song are open to everyone, for songs that are published with a confirmed licence. A visitor gets no download control, five-minute stream links, and rate limits; Save and Add to playlist say that accounts are coming soon; sharing a song shares its page address. Nothing in the studio, settings or account area is reachable from there.
- One sign in for you on both hosts. The sign in covers `navaan.online` and `studio.navaan.online` (a cookie for the whole domain), so signing in on one signs in on the other. On the public site you see Studio, Settings and Security as links to the studio host, and the studio's menu has a link to the public site. Passkeys now belong to `navaan.online` and work on both hosts; the old address keeps its own sign in. Register your passkey again once (Account menu, Security).
- Volume and mute on the player (the bar and play mode), remembered between visits.

### Fixed
- The Now playing bar no longer lets the page show through it, and the page leaves room beneath its last block.

## [0.21.0] - 2026-10-16

### Added
- Songs list a page at a time: the Library's Songs tab and the playlist's Add songs panel load 24, then more as you scroll (or with a Show more button), and say nothing more when there is no more. `GET /api/catalog/tracks` takes `limit` and `offset`.
- Add a song to a playlist from anywhere a song is listed (Library songs, album pages): a plus button opens your playlists and a New playlist form. A playlist page has an Add songs panel with search, marks songs already in it, and an editable description.
- Creating a playlist asks for its name, what it is for, and who can see it (private, unlisted or public, each explained), not only a name.

### Changed
- Moving between screens is smooth: each block of a new screen eases in (opacity and movement only, so nothing shifts), and a quick load shows nothing instead of a flash of "Loading…"; a slower one shows soft placeholder blocks.

## [0.20.0] - 2026-10-16

### Added
- The app has its own domain. `navaan.online` is the public app, `www.navaan.online` redirects to it, and `studio.navaan.online` is the studio; `navaan.njlabs.dev` keeps working for now. Each host has its own sign in (cookies are per host). A session on the public host sees the listener app only, even the owner's, and share links are made on the public host. Passkeys belong to a host: register the owner passkey again on `studio.navaan.online`.
- The release now checks the new hosts after rolling out and rolls back if they do not answer.

### Changed
- The credit is NAVAAN Studio instead of NJLABS: the sign-in page, the classic page, the privacy policy and the terms, and a footer with links to the privacy policy and the terms in the app.

## [0.19.0] - 2026-10-16

### Added
- Albums for listeners: Browse has an Albums row, and an album page plays from the top (the queue is the album, so Next goes to its next song) with a Play button on each song. Listeners only see published albums, and only the songs they may hear.
- Play buttons on the studio's album page and on playlists: one for the whole list and one per song, with the list as the queue.

## [0.18.1] - 2026-10-16

### Fixed
- Analytics no longer fails to draw on a database with nothing collected yet: it shows "Nothing collected yet" and the Collect now button.
- Library > Songs: choosing a language and then a genre quickly could show the answer for the first choice (a slower reply replaced the newer one). Only the latest choice's answer is shown now.

## [0.18.0] - 2026-10-16

### Added
- A proper player. Back and Next on the song page, the bar and the full-screen play mode; a finished song starts the next one (the list it was started from, else the whole catalogue); a seek bar and the time on the bar; lock screen and headset controls where the browser has them.
- Share opens a sheet with where to send it: WhatsApp, X, Facebook, Threads, Telegram, LinkedIn, Reddit, email, the phone's own share sheet, and copy. It makes the 30 second preview link as it opens, and you can stop sharing from the same sheet.
- Cloud: Play audio, watch video and view pictures inside the app; lyrics, style, caption and the other words open in the song's editor; Download is called Download, for any file.

### Fixed
- The Play button is a circle (it was an oval: two rules disagreed about its width).
- Lyrics follow the song. A song whose timing was measured by the pipeline (`caption_cues.json`, as on song-006) now has its lines marked as it plays; a song with no timing at all follows approximately, spread over its length, and says so.
- Cloud rows no longer run into each other on a phone.

## [0.17.1] - 2026-10-16

### Fixed
- A song whose history was written as objects (song-001, from before the move to the database) no longer shows a black screen: its history reads normally. If a screen ever fails to draw, it now shows what happened with a Reload button instead of going black, and reports the error.
- Studio (`/app/studio`) is a real front page with a tile for each area and what is waiting, instead of a "coming soon" note that sent you to the classic view.

## [0.17.0] - 2026-10-16

### Changed
- The new app is the front door: opening the site goes to `/app/` for everyone who is signed in (a listener lands in the listener app). The classic view stays at `/legacy` for one release as the way back; it is removed after that.

### Added
- Redo a finished step, or restart the Produce phase from it, on the song page (each asks first and says where the old files go), and "Put it to work" on a recommendation: a timing one opens the schedule, the rest becomes a standing rule for new items.
- The song page in the new app edits a song's words and settings (title, lyrics, style, Instagram caption, quote, tags, brief) and its shot list (start, end, picture, camera move, label), and attaches or removes an inspiration's narration. The made audio and videos play on the page, with a link to each file; audio archived to the bucket plays after being fetched back. An unsaved edit is flagged, kept for the tab, and the browser warns before you leave; every save is recorded in the history with who made it.
- The visuals gate is chosen in the new app: the look (video from pictures, one cover picture, or Google Flow clips), your own pictures (add, remove), the prompts to paste into Gemini or ChatGPT (write, copy), the two-picture OpenAI test, 9:16 versions, and camera and look notes. Nothing that spends credits runs without its approval, as before.
- Settings in the new app (Settings in the account menu): each Instagram and YouTube connection with whether it works and what is wrong, refreshing or saving a token (a token is never shown again), YouTube sign in, the Claude token, which approvals approve themselves (the risky ones say what they do before they can be switched off), the picture, narration and music choices with their keys and this month's spend, and where cloud storage points.
- A "Needs attention" banner on every studio screen when a sign in has expired or is about to, the schedule is paused, or the worker is down, with a link to where it is fixed.
- Security in the new app (account menu): change the password (other sessions end), renew the recovery codes (shown once), add and remove passkeys, sign out.
- Scheduling in the new app: set times for YouTube and Instagram from the recommended slots (the Reel must follow YouTube by 5 minutes), accept the suggested times, change or clear a schedule, from the Schedule screen or from the song; a view of the hours and weekdays that did best.
- A Cloud page in the new app: what is archived in the bucket per song, whether the copy is verified, whether the local copy was cleaned, and a short-lived link to open any file; it says plainly when the cloud is not set up or not reachable.
- The rest of Analytics in the new app: Collect now, Re-run analysis, Ask for advice (each runs only when pressed), the auto refresh schedule, peers and hashtag suggestions, linking a post or video to a song, and a song's own numbers on its page.

## [0.16.0] - 2026-10-16

### Added
- The new app can start a song or an inspiration: a New button on Songs opens a short form (title, optional first idea) and takes you to the new item. The song page also takes a Suno link or file, shows the questions waiting for an answer and lets you answer them, and has the Approvals sections, so these no longer need the classic page.

### Fixed
- The history of a revoked approval now names who revoked it (it showed no name).

## [0.15.1] - 2026-10-16

### Changed
- The classic dashboard loads small cover pictures instead of the full-size ones: the first load pulled about 11 MB of PNG covers; list cards, small covers and the hero now ask for a 160, 480 or 960 pixel JPEG (made once with ffmpeg and kept), while a song's own page and downloads still use the full file. If a thumbnail cannot be made, the original is served and the reason is logged.

## [0.15.0] - 2026-10-16

### Added
- The listener side of the app. A person without studio access now sees a listener app: Browse (newest, then by language, with covers that fade in), a song page with the big cover, one round Play button, the lyrics (line by line, with the current line marked and followed as the song plays, when timing exists), save, add to a playlist and share, and a full-screen play mode that opens from the Now playing bar and back with the keyboard (Escape) or the close button. A listener only ever sees songs that are published with a confirmed licence, and the studio stays closed to them.
- Library gets a Songs tab you can filter by album, language and genre. Albums are real objects in the new app: create one, open it, add songs, put them in order (and the order persists), edit its kind, status, date and description, and delete it; a published album can only hold published songs, and its cover is its first song's.
- Anyone signed in can share a song they can see (the link and preview work as before); you can stop any link you made, and the owner can stop any link. A playlist set to unlisted or public opens by its link for another person, read only; a private one is "not found". The new Account page downloads your data or deletes your account.
- Browser checks for the listener side run in CI: browsing, playing with lyrics, a share link opened signed out, the free playlist limit, album create, reorder and reload, and the layout and accessibility checks on the listener screens in both themes.

### Fixed
- Search and the catalog no longer treat the key names of a song's metadata file (genre, composer, album, ...) as words about the song; the song's genre and language are now stored and used for the filters.
- A request could leave its database connections open until a later clean-up; 200 requests left 82 open against a limit of 30 on the server. Each request now gives its connections back, and the server's connection limit is 60.

### Changed
- The app itself (`/app/`) is served to every signed-in person; what they can do is still decided route by route.

## [0.14.0] - 2026-10-16

### Added
- Plans and playlists. Every person is on the Free plan (3 playlists) until they are moved; what a plan includes is data, so you can raise a limit with one change and it applies at once with no release (`POST /api/billing/entitlement`, owner only). Premium is shown but cannot be bought yet. The new Plans page compares them and shows how much of yours you have used; the owner is never limited.
- Library in the new app: create playlists, open one, rename it, change who can see it, put songs in order (move up and down) and remove them; save songs from a song's page or add them to a playlist. Two edits to one playlist at the same time are both kept, in a sensible order. A playlist, a saved song or a play belongs to one person; another person gets "not found".
- Listening needs the plan's `audio.play` (everyone has it for now) and each play is recorded per person and song, in monthly partitions so old detail can be removed by dropping a month.
- Account export and delete: `GET /api/account/export` downloads everything held about a person, and `POST /api/account/delete` (typing "delete my account") removes their library, plan, sessions and links; the owner account cannot be deleted this way.

### Not yet
Point-in-time recovery, error tracking and the uptime check, and the security review of the public surface, are still to do before anyone can sign up.

## [0.13.0] - 2026-10-16

### Added
- Motion and playback in the new app: a short fade when you move between screens, covers that fade in over their dominant colour in the right size (AVIF or WebP, 320, 640 or 1280) with no layout shift, an equaliser that marks the song that is playing, and a Play button on a published song with a Now playing bar that keeps playing while you move around. All motion stops when your device asks for reduced motion, and the glass panels become solid without backdrop-filter support or when reduced transparency is on.
- Quality gates that run on every pull request: browser checks at 390x844 and 1280x800 in both themes on ten screens (no horizontal scroll, touch targets of 44px, no serious accessibility violation including colour contrast in the real layout), and a Lighthouse mobile gate (performance and accessibility of 90 or more on the main screens). They sit next to the existing checks for colour literals and theme contrast. Run them yourself with `npm run e2e` in `plugins/navaan-studio/web/e2e`.

### Changed
- The app's files are sent gzipped and each screen loads when you open it, so the first paint on a slow phone connection is faster (Lighthouse mobile performance 87 to 98).
- The account button's name now matches what it shows, which the new browser check flagged on a desktop.

## [0.12.1] - 2026-10-16

### Fixed
- The 30 second share preview no longer carries the song's embedded cover picture and tags, which made it a third bigger than it needed to be.

## [0.12.0] - 2026-10-16

### Added
- Share links. On a published song with a confirmed licence, Studio > Songs now has a Share section: Create a share link gives a link anyone can open without an account (`/s/<token>`). It shows a branded card with the cover and a 30 second preview, and chats show a preview card with the song's title and cover. You can stop a link at any time and it stops working at once; opens are counted. The preview is cut once from the audio in the bucket and stored next to it.
- Cover pictures in three sizes (320, 640, 1280) as AVIF, WebP or JPEG (`/img/<song>/<size>.<format>`), made from the original in the bucket on first request, cached, and served with a one year cache lifetime and an ETag, so they still work after the studio's local copy is archived. The first request also records the cover's size and dominant colour.
- Play links: `GET /api/play?slug=` returns a link that expires after 5 minutes and goes straight to the bucket, so audio never passes through this server; it refuses a track that is not published or is marked not allowed.
- Search in the new app: the search box in the top bar (and a Search icon on a phone) finds songs and albums in Devanagari or Roman letters.

### Changed
- Links to files in the bucket are made with the OCI SDK instead of a command line process per link, and one link is reused for its lifetime.

## [0.11.0] - 2026-10-16

### Added
- Studio > Analytics in the new app, in three tabs. Analytics: the headline numbers, a line per metric, and your posts or videos (a table on a desktop, stacked cards on a phone), for Instagram or YouTube, one account or all, the last 7, 30 or 90 days. Recommendations: each with its evidence, the action and the expected effect, Done or Dismiss, and the Done and Dismissed lists with Reopen. Interactions: unreplied comments where you edit a reply or ask Claude for a draft, then Approve and send; nothing is posted until you press it and confirm for that one comment. It reads the same data as the classic Analytics page, so the numbers match; the view is in the address, so it can be linked.

## [0.10.0] - 2026-10-16

### Added
- Studio > Inspiration, Approvals and Schedule in the new app. Inspiration lists your quotes and short videos and opens each on its own pipeline steps (quote, originality, background, typography, render), with the same gate, Approve and Request changes as songs. Approvals is one list of everything waiting for your yes across songs and inspiration, grouped by what is asked, with one Review action each. Schedule is a month calendar (Monday first) with every YouTube and Instagram time, a day-by-day list under it, and missed or blocked publishes marked; on a phone it is the list only. `GET /api/schedule` serves it.
- Home opens inspiration items in the new app too.

## [0.9.0] - 2026-10-16

### Added
- The owner decides, per track, whether it may be offered behind a plan: `POST /api/catalog/license` (owner only, audited) sets confirmed, unconfirmed or not allowed with a note, and `GET /api/tracks` lists every track with its origin, Suno model, plan tier and licence. The same decision can be made from a shell: `python3 catalog_store.py license confirmed "why" --plan paid`.
- A new song records the Suno plan tier at import when `suno.plan` is set in `navaan.config.json`.

### Fixed
- The Postgres container gets 256 MB of shared memory instead of Docker's 64 MB default, so a large index build can no longer crash it. The database container restarts once at this deploy; the data is on its volume.
- The catalog sync no longer logs an error for the `_template` folder at every start.

## [0.8.0] - 2026-10-16

### Added
- A catalog in Postgres (schema `catalog`): your published songs as tracks with their audio and cover files in the bucket, albums made from the album labels, and a search index. It is rebuilt from the studio at every start and after every run, so it never needs hand editing. Every track records its origin and a licence status that starts as unconfirmed; only you confirm it, and an unconfirmed track can never be put behind a plan.
- Search that finds a song by typing it in Devanagari or in Roman letters (`/api/search?q=tere hone se` finds तेरे होने से), tolerating typos and accent differences; 10,000 tracks answer in about 40 ms (95th percentile). A listener account may search; it cannot use the studio.
- An album editor API: create, edit, reorder and delete albums (`/api/albums`, `/api/albums/save`, `/api/albums/reorder`, `/api/albums/delete`). The screens come later.

## [0.7.0] - 2026-10-16

### Added
- Studio > Songs in the new app (`/app/studio/songs`): the list of songs with state, next action and filters, and a song page with the step list, the approval gate with the text you are approving, Approve and Request changes, a failed step with its log reference and a Retry, and the history with who and when. Music songs on Home open there; inspiration and the other screens still open in the classic view.
- Request changes: send a song back with a note instead of approving. It drops any approval of that gate and keeps the note in the history; it never counts as an approval and does not start a run by itself.

### Changed
- Approvals and requested changes made in the new app record who made them in the history (for example `via ui:owner`).

## [0.6.0] - 2026-10-16

### Added
- People, roles and permissions in Postgres (schema `core`). You are the `owner`; a `listener` role exists for the public app. The studio refuses any account without studio access, and `GET /api/me` says who you are and what you may do. The new app shows your name.
- An audit trail of sign-ins, failed sign-ins, sign-outs, password and passkey changes (who, what, when, from where, never a secret).

### Changed
- Sessions are in Postgres instead of `sessions.json` (existing sessions carry over, so the deploy does not sign you out), and each session has its own CSRF token instead of one for the whole server.
- The sign-in lockout (5 failures from one address, growing to 15 minutes) is in Postgres too, so it survives a restart. Your password, authenticator secret, passkeys and recovery codes stay in `auth.json` from Vault, out of database backups.

## [0.5.0] - 2026-10-16

### Added
- This changelog, and one version number across the plugin, the marketplace entry and the web app; the account menu in the new app shows it and the signed-in portal reports it. `deploy/bump-version.py` makes a release.
- A new app at `/app/` (React, Vite, TypeScript): Midnight Cinema and Ivory & Gold themes as data, glass panels with flat buttons, a mobile-first shell (sidebar and top bar on a desktop, header and floating tab bar on a phone), an account menu with the theme choice kept per device, and a Home screen on your real songs. The classic page stays at `/` and `/legacy` until every screen has moved over.

### Changed
- The sign-in page returns you to the page you asked for instead of always the classic page.

## [0.4.0] - 2026-10-15

### Added
- One structured JSON log for the whole app (web, pipeline and browser errors), a log per pipeline run, request ids on every reply, and a rule that no error is swallowed silently.
- Postgres as the database, in its own container with its own role: analytics moved over automatically at the first start, verified table by table, with the SQLite file kept as the rollback copy.
- The state of every song and inspiration (what `meta.json` held) in Postgres, with locked updates so the web page, the scheduler and a running step cannot overwrite each other; the scheduler claims a due step under that lock, so a post is published once. `meta.json` is still written as an export, and edits made to it outside the app are taken in.
- A job queue and a separate worker container: a run survives a deploy or a crash of the web server, an interrupted job is retried once, Stop works across processes, and the schedule runs in the worker.

### Changed
- Song and inspiration folders are local working data and are no longer tracked in git; media stays in the OCI bucket.
- The dev Postgres host port is configurable (`NAVAAN_PG_PORT`).

## [0.3.0] - 2026-10-15

### Added
- Music Short and Reel without a browser, with lyric captions on the reel; the reel is its own step and can be redone alone; watermark, reel fit and hook pick.
- Narration for inspiration shorts: upload a ready-made narration (audio plus subtitles), time lines from audio alone with Whisper, or have ElevenLabs speak it (voice choice, cache and cap).
- OpenAI pictures for inspiration shorts and for songs (director prompts, picture roles, cinematic look, matching people, 9:16), motion loops under the camera move, a Try the first 2 pictures card, a pictures-per-song setting with a run cap, and a Stop button.
- Restart Produce from a chosen step through the render.
- Gate switches in Settings, and media settings (voice, keys).

### Changed
- Faster: parallel speech recognition, a pre-blurred reel backdrop, an ffmpeg renderer for the Shots video and the reel (Remotion stays as the fallback), a cached caption-package check and media ETags (the song list went from about 2.3 s to 0.02 s).
- Instagram publishing on the server reads the OCI region from instance metadata; the song MP3 can be uploaded when Suno audio is unreadable.

### Fixed
- The song page no longer fails with `missing prompt_pack.json`; picture steps no longer repeat runs.

## [0.2.0] - 2026-10-13

### Added
- NAVAAN on the server: Docker deploy on the Oracle VM at `navaan.njlabs.dev`, secrets from Vault, nightly backup to the OCI bucket, and the server owning the publishing schedule.
- A release pipeline: CI on every pull request, deploy to production on a merge to `main` with an automatic roll back of the image when the health check fails.
- Sign-in with a password and authenticator code, passkeys alone, recovery codes, per-IP lockout, 7-day sessions that survive restarts; privacy and terms pages.
- Comment replies (Claude drafts, you approve and send each one) and best-time-to-publish suggestions for the schedule.

## [0.1.0]

### Added
- The studio plugin: lyrics, Suno song, visuals, synced captions, YouTube and Instagram publishing behind human approval gates, an analytics loop with recommendations, and a local web portal.

[Unreleased]: https://github.com/NjAIAgents/navaan/compare/v0.58.3...HEAD
[0.58.3]: https://github.com/NjAIAgents/navaan/compare/v0.58.2...v0.58.3
[0.58.2]: https://github.com/NjAIAgents/navaan/compare/v0.58.1...v0.58.2
[0.58.1]: https://github.com/NjAIAgents/navaan/compare/v0.58.0...v0.58.1
[0.58.0]: https://github.com/NjAIAgents/navaan/compare/v0.57.0...v0.58.0
[0.57.0]: https://github.com/NjAIAgents/navaan/compare/v0.56.5...v0.57.0
[0.56.5]: https://github.com/NjAIAgents/navaan/compare/v0.56.4...v0.56.5
[0.56.4]: https://github.com/NjAIAgents/navaan/compare/v0.56.3...v0.56.4
[0.56.3]: https://github.com/NjAIAgents/navaan/compare/v0.56.2...v0.56.3
[0.56.2]: https://github.com/NjAIAgents/navaan/compare/v0.56.1...v0.56.2
[0.56.1]: https://github.com/NjAIAgents/navaan/compare/v0.56.0...v0.56.1
[0.56.0]: https://github.com/NjAIAgents/navaan/compare/v0.55.1...v0.56.0
[0.55.1]: https://github.com/NjAIAgents/navaan/compare/v0.55.0...v0.55.1
[0.55.0]: https://github.com/NjAIAgents/navaan/compare/v0.54.0...v0.55.0
[0.54.0]: https://github.com/NjAIAgents/navaan/compare/v0.53.0...v0.54.0
[0.53.0]: https://github.com/NjAIAgents/navaan/compare/v0.52.0...v0.53.0
[0.52.0]: https://github.com/NjAIAgents/navaan/compare/v0.51.0...v0.52.0
[0.51.0]: https://github.com/NjAIAgents/navaan/compare/v0.50.0...v0.51.0
[0.50.0]: https://github.com/NjAIAgents/navaan/compare/v0.49.0...v0.50.0
[0.49.0]: https://github.com/NjAIAgents/navaan/compare/v0.48.0...v0.49.0
[0.48.0]: https://github.com/NjAIAgents/navaan/compare/v0.47.3...v0.48.0
[0.47.3]: https://github.com/NjAIAgents/navaan/compare/v0.47.2...v0.47.3
[0.47.2]: https://github.com/NjAIAgents/navaan/compare/v0.47.1...v0.47.2
[0.47.1]: https://github.com/NjAIAgents/navaan/compare/v0.47.0...v0.47.1
[0.47.0]: https://github.com/NjAIAgents/navaan/compare/v0.46.3...v0.47.0
[0.46.3]: https://github.com/NjAIAgents/navaan/compare/v0.46.2...v0.46.3
[0.46.2]: https://github.com/NjAIAgents/navaan/compare/v0.46.1...v0.46.2
[0.46.1]: https://github.com/NjAIAgents/navaan/compare/v0.46.0...v0.46.1
[0.46.0]: https://github.com/NjAIAgents/navaan/compare/v0.45.0...v0.46.0
[0.45.0]: https://github.com/NjAIAgents/navaan/compare/v0.44.0...v0.45.0
[0.44.0]: https://github.com/NjAIAgents/navaan/compare/v0.43.0...v0.44.0
[0.43.0]: https://github.com/NjAIAgents/navaan/compare/v0.42.0...v0.43.0
[0.42.0]: https://github.com/NjAIAgents/navaan/compare/v0.41.1...v0.42.0
[0.41.1]: https://github.com/NjAIAgents/navaan/compare/v0.41.0...v0.41.1
[0.41.0]: https://github.com/NjAIAgents/navaan/compare/v0.40.0...v0.41.0
[0.40.0]: https://github.com/NjAIAgents/navaan/compare/v0.39.0...v0.40.0
[0.39.0]: https://github.com/NjAIAgents/navaan/compare/v0.38.1...v0.39.0
[0.38.1]: https://github.com/NjAIAgents/navaan/compare/v0.38.0...v0.38.1
[0.38.0]: https://github.com/NjAIAgents/navaan/compare/v0.37.0...v0.38.0
[0.37.0]: https://github.com/NjAIAgents/navaan/compare/v0.36.1...v0.37.0
[0.36.1]: https://github.com/NjAIAgents/navaan/compare/v0.36.0...v0.36.1
[0.36.0]: https://github.com/NjAIAgents/navaan/compare/v0.35.1...v0.36.0
[0.35.1]: https://github.com/NjAIAgents/navaan/compare/v0.35.0...v0.35.1
[0.35.0]: https://github.com/NjAIAgents/navaan/compare/v0.34.0...v0.35.0
[0.34.0]: https://github.com/NjAIAgents/navaan/compare/v0.33.1...v0.34.0
[0.33.1]: https://github.com/NjAIAgents/navaan/compare/v0.33.0...v0.33.1
[0.33.0]: https://github.com/NjAIAgents/navaan/compare/v0.32.0...v0.33.0
[0.32.0]: https://github.com/NjAIAgents/navaan/compare/v0.31.0...v0.32.0
[0.31.0]: https://github.com/NjAIAgents/navaan/compare/v0.30.1...v0.31.0
[0.30.1]: https://github.com/NjAIAgents/navaan/compare/v0.30.0...v0.30.1
[0.30.0]: https://github.com/NjAIAgents/navaan/compare/v0.29.10...v0.30.0
[0.29.10]: https://github.com/NjAIAgents/navaan/compare/v0.29.9...v0.29.10
[0.29.9]: https://github.com/NjAIAgents/navaan/compare/v0.29.8...v0.29.9
[0.29.8]: https://github.com/NjAIAgents/navaan/compare/v0.29.7...v0.29.8
[0.29.7]: https://github.com/NjAIAgents/navaan/compare/v0.29.6...v0.29.7
[0.29.6]: https://github.com/NjAIAgents/navaan/compare/v0.29.5...v0.29.6
[0.29.5]: https://github.com/NjAIAgents/navaan/compare/v0.29.4...v0.29.5
[0.29.4]: https://github.com/NjAIAgents/navaan/compare/v0.29.3...v0.29.4
[0.29.3]: https://github.com/NjAIAgents/navaan/compare/v0.29.2...v0.29.3
[0.29.2]: https://github.com/NjAIAgents/navaan/compare/v0.29.1...v0.29.2
[0.29.1]: https://github.com/NjAIAgents/navaan/compare/v0.29.0...v0.29.1
[0.29.0]: https://github.com/NjAIAgents/navaan/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/NjAIAgents/navaan/compare/v0.27.0...v0.28.0
[0.27.0]: https://github.com/NjAIAgents/navaan/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/NjAIAgents/navaan/compare/v0.25.1...v0.26.0
[0.25.1]: https://github.com/NjAIAgents/navaan/compare/v0.25.0...v0.25.1
[0.25.0]: https://github.com/NjAIAgents/navaan/compare/v0.24.1...v0.25.0
[0.24.1]: https://github.com/NjAIAgents/navaan/compare/v0.24.0...v0.24.1
[0.24.0]: https://github.com/NjAIAgents/navaan/compare/v0.23.0...v0.24.0
[0.23.0]: https://github.com/NjAIAgents/navaan/compare/v0.22.0...v0.23.0
[0.22.0]: https://github.com/NjAIAgents/navaan/compare/v0.21.0...v0.22.0
[0.21.0]: https://github.com/NjAIAgents/navaan/compare/v0.20.0...v0.21.0
[0.20.0]: https://github.com/NjAIAgents/navaan/compare/v0.19.0...v0.20.0
[0.19.0]: https://github.com/NjAIAgents/navaan/compare/v0.18.1...v0.19.0
[0.18.1]: https://github.com/NjAIAgents/navaan/compare/v0.18.0...v0.18.1
[0.18.0]: https://github.com/NjAIAgents/navaan/compare/v0.17.1...v0.18.0
[0.17.1]: https://github.com/NjAIAgents/navaan/compare/v0.17.0...v0.17.1
[0.17.0]: https://github.com/NjAIAgents/navaan/compare/v0.16.0...v0.17.0
[0.16.0]: https://github.com/NjAIAgents/navaan/compare/v0.15.1...v0.16.0
[0.15.1]: https://github.com/NjAIAgents/navaan/compare/v0.15.0...v0.15.1
[0.15.0]: https://github.com/NjAIAgents/navaan/compare/v0.14.0...v0.15.0
[0.14.0]: https://github.com/NjAIAgents/navaan/compare/v0.13.0...v0.14.0
[0.13.0]: https://github.com/NjAIAgents/navaan/compare/v0.12.1...v0.13.0
[0.12.1]: https://github.com/NjAIAgents/navaan/compare/v0.12.0...v0.12.1
[0.12.0]: https://github.com/NjAIAgents/navaan/compare/v0.11.0...v0.12.0
[0.11.0]: https://github.com/NjAIAgents/navaan/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/NjAIAgents/navaan/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/NjAIAgents/navaan/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/NjAIAgents/navaan/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/NjAIAgents/navaan/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/NjAIAgents/navaan/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/NjAIAgents/navaan/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/NjAIAgents/navaan/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/NjAIAgents/navaan/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/NjAIAgents/navaan/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/NjAIAgents/navaan/releases/tag/v0.1.0
