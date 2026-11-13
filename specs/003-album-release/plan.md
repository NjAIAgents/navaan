# Implementation Plan: Album release

**Branch**: `feat/003-album-release` | **Date**: 2026-11-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-album-release/spec.md`

## Summary

Only an album can be released. Releasing it does two things at the same moment: every song's full YouTube video becomes public, and the album and its songs are listed on navaan.online. The plan reuses what already exists rather than building a second publisher:

- **Hold**: `navaan.run` stops the `go_public` step of a song that has not been released. It works the way a scheduled step is stopped today (rc 7) and shows "Waiting for album release: <album>".
- **Release**: a single Postgres transaction marks the album and its tracks `published`. Each song's full-video flip then goes to the existing publishing scheduler (`publish_schedule`):
  - the owner's confirm approves each song's `go_public` gate (via "album release <slug>");
  - it sets `schedule.youtube_at` to the release time.
  
  The existing retries (3, 10 min apart), the 12 h grace and the "missed" state need no new code.
- **Scheduled release**: a new `albums.release_at` column. The scheduler loop already runs in the worker, and each minute it also checks for albums that are due.
- **Teasers**: the Short moves out of `go_public` into its own `short_public` step, behind the existing `publish_short` gate. `with_site_link` is the one place captions get their link. For a held song, it now points the Short and the Reel at the album page and adds "Out <date> · <album>".
- **Coming-soon page**: the listener album route serves an announced, unreleased album without its tracks.

## Technical Context

**Language/Version**: Python 3.12 (stdlib-first orchestrator), TypeScript + React (web, Vite build)

**Primary Dependencies**: existing only: `psycopg`, React/Vite/Tailwind (constitution VII). No new dependency.

**Storage**: Postgres schema `catalog` (albums, tracks, album_tracks) for album state. Each song's `meta.json` keeps its pipeline state, approvals and schedule; that area has not moved to Postgres yet (constitution III note).

**Testing**: `unittest` via `python3 -m unittest discover -s plugins/navaan-studio/tests -p 'test_*.py'` (locally needs `NAVAAN_PG_PORT=5440`); web: `npm test` in `plugins/navaan-studio/web`

**Target Platform**: Oracle ARM Linux VM (Docker: navaan, navaan-worker, navaan-slack, navaan-postgres) and the owner's Mac

**Project Type**: web service + pipeline orchestrator in one plugin

**Performance Goals**: the release transaction takes under 1 s for an album of up to 30 songs. A scheduled release starts within 2 min of its time (SC-004); the loop ticks every 60 s.

**Constraints**:
- YouTube API quota: each privacy flip is one `videos.update` call (50 units).
- A release must never leave the catalog half-published, so it runs in one transaction.

**Scale/Scope**: one artist, albums of 1 to ~30 songs, a handful of releases a month

## Constitution Check

| Principle | Check | Status |
|---|---|---|
| I Humans own the gates | Release and schedule need the owner's confirm, with the song list shown. That confirm is the recorded approval of each song's `go_public` (via "album release"). Scheduling alone approves nothing, and changing the song list disarms a schedule. | Pass |
| II Secrets | No new secret. YouTube and Instagram tokens unchanged. | Pass |
| III Postgres is the state | Album state, release time and release record live in Postgres. Song pipeline state stays in `meta.json` (not yet migrated). The catalog flip is idempotent and can be re-derived. | Pass |
| IV No hidden spend | No paid call. | Pass |
| V Safe by default | Release routes are studio routes (owner, login, CSRF). The coming-soon page is a listener read that exposes no track. | Pass |
| VII Small dependency surface | Nothing added. | Pass |
| VIII Prove it | quickstart.md lists the real run; tests per story. | Pass |
| X Recoverable and visible | History lines for confirm, schedule, cancel, start, each song's result, and missed. Retries are bounded (3). | Pass |
| XII Least privilege | New routes require the `studio` permission. The listener album read keeps its current permission. | Pass |
| XIII Schema discipline | One expand-only migration, `catalog/0009_album_release.sql`: widen the status check and add nullable columns. The previous release still runs on it. Back up before release. | Pass |
| XIV Mobile-first | Release card and confirm sheet designed at 390 px, 44 px targets, tokens only. | Pass |
| XVII Nothing fails silently | Every failed flip is logged once with album, song and attempt. No empty except. | Pass |

Re-checked after Phase 1 design: no change.

## Project Structure

### Documentation (this feature)

```text
specs/003-album-release/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── studio-api.md
│   └── cli.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
plugins/navaan-studio/
├── db/migrations/catalog/0009_album_release.sql   # new: status values, release_at, announced, release jsonb
├── scripts/
│   ├── album_release.py      # new: readiness, confirm (now or at a time), cancel, due-check, release transaction
│   ├── catalog_store.py      # sync_item: track published only once released; no auto-publish of albums; coming-soon view
│   ├── navaan.py             # hold go_public for unreleased songs; new short_public step; CLI album-release/-schedule/-cancel
│   ├── publish_youtube.py    # go-public --only full|short
│   ├── publish_schedule.py   # loop also calls album_release.tick()
│   ├── navaan_common.py      # with_site_link: held song -> album page + "Out <date> · <album>"
│   ├── short_meta.py         # Short description links the album page, not the private full video
│   └── navaan_ui.py          # studio routes /api/albums/release*, listener coming-soon album
├── skills/instagram-caption/SKILL.md   # note: the album line is appended for unreleased songs
├── web/src/
│   ├── pages/Album.tsx           # owner Release card: readiness, Release now, Schedule, Cancel, per-song progress
│   ├── pages/ListenerAlbum.tsx   # coming-soon view: cover, date, countdown, teasers, no tracks
│   └── lib/api.ts                # AlbumRow gains release fields
├── docs/SCHEDULING.md        # album release section
└── tests/
    ├── test_album_release.py     # new
    ├── test_catalog.py           # release gating of tracks
    └── test_scheduler_once.py    # album due-check
```

**Structure Decision**: one new module, `album_release.py`, owns the release rules (one place, constitution XVI). Every other change is small and sits at an existing choke point: the `navaan.run` hold, `with_site_link`, `sync_item`, and the scheduler loop.

## Complexity Tracking

None.
