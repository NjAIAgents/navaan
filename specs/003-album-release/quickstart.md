# Quickstart: prove album release works

## Prerequisites

- Local Postgres up, with `NAVAAN_PG_PORT=5440` exported.
- Migrations applied, including `catalog/0009_album_release.sql`.
- `NAVAAN_YT_PRIVACY=private` (the default). The real-run steps use the owner's YouTube channel and need the owner's go.

## 1. Automated

```bash
cd plugins/navaan-studio
NAVAAN_PG_PORT=5440 python3 -m unittest discover -s tests -p 'test_album_release.py'
NAVAAN_PG_PORT=5440 python3 -m unittest discover -s tests -p 'test_catalog.py'
NAVAAN_PG_PORT=5440 python3 -m unittest discover -s tests -p 'test_scheduler_once.py'
NAVAAN_PG_PORT=5440 python3 -m unittest discover -s tests -p 'test_*.py'      # full suite, as CI runs it
(cd web && npm test)
```

The tests must show:
- **Hold**: a held song stops at `go_public` (rc 7, "Waiting for album release"), and its track is not in search or on the album page.
- **Readiness**: release is refused with per-song reasons; a song list that changed is answered with 409.
- **Release now**: album and tracks are `published` in one transaction; each song has `go_public` approved via the album at the confirm, and `youtube_at` set at the release.
- **Atomic**: a failure inside the transaction leaves 0 tracks listed.
- **Scheduled**: a tick before the time does nothing; at the time, the album is released. If a song is not ready, the album stays blocked, and after 12 h it is `missed`.
- **Disarm**: adding a song to a scheduled album sets it back to `draft` and revokes the approvals.
- **Legacy**: a track listed before migration 0009 (`public_before_albums`) stays listed without a release.
- **Teaser caption**: a held song gets "Out <date> · <album>" and the album link; a released song gets the song link.
- **Coming soon**: an announced album has no `tracks` key; an unannounced one returns 404.

## 2. Real run (needs the owner's go; publishes to YouTube)

1. Create a test album "Release Test" with one finished private song. `navaan.py album-status release-test` → ready.
2. Run the song's pipeline. It stops at `go_public` with "Waiting for album release". The full video is still private (YouTube Studio), and https://navaan.online/app/song/<slug> is not found.
3. Run `short_public`: the Short is public and its description shows "Coming soon · Release Test" and the album link.
4. `navaan.py album-announce release-test on`, then open /app/album/release-test: cover and "Coming soon", no tracks.
5. `navaan.py album-release release-test --at "<now + 5 min>" --yes`. Studio shows "Scheduled for …".
6. Within 2 min of the time:
   - the album and song are on navaan.online;
   - within 15 min the full video is public;
   - the history shows "released with release-test".
7. Optionally, put that video back to private by hand afterwards: unreleasing is out of scope.

## 3. Release checks

- Back up before deploying (the release carries a migration, constitution XIII).
- After deploy: the count of published tracks is the same before and after (the migration marks them `public_before_albums`).
