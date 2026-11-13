# Research: Album release

Findings from the code on `origin/develop` (2f12faf). No external research needed.

## R1. Where a song goes public today

- `navaan.py` music `tail` steps run in this order: `archive` (cloud upload, sets `state=published`) → `youtube_meta` → `publish_youtube` (full video, private) → `youtube_short` (Short, private) → `go_public` (`publish_youtube.py go-public`: full video **and** Short public) → `instagram_caption` → `publish_instagram` (Reel).
- `catalog_store.sync_item` lists a track when `meta.state == "published"` (set by `archive`) **or** all of its YouTube items are public. So, today, a track is on navaan.online as soon as it is archived.
- `sync_item` also creates the album from the `meta.album` label, and promotes the album `draft → published` when a published song joins it.

**Decision**: the catalog lists a track only once the song is released. The rule, `released(m)`, is true when `meta.release` exists or the full video is already public. Songs listed today stay listed through `tracks.public_before_albums`, set by migration 0009 itself (a backfill command would race with the startup sync, which would unlist them first) (FR-018). `sync_item` stops promoting albums.

**Rationale**: one predicate covers search, album pages, direct links and the cover/`play` routes, because they all read catalog `status`.

**Alternatives considered**:
- Stop `archive` from setting `state=published`: rejected, because other code reads `state` (UI status, the reel music library).
- Keep tracks unlisted with a flag: rejected, because it would add a second visibility field next to `status`.

## R2. Holding the full video

- `navaan.run` already stops a step that has a schedule time (`PS.hold`, rc 7, "scheduled") unless the scheduler is firing it (`PS.FIRING`).

**Decision**: in the same place, a music item's `go_public` that is not released returns rc 7. The message is "Waiting for album release: <album>", or "Add this song to an album to release it" when the song is in no album. `PS.FIRING` lets the scheduler through once the album is released.

**Alternatives considered**: a new gate per song: rejected, because the spec says no per-song release control (FR-003).

## R3. Splitting the Short from the full video

- `publish_youtube.go_public` flips every YouTube item plus `youtube_short` together.

**Decision**: add `--only full|short`.
- `go_public` runs `--only full`.
- A new step, `short_public` (`before="publish_short"`, after `youtube_short`), runs `--only short`, so teasers can go public before release.
- `public_done` is split to match.

**Rationale**: the spec allows teasers on both platforms before release (Q1 = A). Instagram already has its own lane.

## R4. Release mechanics

**Decision**: `album_release.release(slug, by, at)`:
1. Readiness check. Every song needs:
   - the full video uploaded (`yt_done`);
   - `archive` done and verified (navaan.online needs the audio);
   - every gate before `go_public` approved and not stale (`gate_ok`);
   - and the album needs at least one song.
2. Confirm writes, per song: approval `go_public` via `album release <slug> by <who>` (keeping its existing semantics), `schedule.youtube_at = at`, `meta.release = {"album": slug, "at": at, "by": who}` (only effective at release time, see step 3), and a history line.
3. At `at` (now, or the scheduler tick), one transaction: `albums.status='published'`, `published_at`, and `tracks.status='published'` for each song, followed by a reindex. If the transaction fails, nothing is listed and it is retried on the next tick.
4. The full-video flip is the existing scheduled `go_public`. The scheduler already provides 3 tries 10 min apart, the 12 h grace and "missed".

**Rationale**: no second retry or claim loop. It reuses the row-locked claim in `publish_schedule.tick`.

**Alternatives considered**: a new jobs kind `album_release`: rejected, because it duplicates scheduler semantics.

## R5. Scheduled release

- The worker starts `PS.loop` (every 60 s, unless `NAVAAN_SCHEDULER=off`).

**Decision**: `PS.loop` also calls `album_release.tick(now)`. It handles albums with `status='scheduled'` and `release_at <= now`:
- ready → step 3 of R4;
- not ready → stay scheduled, and set `release.blocked` with the reason;
- more than 12 h late → `status='missed'` and an alert (it uses `settings_api.alerts()`, which Slack also forwards).

**Song list changes**: `save_album`, reorder and the add/remove paths call `album_release.disarm(slug)` when the album is scheduled. That sets the status back to `draft`, revokes the `go_public` approvals it gave, clears those `youtube_at`, and writes a history line (FR-012).

## R6. Teaser captions and links

- `navaan_common.with_site_link(text, slug, plain, itype)` appends the song page to YouTube descriptions and Instagram captions. It is called from `publish_youtube.py:123` and `publish_instagram.py:62`.
- `short_meta.build` writes "Full song: <full video url>" into the Short. That video is private before release.

**Decision**:
- For a music item that is not released and is in an album, `with_site_link` appends "Out <date> · <album>" (or "Coming soon · <album>") plus `SITE/app/album/<album slug>`.
- `short_meta` drops the full-video link when the song is not released.
- When an album is released, the Short and Reel captions are **not** edited. The album page link stays valid (FR-017).

## R7. Coming-soon page

- `/api/catalog/album/<slug>` returns only `public_albums` (status published), so other albums 404.

**Decision**: `catalog_store.album_page(slug)` returns:
- published → unchanged;
- `announced` and unreleased → `{title, kind, cover, release_at, teasers:[{platform,url}], coming_soon:true}`, with no tracks;
- otherwise → 404.

Teaser URLs come from each song's `meta.published` (Short URL, Reel permalink) once they are public. `ListenerAlbum.tsx` renders the countdown, and shows "Releasing now" at or after `release_at` until the album is published.

## R8. Album states

- The current check allows `draft|scheduled|published`.

**Decision**: add `missed`, and keep `published` as "released". `announced` is a separate boolean, so a draft or scheduled album can be announced. Columns: `release_at timestamptz NULL`, `announced boolean NOT NULL DEFAULT false`, `release jsonb NOT NULL DEFAULT '{}'`.

The migration is expand-only: the new check is a superset, and every new column has a default.

## R9. Teaser drip (P4)

**Decision**: deferred to a later task set. It will build on `PS.suggest` slots, and nothing in P1–P3 depends on it.
