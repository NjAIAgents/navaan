# Changelog

All notable changes to NAVAAN Studio are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/) (0.y.z until the public listener app exists).
The version lives in `plugins/navaan-studio/.claude-plugin/plugin.json` and is mirrored in `.claude-plugin/marketplace.json` and `plugins/navaan-studio/web/package.json`; a test keeps them and this file in step.
Release steps are in `deploy/README.md` (Releasing). Only changes a person using or running the studio would notice are listed; refactors, tests and docs-only edits are in the git history.

## [Unreleased]

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

[Unreleased]: https://github.com/NjAIAgents/navaan/compare/v0.29.2...HEAD
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
