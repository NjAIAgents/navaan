# Tasks: Album release

**Input**: `specs/003-album-release/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Tests**: included. The constitution (VIII) requires them, and quickstart.md §1 lists the cases. Paths are relative to `plugins/navaan-studio/` unless they start with `specs/`.

**Run tests**: `NAVAAN_PG_PORT=5440 python3 -m unittest discover -s tests -p '<file>'` from `plugins/navaan-studio`.

## Phase 1: Setup

- [X] T001 Create migration `db/migrations/catalog/0009_album_release.sql`. It is expand-only: drop and re-add the `albums_status_check` constraint, with values `draft, scheduled, published, missed`; add `release_at timestamptz NULL`, `announced boolean NOT NULL DEFAULT false`, and `release jsonb NOT NULL DEFAULT '{}'::jsonb`. Add the header comment in the style of 0001 ("Released: never edit, add 0010").
- [X] T002 Create `scripts/album_release.py` with the author header (Author from `git config user.name`, Created/Last updated 2026-11-13, Description) and an empty module docstring that lists the functions planned in data-model.md. Use `navaan_log` as `L` and `LOG = L.get("album_release")`.

## Phase 2: Foundational (blocks every story)

- [X] T003 Add `released(m)` (= `bool(m.get("release"))`) and `held_album(m, slug)` to `scripts/navaan_common.py`. `held_album` returns the album that releases first, or `None`; read `catalog.album_tracks` through `catalog_store`, and fall back to the `meta.album` label when the DB is not reachable (log it with `L.soft`).
- [X] T004 Change `sync_item` in `scripts/catalog_store.py`:
  - a track is `published` only when `released(m)` and it meets today's rule;
  - remove the album `draft→published` promotion in the `album` block, and insert a new album as `draft`;
  - index the track only when it is published.
- [X] T005 Keep songs listed today listed. Changed from a backfill command: a sync on the server before the backfill ran would have unlisted them. Migration 0009 now sets `tracks.public_before_albums = true` for every track listed when it runs; `sync_item` keeps those listed; `navaan_common.released(m)` also treats a song whose full video is already public as released.
- [X] T006 [P] Add to `tests/test_catalog.py`:
  - an unreleased archived song is `draft` and missing from `search` and `public_albums`;
  - a released song is `published`;
  - a track marked `public_before_albums` stays `published`;
  - adding a published song to a draft album no longer publishes the album.

**Checkpoint**: the catalog only lists songs that have been released, and legacy songs stay listed.

## Phase 3: User Story 1: Songs wait for their album (P1)

**Goal**: a finished song never goes public on its own.
**Independent test**: put a song in an unreleased album and run its pipeline to the end. It stops at `go_public` with rc 7, the video stays private, and the track is not listed.

- [X] T007 [P] [US1] In `tests/test_album_release.py`, write the hold tests:
  - `navaan.run` on `go_public` for an unreleased music item in an album returns 7 and prints "Waiting for album release: <title>";
  - with no album, it prints "Add this song to an album to release it";
  - a released item, or a slug in `PS.FIRING`, passes;
  - aha and inspiration items are not affected.
- [X] T008 [US1] In `scripts/navaan.py` `run()`, right after the `PS.hold` check, add the hold. When `item_type == "music"`, `sid == "go_public"`, `not C.released(m)` and `slug not in PS.FIRING`: print the message, set `RUN[slug]`, and return 7.
- [X] T009 [US1] Add `--only full|short` to `publish_youtube.py go-public` (in `go_public(a)`, filter the `items` list; with no flag, both kinds flip, as today). Split `public_done` in `scripts/navaan.py` into `full_public_done(m)` and `short_public_done(m)`.
- [X] T010 [US1] Change the music `tail` in `scripts/navaan.py`:
  - `go_public` runs `go-public --only full`, its label becomes "Make the full YouTube video public (on album release)", and `done=full_public_done`;
  - add a step `short_public` after `youtube_short` (`before="publish_short"`, cmds `go-public --only short --yes`, `done=short_public_done`, label "Make the Short public (teaser)").
- [X] T011 [US1] Make the studio UI show the hold reason. `navaan_ui.py` builds the item row (line ~121): set `status` to "Waiting for album release: <album>" when the item is held. Remove the per-song approve control for `go_public` on music items in `web/src/lib/gates.ts` (FR-003), and link to `/app/albums/<slug>` instead.
- [X] T012 [P] [US1] In `tests/test_album_release.py`: `go-public --only short` flips only the Short and `--only full` flips only the full video (stub the YouTube client the way the existing publish tests do).

**Checkpoint**: MVP safety. Nothing a pipeline does can release a song.

## Phase 4: User Story 2: Release an album now (P1)

**Goal**: one confirm releases the album and all its songs.
**Independent test**: an album with two ready held songs → release → both tracks and the album are listed at once, both `go_public` steps are approved via the album with `youtube_at` = now, and the history says "released with <album>".

- [X] T013 [P] [US2] In `tests/test_album_release.py`, write the readiness tests. `readiness(album)` reports, per song: "video not uploaded", "not archived", "gate <g> not approved", "<file> changed since approval". An album with no songs gives "Add at least one song".
- [X] T014 [P] [US2] In `tests/test_album_release.py`, write the release tests:
  - `confirm(album, songs, by, at=None)` refuses when the song list differs (`ValueError` "the song list changed") and when the album is not ready;
  - when ready, it sets album and tracks to `published` in one transaction (force a failure on the second track and assert that 0 tracks are listed);
  - it writes `approvals.go_public` with via "album release <slug> by <who>", `schedule.youtube_at`, `meta.release`, and the history lines.
- [X] T015 [US2] In `scripts/album_release.py`, implement `readiness(album_slug)`. Reuse `navaan.yt_done`, the cloud verified check from the `archive` step's `done`, and `navaan.gate_ok` for every gate whose step comes before `go_public` in `navaan.steps(slug)`.
- [X] T016 [US2] In `scripts/album_release.py`, implement `confirm(album_slug, songs, by, at=None)` and `_release(album_slug)`:
  - `confirm` writes `albums.release` (`confirmed_by`, `confirmed_at`, `songs`, `via`) and, per song, the go_public approval and `youtube_at`. With `at` unset or in the past, it calls `_release` straight away; otherwise it sets `status='scheduled'` and `release_at`.
  - `_release` runs one `catalog_store._tx`: album `published`, `release_at`, `release.released_at`, each track `published` + `published_at`, reindex. After the commit it sets each song's `meta.release = {"album","at","by"}` and calls `catalog_store.sync_item`.
- [X] T017 [US2] In `scripts/album_release.py`, implement `retry(album_slug, song)`: reset the song's `schedule.attempts.go_public` and `missed.go_public`, and write a history line.
- [X] T018 [US2] Add the studio routes in `scripts/navaan_ui.py`, following contracts/studio-api.md:
  - `GET /api/albums/release`, `POST /api/albums/release`, `POST /api/albums/release/retry`;
  - `studio` permission, CSRF as in the existing `/api/albums/save`;
  - 409 with the readiness body when not ready or when the song list changed.
- [X] T019 [US2] Add the CLI commands `album-status` and `album-release <album> [--at] --yes` to `scripts/navaan.py` (contracts/cli.md exit codes 0/2/4/9). Both call `album_release`.
- [X] T020 [US2] Add the per-song state to the status: `youtube` is public, retrying (attempts and last error from `meta.schedule`) or failed (3 tries); `site` is listed or unlisted. Put it in the `readiness`/status response in `scripts/album_release.py`.
- [X] T021 [US2] Add the Release card to `web/src/pages/Album.tsx` (owner only):
  - the readiness list with reasons and a Release now button;
  - a confirm sheet listing every song and "YouTube + navaan.online, hard to undo";
  - per-song progress with Retry;
  - 390 px first, 44 px targets, theme tokens only.
  
  Add the types to `web/src/lib/api.ts` (`AlbumRow` gets `release_at`, `announced`, `release`).

**Checkpoint**: a manual album release works end to end.

## Phase 5: User Story 3: Schedule an album release (P2)

**Goal**: the release fires at a set time without the owner present.
**Independent test**: schedule a release 2+ minutes ahead. A tick before the time does nothing; a tick after it releases the album.

- [X] T022 [P] [US3] In `tests/test_scheduler_once.py` (or `tests/test_album_release.py`), test `album_release.tick(at)`:
  - before the time, it does nothing;
  - at the time and ready, it releases;
  - not ready, it sets `release.blocked` and stays scheduled;
  - more than 12 h late, it sets `status='missed'`, `release.missed_at`, and raises one alert;
  - `cancel` reverts to `draft` and revokes approvals and `youtube_at`;
  - changing the song list on a scheduled album disarms it.
- [X] T023 [US3] Implement `tick(at=None)`, `cancel(album_slug, by)` and `disarm(album_slug, why)` in `scripts/album_release.py`. Reuse `publish_schedule.GRACE_H` and `MIN_LEAD_MIN`; for the missed alert, use the existing alert path in `settings_api` (the one the Slack bridge already forwards).
- [X] T024 [US3] In `scripts/publish_schedule.py` `loop()`, call `album_release.tick()` before the item `tick` on every pass. Log errors with `L.exc`; an album error must never stop item scheduling.
- [X] T025 (the disarm check runs on reorder and on every scheduler minute, which covers every path that changes an album's songs) [US3] In `scripts/catalog_store.py`, make `save_album` (and the reorder and add/remove paths behind `/api/albums/save|reorder` and `/api/album`) call `album_release.disarm` when the album is `scheduled` and its song set changed, and return `disarmed: true`. Also remove the old "every song must already be published" check in `save_album`, and reject `status='published'` through save: releasing goes only through `confirm`.
- [X] T026 [US3] Add the `album-cancel` CLI command to `scripts/navaan.py`. Add `POST /api/albums/release/cancel` to `scripts/navaan_ui.py`.
- [X] T027 (done except listing scheduled albums on `Schedule.tsx`, left for later) [US3] Add scheduling to the Release card in `web/src/pages/Album.tsx`: a date-time input (native `datetime-local`, local time), the "Scheduled for <time>" state, Cancel, and the "missed" state with a release again option. Also list scheduled albums on `web/src/pages/Schedule.tsx`.

## Phase 6: User Story 4: Promote with clips before release (P2)

**Goal**: teasers point to the album and never expose the full song.
**Independent test**: for a held song, the Short description and Reel caption carry "Out <date> · <album>" and the album link; the full video stays private.

- [X] T028 [P] [US4] In `tests/test_album_release.py`, test `with_site_link`:
  - a held music song in an album with `release_at` gets "Out <local date> · <title>" and `.../app/album/<slug>`;
  - without a date, it gets "Coming soon · <title>";
  - a released song gets the song link as today;
  - `plain=True` drops https;
  - aha and blog are unchanged.
- [X] T029 [US4] Implement the held branch in `with_site_link` in `scripts/navaan_common.py`. Load meta when a slug is given, and use `held_album` from T003.
- [X] T030 [US4] In `scripts/short_meta.py` `build()` and its caller, drop "Full song: <url>" when the song is not released. `with_site_link` adds the album line instead.
- [X] T031 [P] [US4] Add one line to the caption rule in `skills/instagram-caption/SKILL.md`: for a song not yet released, the album line and link are appended automatically, so do not mention release dates in the caption body.
- [X] T032 [P] [US4] Check the teaser length (30 to 60 s, shorter than the full song) at `short_public` and `publish_instagram`, using `C.duration()`. Refuse with a clear message in `scripts/navaan.py` `run()`.

## Phase 7: User Story 5: Album coming-soon page (P3)

**Goal**: an announced album has a public page with no full songs.
**Independent test**: an announced unreleased album returns `coming_soon: true` with no `tracks`; an unannounced one returns 404.

- [X] T033 [P] [US5] In `tests/test_catalog.py`, test `album_page(slug)`:
  - published: as today;
  - announced and unreleased: `coming_soon`, `release_at`, `teasers`, and no `tracks` key;
  - not announced: `None`.
- [X] T034 [US5] Implement `album_page(slug)` in `scripts/catalog_store.py`. Collect teaser URLs from each song's `meta.published`: the Short URL once public, and the Instagram permalink. Change `GET /api/catalog/album/<slug>` in `scripts/navaan_ui.py` to use it. Keep the share and cover routes as they are: they already require `published`, so no full-track leak.
- [X] T035 [US5] Add the `album-announce <album> on|off` CLI command to `scripts/navaan.py`, and an `announced` toggle on the Release card in `web/src/pages/Album.tsx` (it saves through `/api/albums/save`).
- [X] T036 [US5] Add the coming-soon view to `web/src/pages/ListenerAlbum.tsx`: cover, title, kind, release date, a countdown (show "Releasing now" at or after `release_at`, and update at most once a second, respecting reduced motion), and teaser links. Show no track list.

## Phase 8: User Story 6: Teaser drip (P4, later)

- [ ] T037 [US6] Deferred. Write a follow-up story in `specs/003-album-release/spec.md` §User Story 6 when the owner asks for it; it will build on `publish_schedule.suggest`. No code in this release.

## Phase 9: Polish

- [X] T038 [P] Add an "Album release" section to `docs/SCHEDULING.md` (hold, release now, scheduled, missed, teasers), and update the gates line in `AGENTS.md` (new step `short_public`; `go_public` now means the full video on album release).
- [X] T039 [P] Add a CHANGELOG `[Unreleased]` entry, through `/changelog` or by hand per the repo's practice, covering:
  - Added: album release, scheduled release, coming-soon page, teaser links;
  - Changed: songs go public only with their album; the Short is published separately.
- [X] T040 Run the full suite (`python3 -m unittest discover -s tests -p 'test_*.py'`) and `cd web && npm test`; fix failures caused by the step split (tests that assert the old `go_public` behaviour).
- [X] T041 Run `graphify update .` after the code changes (no graph in this worktree: nothing to update).
- [ ] T042 Release note for the owner: before deploy, back up (migration) and check `studio.jobs`; after deploy, compare the published track count before and after (quickstart §3).

## Dependencies

- Setup (T001–T002) → Foundational (T003–T006) → every story.
- US1 (T007–T012) comes before US2: release relies on the hold and on the `--only full` flip.
- US2 (T013–T021) comes before US3, which reuses `confirm`/`_release`.
- US4 depends only on Foundational T003 and can run in parallel with US2 and US3.
- US5 depends on T001 (`announced`) and T004, and can run in parallel with US2–US4.
- Polish comes last.

## Parallel opportunities

- T006, T007, T012, T013, T014 are test files written in parallel before the code they cover.
- After Foundational: US4 (T028–T032) and US5 (T033–T036) can go alongside US2.
- T031, T038 and T039 are docs only.

## Implementation strategy

1. **MVP** = Phase 1–3 (hold) + Phase 4 (release now). Ship it.
2. Next: Phase 5 (scheduled) and Phase 6 (teaser links).
3. Then Phase 7 (coming-soon page).
4. Phase 8 waits for the owner.
