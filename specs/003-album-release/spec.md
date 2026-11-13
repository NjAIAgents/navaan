# Feature Specification: Album release

**Feature Branch**: `feat/003-album-release`

**Created**: 2026-11-13

**Status**: Draft

**Input**: User description: "Album release for NAVAAN Studio. Release means a song's full version going public: the full YouTube video becomes public and the track appears on navaan.online. A song cannot be released on its own; only an album can be released, and releasing an album releases every song in it. Release button with confirm, scheduled release, promotion with clips before release, an album coming-soon page, later a teaser drip."

## Definitions

- **Release**: the full version of a song becomes public everywhere it lives: the full YouTube video is public and the track is listed and playable on navaan.online.
- **Album**: a release unit of kind album, EP or single, with an ordered list of songs. Only an album can be released.
- **Teaser clip**: a short cut of a song (30 to 60 seconds, never the full song) posted as a YouTube Short or an Instagram Reel to promote it.
- **Held**: a song whose pipeline has finished everything except going public, waiting for its album's release.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Songs wait for their album (Priority: P1)

The owner finishes a song (lyrics, audio, video, uploads). Because the song belongs to an album, its full version is not made public. The song shows "Waiting for album release" with the album's name, the full video stays private on YouTube, and the song is not on navaan.online. There is no way to release the song by itself.

**Why this priority**: Without the hold, a finished song goes public on its own and the album launch is spoiled. Everything else builds on this.

**Independent Test**: Put a song in an unreleased album, run its pipeline to the end, and check that the full video is still private, the song is absent from navaan.online, and Studio offers no per-song release action.

**Acceptance Scenarios**:

1. **Given** a song in an unreleased album with every gate before going public approved, **When** its pipeline runs to the end, **Then** it stops at going public with "Waiting for album release: <album>", the full YouTube video is private, and the song does not appear on navaan.online (search, album page, direct link).
2. **Given** a held song, **When** the owner looks at the song in Studio, **Then** no control releases the song alone; the page links to its album's release controls.
3. **Given** a finished song that is in no album, **When** its pipeline reaches going public, **Then** it is held with "Add this song to an album to release it".
4. **Given** a song that was already public before this feature, **When** this feature ships, **Then** it stays public and unchanged.

---

### User Story 2 - Release an album now (Priority: P1)

The owner opens an album in Studio and presses Release. A confirmation shows the album, every song, where each goes public (YouTube, navaan.online), and that this cannot be easily undone. On confirm, the album and all its songs go public together. Studio shows each song's progress (public on YouTube, live on navaan.online, retrying, failed).

**Why this priority**: This is the only way any song goes public under the new rule.

**Independent Test**: With an album of two held songs, press Release, confirm, and check both full videos are public, the album and both tracks are on navaan.online, and the history notes the release by the owner.

**Acceptance Scenarios**:

1. **Given** an album whose songs are all held and ready, **When** the owner presses Release and confirms, **Then** the album and every song in it appear on navaan.online at the same moment, each song's full YouTube video is made public, and each song's history says "released with <album>".
2. **Given** the confirmation is open, **When** the owner cancels, **Then** nothing changes.
3. **Given** an album where one song is not ready (its full video is not uploaded or a gate before going public is not approved), **When** the owner opens Release, **Then** Release is blocked and the list names each song that is not ready and why.
4. **Given** a release in progress, **When** making one song's YouTube video public fails, **Then** it is retried up to 3 times, 10 minutes apart; the album and the other songs stay released; the failed song is shown as failed with the reason and a Retry control after the last try.
5. **Given** an album with no songs, **When** the owner opens Release, **Then** Release is blocked with "Add at least one song".

---

### User Story 3 - Schedule an album release (Priority: P2)

The owner sets a release date and time for an album and arms it. At that time the album is released exactly as in User Story 2, without anyone pressing a button then. Before the time, the album shows "Scheduled for <date time>" and can be rescheduled or cancelled.

**Why this priority**: Releases are timed for the audience; the owner should not have to be at the computer.

**Independent Test**: Schedule an album a few minutes ahead, wait, and check it releases at that time with the same result as a manual release.

**Acceptance Scenarios**:

1. **Given** an album with all songs ready, **When** the owner sets a release time and confirms (the same confirmation as Release, showing the time), **Then** the album shows "Scheduled for <time>" in the owner's local time.
2. **Given** a scheduled album, **When** the time comes, **Then** it is released as in User Story 2 and its history says "released on schedule".
3. **Given** a scheduled album where a song is not ready at the time, **When** the time comes, **Then** nothing is released, the album waits and retries when the song becomes ready, up to 12 hours late, then it is marked "missed" and the owner is told.
4. **Given** a scheduled album, **When** the owner cancels the schedule or changes the time, **Then** the old time no longer releases anything.
5. **Given** a song added to or removed from a scheduled album, **When** the change is saved, **Then** the schedule is disarmed and the owner must confirm again (the confirmed song list changed).

---

### User Story 4 - Promote with clips before release (Priority: P2)

Before the album is out, the owner posts teaser clips of its songs as YouTube Shorts and Instagram Reels. Their captions say when the song is out and on which album, and they link to the album's page on navaan.online, not to the song (which is not public yet). Posting a clip never makes the full song public.

**Why this priority**: Promotion before release is how the audience learns the album is coming.

**Independent Test**: For a held song, publish its Short and Reel; check both are public, captions carry the album name and date and the album link, and the full video is still private.

**Acceptance Scenarios**:

1. **Given** a held song in an album with a release date, **When** its Short or Reel is published, **Then** the caption includes "Out <date> · <album>" and the album page link, and the full video stays private.
2. **Given** a held song in an album with no release date yet, **When** a clip is published, **Then** the caption says "Coming soon · <album>" with the album page link.
3. **Given** a teaser clip, **When** it is made, **Then** it is between 30 and 60 seconds and shorter than the full song.
4. **Given** the album is later released, **When** someone opens the album link from an old clip, **Then** they land on the released album with the full songs.
5. **Given** a held song, **When** the owner publishes teasers, **Then** both a YouTube Short and an Instagram Reel may go public before release (owner, 2026-11-13).

---

### User Story 5 - Album coming-soon page (Priority: P3)

Before release, the album has a public page on navaan.online: cover, title, kind, release date with a countdown (or "Coming soon" when no date), and its teaser clips. Full songs are not listed or playable. On release the same address becomes the normal album page.

**Why this priority**: Clips need somewhere to point; useful but the release works without it.

**Independent Test**: Open the address of an unreleased album with a date; check cover, title, countdown and clips are shown and no full song can be played or found.

**Acceptance Scenarios**:

1. **Given** an unreleased album the owner has marked "announced", **When** a listener opens its address, **Then** they see cover, title, release date and countdown, and teaser clips; no song titles link to full tracks and no full audio plays.
2. **Given** an unreleased album not announced, **When** its address is opened, **Then** it is not found, as today.
3. **Given** the countdown reaches zero before the release has completed, **When** the page is open, **Then** it shows "Releasing now" rather than a negative or broken countdown.

---

### User Story 6 - Teaser drip (Priority: P4, later)

The owner picks how many clips per song and a window before the release; the clips are spread over the weeks before the release time using the existing publishing schedule and best-time slots. Each clip still needs its approvals.

**Why this priority**: Saves manual scheduling; optional and can follow later.

**Independent Test**: For an album with a release date three weeks out, set two clips per song; check the proposed times all fall before the release and on suggested slots, and nothing posts without its approvals.

**Acceptance Scenarios**:

1. **Given** an album with a release time, **When** the owner sets a drip plan, **Then** proposed clip times are shown, all before the release, and the owner accepts or edits them.
2. **Given** an accepted drip, **When** a clip's approval is missing at its time, **Then** it waits as scheduled posts do today, and never posts after the release time as a teaser.

---

### Edge Cases

- A song is in two albums: it is released by whichever album is released first; the other album shows it as already released.
- The owner removes a song from an album after the album is released: the song stays public (release is not undone by editing).
- Unreleasing: out of scope; making something private again stays a manual action per platform.
- A song's audio or video changes after its gates were approved: approvals tied to the content become invalid (constitution III) and the song is no longer ready.
- The worker or server is down at the scheduled time: the release runs when it comes back, within the 12-hour window, otherwise it is missed and the owner is told.
- YouTube reports the video as already public (made public by hand): treated as done, not as a failure.
- An album of kind single: it holds exactly one song and is released like any album.
- Release time: one time for the album; YouTube and navaan.online go public together, no per-platform times (owner, 2026-11-13).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A song MUST NOT become public in full (full YouTube video public, or listed on navaan.online) except through the release of an album that contains it.
- **FR-002**: A song's pipeline MUST run every step except going public, then hold it with a visible reason naming its album (or saying it needs one).
- **FR-003**: Studio MUST NOT offer any control that releases a single song on its own; Studio's existing go-public approval for a song in an album MUST be replaced by the album's release.
- **FR-004**: An album MUST have one of the states: draft, announced, scheduled, releasing, released, missed.
- **FR-005**: The owner MUST be able to release an album now, after a confirmation listing every song, each platform it goes public on, and that it is hard to undo.
- **FR-006**: Release MUST be blocked, with a per-song reason, while any song is not ready (full video not uploaded, an earlier gate not approved, content changed since approval) or the album has no songs.
- **FR-007**: On release, the album and all its songs MUST appear on navaan.online at the same moment (all or none), and each song's full YouTube video MUST be made public.
- **FR-008**: A failed platform step for a song MUST be retried up to 3 times, 10 minutes apart, without undoing the album or other songs; after the last failure the owner MUST see the reason and a Retry control.
- **FR-009**: Studio MUST show each song's release progress per platform: waiting, public, retrying, failed.
- **FR-010**: The owner MUST be able to schedule an album release at a date and time, after the same confirmation; reschedule and cancel MUST be possible until it starts.
- **FR-011**: A scheduled release MUST run without anyone present; if a song is not ready at the time, the release MUST wait up to 12 hours, then be marked missed and the owner told.
- **FR-012**: Changing a scheduled album's song list MUST disarm the schedule until the owner confirms again.
- **FR-013**: Scheduling MUST NOT approve any gate; the release confirmation is the owner's approval for every song's going public, recorded per song as "released with <album>" by the owner.
- **FR-014**: Teaser clips (Shorts, Reels) of a held song MUST be publishable before release, MUST be 30 to 60 seconds and shorter than the full song, and MUST NOT make the full song public.
- **FR-015**: A teaser clip's caption MUST carry "Out <date> · <album>" (or "Coming soon · <album>" without a date) and the album page link instead of a song link.
- **FR-016**: An announced, unreleased album MUST have a public page with cover, title, kind, release date and countdown (or "Coming soon") and its teaser clips, and MUST NOT list, play or link to the full songs.
- **FR-017**: The album address MUST stay the same before and after release.
- **FR-018**: Songs already public when this feature ships MUST remain public; songs not yet public and not in an album become held.
- **FR-019**: Every release action (confirm, schedule, reschedule, cancel, start, each song's per-platform result, missed) MUST leave a history line with who or what did it.
- **FR-020**: (Later, P4) The owner MUST be able to plan a teaser drip: clips per song and a window before release, placed on suggested time slots, each clip still needing its approvals, none posted as a teaser after release.

### Key Entities

- **Album**: title, kind (album, EP, single), ordered songs, cover, description, state, release time (optional), announced flag, history.
- **Song (track)**: belongs to zero or more albums; held, released, or public from before this feature; per-platform public state.
- **Release**: one per album: who confirmed it, when, the confirmed song list, scheduled or immediate, per-song per-platform outcome and retries.
- **Teaser clip**: song, platform, length, caption, link target (the album), posted time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No song's full version becomes public without its album's release: across all songs in albums, 0 full videos public and 0 tracks listed on navaan.online before their album's release.
- **SC-002**: The owner releases a whole album in under 1 minute of their own time (open, review, confirm).
- **SC-003**: After a release, every song is live on navaan.online at the same moment as the album, and every full YouTube video is public within 15 minutes, barring platform outages.
- **SC-004**: A scheduled release starts within 2 minutes of its time when the server is up.
- **SC-005**: 100% of teaser clips of unreleased songs link to the album page and name the album and its date (or "Coming soon").
- **SC-006**: On the coming-soon page, 0 full songs can be found, played or linked.

## Assumptions

- The owner is the only person who releases; listener-facing behaviour changes only on navaan.online album and search pages.
- A single is an album of kind single with exactly one song; there is no separate single-song release path.
- Instagram carries teaser clips only; the full song is never posted there, so "full song public" means YouTube and navaan.online.
- Retry counts, the 12-hour late window and history lines reuse today's scheduled publishing behaviour.
- Times are entered and shown in the owner's local time and stored unambiguously.
- Unreleasing an album is out of scope.
- The existing album name suggestions and cover generation stay as they are.
- The current rule that an album can only be published when all its songs are already published is replaced by FR-001 and FR-007.
