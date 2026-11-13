# Data model: Album release

## catalog.albums (changed by migration `0009_album_release.sql`)

| Column | Type | Note |
|---|---|---|
| status | text | check widened to `draft`, `scheduled`, `published`, `missed`; `published` means released |
| release_at | timestamptz NULL | the release time; set on schedule, and on release-now (= now) |
| announced | boolean NOT NULL DEFAULT false | coming-soon page visible while unreleased |
| release | jsonb NOT NULL DEFAULT '{}' | `{confirmed_by, confirmed_at, songs:[slug...], via:"now"\|"schedule", blocked:"reason", released_at, missed_at}` |
| release_date | date | existing; kept, filled from `release_at` for display |

### State transitions

```text
draft --confirm now--------------------------> published
draft --confirm at T-------------------------> scheduled
scheduled --T reached, all ready-------------> published
scheduled --T reached, not ready-------------> scheduled (release.blocked set; retried each tick)
scheduled --more than 12 h past T------------> missed
scheduled --cancel or song list changed------> draft (go_public approvals given by the confirm revoked)
missed --confirm again (now or new T)--------> published | scheduled
published --(no transition; unrelease out of scope)
```

`announced` can be toggled in `draft` or `scheduled`. It does nothing once the album is `published`.

## catalog.tracks (one new column)

- `status` becomes `published` only through the album release transaction, or stays so when `public_before_albums` (new column, set by migration 0009 for tracks listed then).
- `sync_item` keeps a released track `published`. It never promotes a track that has not been released.

## Song item meta.json (pipeline state, files area)

| Key | Shape | Written by |
|---|---|---|
| `release` | `{"album": slug, "at": iso, "by": who}` | the album release (after its transaction commits) |
| `approvals.go_public` | `{"at", "via": "album release <slug> by <who>"}` | the confirm; revoked on disarm |
| `schedule.youtube_at` | iso | the release (its moment), so a scheduled release never fires a video early |
| `history[]` | lines | confirm, disarm, released, flip results (existing scheduler lines) |

`released(m)` = `meta.release` exists, or every full YouTube video is already public. `catalog.tracks.public_before_albums` (set by migration 0009 for tracks listed then) keeps older songs listed. A song is **held** when its type is `music`, `released(m)` is false, and the next step is `go_public`.

## Readiness (derived, not stored)

A song is ready when all of these hold:
- the full video is uploaded (`yt_done`);
- the cloud archive is verified;
- every gate before `go_public` is approved and its content hash still matches.

An album is ready when it has at least one song and every song is ready. Each song that is not ready reports one reason:
- `video not uploaded`
- `not archived`
- `gate <g> not approved`
- `<file> changed since approval`

## Teaser link (derived)

For a held music item in album A:
- caption suffix `Out <release_at local date> · <A.title>`, or `Coming soon · <A.title>` when there is no `release_at`;
- link `SITE/app/album/<A.slug>`.

A song in several albums uses the album that releases soonest, then the first by title.
