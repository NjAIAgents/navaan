# Feature Specification: NAVAAN platform foundation (listeners, playlists, subscriptions, one database)

**Feature Branch**: `002-platform-foundation` (no git branch created yet; the spec directory carries the number)

**Created**: 2026-10-15

**Status**: Draft. Direction and four decisions agreed with Nj on 2026-10-15 (see Clarifications). Constitution 2.0.0 applies.

**Input**: User description: "Build something like Spotify: users create accounts and playlists, maybe a subscription later. The groundwork has to be solid: proper schema and data structure, and move from SQLite to Postgres. The site must be mobile friendly, look like an enterprise media platform, and have animation, better image rendering and albums. Studio holds all the pipeline work (songs, inspiration, later podcasts, analytics); Library and Albums show finished work. Google and Apple sign-in come later. Roles and the public/studio split come later."

**Relationship to other specs**: Supersedes `001-run-navaan-on-server` where it says the owner is the only user (Assumptions) and that studio and analytics data stay in the file database (FR-019). Everything else in 001 still holds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One reliable database for everything (Priority: P1)

The owner's analytics history and all song/pipeline state live in one database that several parts of the system can use at once without overwriting each other. Nothing is lost in the move, and the owner can see the same numbers and songs as before.

**Why this priority**: Everything else (users, playlists, subscriptions) needs a safe place to keep data, and today song state is in loose files that the scheduler and the web page can overwrite at the same time.

**Independent Test**: After the move, compare counts and totals for every analytics table and every song against the old data; run the scheduler twice at once and confirm each item publishes once.

**Acceptance Scenarios**:

1. **Given** the current analytics data, **When** it is moved, **Then** every table's row count and checks match the old data and the analytics pages show the same numbers.
2. **Given** the current songs, **When** their state is moved, **Then** every approval, schedule, history line and publish record is present and the pipeline continues from where it was.
3. **Given** two scheduler runs at the same moment, **When** a post is due, **Then** it is published exactly once.
4. **Given** a server loss, **When** the owner restores from backup, **Then** the full data set is back in under 1 hour.

---

### User Story 2 - Studio is organised by what you are making (Priority: P1)

The owner finds all production work under a Studio area split by kind of content: Songs, Inspiration, and later Podcasts, with one Approvals queue, one Schedule and Analytics. Finished work appears in Library and Albums. On a phone, everything the owner needs on the go (approving, scheduling, checking numbers) works in a few taps.

**Why this priority**: The current screens are hard to traverse and unusable on a phone; this is the owner's own daily tool and the first thing to prove the new design.

**Independent Test**: On a 390 px wide phone and on a laptop, approve a waiting item from the Approvals queue in two taps or fewer, schedule it, and find it in Library after it is published.

**Acceptance Scenarios**:

1. **Given** items waiting on the owner, **When** the owner opens Home or Approvals, **Then** all of them are in one list and each can be approved or reviewed from there.
2. **Given** a phone, **When** the owner uses any studio screen, **Then** navigation is reachable with the thumb, nothing scrolls sideways, and buttons are easy to hit.
3. **Given** an item is published, **When** the owner opens Library, **Then** it appears there with its cover, and Studio keeps its history.
4. **Given** a new kind of content (Podcasts) is added later, **When** it is registered, **Then** it gets its own Studio section, Library filter and queue without redoing the navigation.
5. **Given** either theme is chosen, **When** any screen is shown, **Then** it is readable and consistent in dark and light.

---

### User Story 3 - Albums as real releases (Priority: P2)

The owner groups songs into an album or EP with a name, cover, description, release date and a chosen track order, and publishes or schedules the release as a whole.

**Why this priority**: Albums are how listeners will browse; today an album is only a text label on a song.

**Independent Test**: Create an album from three songs, reorder them, set a cover, and see the order and cover in Albums and on the album page.

**Acceptance Scenarios**:

1. **Given** published and unpublished songs, **When** the owner builds an album, **Then** the tracklist order is saved and shown everywhere the album appears.
2. **Given** an album with an unfinished song, **When** the owner views it, **Then** it shows as a draft with the unfinished song marked.
3. **Given** songs that already carry an album name, **When** the move completes, **Then** matching albums exist with those songs in them.

---

### User Story 4 - Listeners create accounts and playlists (Priority: P2)

A listener signs up with email and password (Google and Apple sign-in come later), verifies the email, browses published songs and albums, plays them, saves favourites and builds playlists. A listener can see, change and delete only their own data.

**Why this priority**: This is the product direction, but it needs stories 1 and the access rules in place before it is safe to open.

**Independent Test**: Create two listener accounts; each makes a playlist; confirm neither can see or change the other's playlist, and that a listener cannot reach any studio screen or data.

**Acceptance Scenarios**:

1. **Given** a visitor, **When** they sign up and verify their email, **Then** they get a free account and land on the listener home.
2. **Given** a listener, **When** they create a playlist and add songs, **Then** the order is kept and the playlist is private unless they share it.
3. **Given** two listeners, **When** one asks for the other's private data by any route, **Then** the request is refused.
4. **Given** a listener, **When** they ask to export or delete their account, **Then** it is done and their playlists and history are removed.
5. **Given** repeated failed sign-ins or sign-up bursts, **When** limits are hit, **Then** the offender is slowed or locked without locking out other people.
6. **Given** a listener, **When** they try any studio address, **Then** they see no studio content.

---

### User Story 5 - Plans and limits without a payment provider (Priority: P3)

The system knows which plan each listener is on (everyone is on Free for now) and which features and limits each plan has, such as how many playlists. Changing what a plan includes needs no code change in the screens that use it. A Plans page shows what Free and Premium would offer; Premium cannot be bought yet.

**Why this priority**: It lays the groundwork for a subscription later without building payments now.

**Independent Test**: Set the Free playlist limit to 3, create a fourth playlist and see a clear upgrade message; raise the limit in the plan data and confirm the fourth is allowed without redeploying screens.

**Acceptance Scenarios**:

1. **Given** a new listener, **When** their account is created, **Then** they are on the Free plan.
2. **Given** a limit on a plan, **When** the listener reaches it, **Then** they see what the limit is and what a higher plan would give.
3. **Given** the owner grants a listener a temporary exception, **When** it is active, **Then** it applies and expires on its date.

---

### User Story 6 - Listening that works well on a phone (Priority: P3)

Songs start quickly and keep playing, with covers that appear smoothly (a soft colour first, then the sharp image), a mini-player that stays at hand, and no loading of huge images on a small screen.

**Why this priority**: It sets the quality bar for the listener experience but depends on stories 1 to 4. It also covers lyrics, play mode and sharing.

**Independent Test**: On a throttled phone connection, open an album and start a track; the page is usable before images finish, and the audio starts in a few seconds.

**Acceptance Scenarios**:

1. **Given** a listener on a slow connection, **When** an album page opens, **Then** colour placeholders show at once and sharpen as images arrive.
2. **Given** a track is played, **When** the listener is entitled to it, **Then** it streams and can be skipped forward; **When** not entitled, **Then** a clear message appears.
3. **Given** a song archived from the studio's disk, **When** a listener plays it, **Then** it still plays.
4. **Given** a song page or play mode, **When** the song has timed lyrics, **Then** the current line is highlighted as it plays; **When** it has plain lyrics only, **Then** they are shown without highlighting.
5. **Given** a song, **When** a listener chooses Share and copies the link, **Then** a link is created (optionally starting at the current time), and a visitor without an account who opens it hears a preview and is invited to sign in.
6. **Given** a shared link, **When** its owner revokes it, **Then** it stops working.

---

### Edge Cases

- A migration fails halfway: the old data is untouched and the system keeps working on the old store.
- The release is rolled back after a database change: the earlier release still works with the new schema.
- Two people edit the same playlist at the same moment: both edits are kept in a sensible order.
- A listener deletes their account while a track is playing: playback ends and no data remains.
- A song's rights are unconfirmed: it is not placed behind a subscription.
- Email cannot be delivered: sign-up says so and offers to resend; it does not create a verified account.
- A very old phone without modern image formats: a plain format is served.
- A user has reduced-motion turned on: no animation plays.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: All durable data (analytics, song and pipeline state, users, catalog, playlists, plans) MUST live in one relational database, with every change applied through versioned migrations.
- **FR-002**: Moving existing data MUST be verifiable (row counts and checks per table), repeatable, and leave the old data in place until the owner confirms.
- **FR-003**: The scheduler MUST publish each item at most once even when more than one instance runs.
- **FR-004**: The database MUST be backed up daily to the existing cloud storage, and a restore MUST be tested before cutover and after any change to the backup.
- **FR-005**: The studio MUST present Home, Studio (Songs, Inspiration, Approvals, Schedule, Analytics, and Podcasts as "coming soon"), Library and Albums in its navigation, with Settings (accounts, connections, cloud storage), profile, plan, appearance and sign out in a user menu opened from the avatar, and one search/jump box on every screen.
- **FR-006**: Items waiting for approval MUST appear in a single queue where each can be reviewed and approved; routine approvals MUST be undoable for a short time instead of asking for confirmation, while credit-spending and go-public approvals keep an explicit confirmation.
- **FR-007**: Every screen MUST work from 360 px wide upward without sideways scrolling, with touch targets of at least 44 px, readable text, visible keyboard focus, and dark and light themes.
- **FR-022**: Appearance MUST be defined by named themes made of design tokens (colours, surfaces, material such as blur, depth); adding or changing a theme MUST NOT require changing any screen; dark and light themes MUST ship; the listener's choice MUST be remembered and applied before the first paint.
- **FR-028**: A user MUST be able to build a full profile from the user menu: display name and picture, languages, genres, moods and interests. This taste data is personal, is used only to personalise what that user sees, can be switched off, and is included in the user's data export and removed on account deletion.
- **FR-029**: A user MUST be able to personalise appearance with a dark-to-light slider and an accent palette (or follow the device setting); the choice is saved to the account, applied before the first paint, and text, buttons and status colours MUST keep at least 4.5:1 contrast at every slider position and every accent.
- **FR-030**: Search MUST find songs, albums, playlists and shorts when the user types Devanagari or the same words in Roman letters (for example "tere hone se"), tolerates small typos and accent differences, and answers from one search interface that can be replaced by another engine without changing the screens.
- **FR-031**: Long-running and scheduled work (rendering, publishing, collecting analytics, sending email) MUST run in a separate worker that survives restarts, retries a bounded number of times, and never performs the same job twice.
- **FR-032**: Before the listener side is opened to the public, the system MUST have tested point-in-time recovery of the database, error tracking that alerts the owner, and an uptime check on both host names.
- **FR-033**: An item's release pipeline (song or inspiration short) MUST be shown as phases with plain-language steps (no internal step names), each step marked as done, running, waiting on the owner, or locked; each step tagged when it is automatic, written by Claude, needs the Mac, or spends credits; finished phases collapse; locked steps say which decision unlocks them; steps that change visibility or spend credits ask for an explicit confirmation; and a board shows every item by stage (draft, in production, needs you, scheduled, published).
- **FR-034**: The application MUST write one consolidated, structured log stream (one JSON record per event) covering the web servers, the worker and every pipeline run, with a timestamp in UTC, level, service, component, event name, a request or job identifier, the item and step when relevant, duration, and for errors the type and stack; a pipeline run MUST also be readable as one continuous log, not only as small per-step files; logs MUST be rotated and kept for at least 14 days; the format and labels MUST be ready to ship to a log service such as Loki without code changes.
- **FR-035**: No error may be swallowed: every caught exception in the server, worker and browser MUST either be handled and logged or be marked as deliberately ignored with a reason; errors in the browser (uncaught errors, failed requests, unhandled promise rejections) MUST be reported to the server and logged with the page, user id and request id; secrets, tokens, passwords, email addresses and full query strings MUST NOT appear in logs.
- **FR-036**: Studio Analytics MUST be split into three tabs: Analytics (numbers, trends, best times, top posts), Recommendations (suggested actions each with its evidence, sample size and confidence; applying one only prepares an item for the owner to approve), and Interactions (comments and mentions from the audience with category, sentiment and language, a draft reply written for the owner, and actions to send, edit, hide or mark done, plus reply-time and reply-rate figures); no reply is ever sent without the owner pressing send.
- **FR-023**: A reviewer MUST be able to send an item back with a note instead of approving it; this re-opens the step that produced it, keeps the note in the item's history, and never counts as an approval.
- **FR-024**: A song page and a full-screen play mode MUST show the song's lyrics (plain, or highlighted line by line when timing exists); the large cinematic artwork treatment is used only there, not on Studio screens or the listener home.
- **FR-025**: A listener MUST be able to share a song, album or playlist as a link from its page, its play mode and its menu, optionally starting at the current moment; anyone with a link to a published song can hear a short preview and sees a branded preview card when the link is pasted into a chat, signing in plays the full song; the owner of a link can revoke it; private playlists cannot be shared unless the listener makes them shareable.
- **FR-008**: Albums MUST have name, cover, description, release date, kind (album, EP, single), status, and an ordered tracklist; existing album labels MUST be carried over.
- **FR-009**: Cover images MUST be served in several sizes with a colour placeholder, cached by the browser, and available even after the studio's local copy is archived.
- **FR-010**: A visitor MUST be able to create a listener account with email and password, verify the email, reset a forgotten password, and sign in; signing in with other providers MUST be addable later without changing existing accounts.
- **FR-011**: Every route MUST declare the permission it needs and be checked on the server; listener roles MUST have no access to studio data or actions.
- **FR-012**: A listener MUST be able to create, rename, reorder, share and delete playlists, save songs and albums, and follow the artist; each listener MUST see only their own private data.
- **FR-013**: A listener MUST be able to export and delete their account.
- **FR-014**: Failed sign-ins, sign-ups and password resets MUST be rate limited per account and per network address.
- **FR-015**: The system MUST record each listener's plan and decide features and limits through a single check; every new listener MUST start on the Free plan; changes to what a plan includes MUST NOT require changing the screens that use it.
- **FR-016**: Audio MUST be delivered to entitled listeners through short-lived links that expire, without the audio passing through the application server.
- **FR-017**: Every track MUST carry a recorded origin and licence status, and a track with an unconfirmed status MUST NOT be offered behind a subscription.
- **FR-018**: Every catalog and studio record MUST carry its owning artist so more artists can be added later without changing the data layout.
- **FR-019**: Plays MUST be recorded per listener and track for history and statistics, with old detail removed after a retention period.
- **FR-020**: The existing owner login (password, authenticator, passkeys, recovery codes) MUST keep working and become the owner role.
- **FR-021**: No payment details are stored, and no payment provider is required for this feature.

### Key Entities

- **User**: a person with an account; has credentials, linked sign-in providers (none yet), roles and a plan.
- **Role and permission**: what a user may do; owner, editor and listener to start.
- **Artist**: the tenant that owns catalog and studio records; NAVAAN is the only one now.
- **Item**: a piece of content being made in the studio (song, inspiration short, later podcast) with its steps, approvals, schedule and history.
- **Track, Album, Asset**: a published piece of music, a release that orders tracks, and the files (audio, cover, video) with sizes and placeholders.
- **Playlist**: a listener's ordered list of tracks with a visibility setting.
- **Plan, Entitlement, Subscription**: what a plan includes, a named limit or feature, and a listener's plan with its status and dates.
- **Play event**: one listen by one listener.
- **Analytics record**: the existing Instagram and YouTube history, now owned by an artist.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After the move, 100% of analytics rows and 100% of songs, approvals and schedules match the old data in an automated comparison.
- **SC-002**: Two simultaneous scheduler runs publish a due item once in 100% of 100 trials.
- **SC-003**: A full restore from backup onto a clean server completes in under 1 hour.
- **SC-004**: On a 390 px screen, approving a waiting item takes two taps or fewer from Home, and no studio screen scrolls sideways.
- **SC-005**: In an automated check, 100% of attempts by one listener to read or change another listener's data, or any studio data, are refused.
- **SC-006**: An album page is usable (colour placeholders shown) within 1 second on a throttled mobile connection and a track starts within 3 seconds after pressing play.
- **SC-007**: Accessibility checks report zero serious violations on Home, a song workspace, Library, an album and the sign-up page; mobile performance score is at least 90 on Home and an album.
- **SC-008**: Changing a plan's playlist limit takes effect without changing or redeploying any screen.
- **SC-011**: An automated check samples every slider position with every accent in both modes and finds zero body-text, button-label or status-colour contrast below 4.5:1 (3:1 for large text).
- **SC-012**: On a catalog of 10,000 tracks, searching "tere hone se" returns "तेरे होने से" in the first three results, and the 95th-percentile search time is under 200 ms.
- **SC-013**: A job interrupted by a restart is resumed or retried exactly once, and a duplicate trigger runs it once, in an automated test.
- **SC-014**: An automated check finds zero empty `except` or `catch` handlers without a written reason and a debug log; a deliberately raised error in each component (web server, worker, a pipeline step, the browser) produces exactly one log record containing its request or job id; a scan of a full day of test logs finds no secret, token or email address.
- **SC-010**: A new theme is added by creating one theme file and one list entry, with no change to any screen, and a build check finds zero colour literals outside theme files.
- **SC-009**: The earlier release keeps working after the new release's migrations are applied, in a rollback rehearsal.

## Assumptions

- Target load at launch is 1 to 100 live users; growth later. Search, background jobs and recommendations start inside the existing database and move to separate services only when the triggers in the plan are hit.

- Nj remains the owner and only studio user at the start; more studio roles come with the role work.
- Artists other than NAVAAN are not onboarded in this feature; only the data layout allows for them.
- Payments, tax and invoicing are out of scope; a payment provider is chosen later and attaches to the plan records.
- Google and Apple sign-in, in-app purchases, music-service pre-save, a separate listener hostname, offline listening, adaptive streaming, ads and collaborative playlists are later features.
- An email-sending service will be chosen before listener sign-up is opened; the sending domain is `navaan.online`.
- Owner passkeys are tied to the host name they were registered on, so moving the studio to a new host means registering them again (the authenticator app and recovery codes keep working).
- The listener side is not opened to the public until its security review is done.
- The server has enough memory and disk for the database next to the application (to be confirmed).
- Rights to commercially use generated songs are checked by Nj before any song goes behind a subscription.
- Owner decision 2026-10-16 (NAV-11): every song in NAVAAN at this date was generated on a paid Suno plan. Each existing track is recorded with `license_status = confirmed`, plan `paid` and this note; the owner stays responsible for reading Suno's terms (not legal advice). Songs added later start `unconfirmed` and the plan tier is recorded at import from `suno.plan` in `navaan.config.json`; the owner confirms them one by one.

- **FR-026**: The listener site MUST be served on the domain `navaan.online` (and `www.navaan.online` redirecting to it) over valid, automatically renewed secure connections; the studio MUST be served on a separate host name so listener and studio sessions never share cookies; shared links use `navaan.online`. The studio host is `studio.navaan.online`; `navaan.online` serves all public pages (songs, albums, playlists, share links, listener sign-up).
- **FR-027**: Email sent to listeners (verification, password reset) MUST come from the `navaan.online` domain with sender authentication in place (SPF, DKIM, DMARC) so it is delivered.

## Clarifications

### Session 2026-10-15

- Q: Who adds music? -> A: NAVAAN only now, artists later (data layout ready, FR-018).
- Q: Where does the database run? -> A: A container on the existing VM with daily backup to cloud storage (FR-004).
- Q: How far does billing go now? -> A: Plans and limits only, no payment provider (FR-015, FR-021).
- Q: Which screens move to Studio? -> A: All pipeline work, including Analytics; Library and Albums stay outside (FR-005).
- Q: Sign-in providers? -> A: Email and password now; Google and Apple later (FR-010).
- Q: Roles and public/studio split? -> A: Later; the data and permission checks are built now (FR-011).
- Q: Domain? -> A: `navaan.online` was bought on 2026-10-15 for the listener site and shared links. Confirmed by Nj on 2026-10-15: studio at `studio.navaan.online`; everything public (songs, albums, playlists, share links, listener sign-up) at `navaan.online`; `navaan.njlabs.dev` keeps working during a transition period and then redirects to the studio host.
- Q: Profile and personalisation? -> A: Full profile (languages, genres, moods, interests) and appearance (dark-to-light slider, accent palette, match device) live in the user menu (FR-028, FR-029).
- Q: Logging? -> A: One consolidated structured log stream (JSON lines on stdout plus a rotated file), a continuous per-run log for pipeline jobs, browser errors reported to the server, and no silent catch; shipping to Loki (or similar) comes later and needs no code change (FR-034, FR-035).
- Q: Technology direction for scale? -> A: Keep Postgres for search (full-text, trigram, unaccent, Roman transliteration column), add pgvector later for semantic features, move the listener API to FastAPI with uvicorn, run a Postgres-backed worker, put Cloudflare's free tier in front of the public site, and add point-in-time recovery, error tracking and an uptime check before opening to listeners. No Elasticsearch, ClickHouse, Kubernetes or second server now (FR-030, FR-031, FR-032).
- Q: Visual direction? -> A: "Midnight Cinema" (navy, moonlit gold, ember, ivory) and "Ivory & Gold" light, with soft glass on top; Studio stays slim, cinematic hero only on the listener song page and play mode (FR-022, FR-024).
- Q: Typography? -> A: Cormorant Garamond for titles with Noto Serif Devanagari, Manrope for the interface with Noto Sans Devanagari, because titles and lyrics are Hindi and Maithili.
- Q: Out of scope from the supplied concept? -> A: Spotify pre-save, TikTok and Spotify icons, and "Restore purchase"; the menu structure stays as decided (Analytics inside Studio).
- Q: Request changes? -> A: Yes, next to Approve (FR-023).
- Q: Sharing? -> A: Link sharing for songs, albums and playlists with preview (FR-025).
