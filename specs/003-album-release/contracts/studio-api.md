# Studio and listener HTTP contract: Album release

Every studio route needs the `studio` permission, login and CSRF, like the existing `/api/albums/save`. Errors use the existing `{"error": "..."}` shape with 400, 404 or 409.

## GET /api/albums/release?album=<slug>  (studio)

The readiness check and the current release state. Spends nothing and changes nothing.

```json
{
  "album": "monsoon-letters", "status": "draft", "announced": false, "release_at": null,
  "ready": false,
  "songs": [
    {"slug": "song-031", "title": "...", "ready": true, "reason": null,
     "youtube": "private|public|retrying|failed", "site": "unlisted|listed", "attempts": 0, "error": ""},
    {"slug": "song-032", "title": "...", "ready": false, "reason": "gate media not approved"}
  ],
  "blocked": null
}
```

## POST /api/albums/release  (studio)

Body: `{"album": "<slug>", "at": "<ISO UTC>" | null, "songs": ["song-031", ...]}`

- `songs` must equal the album's current song list (the list the owner confirmed). Otherwise the response is **409** `"the song list changed; review again"`.
- Not ready → **409**, with the readiness body.
- `at` null or not in the future → release now: responds **200** with `status: "published"`, and the YouTube flips are queued.
- `at` in the future → **200** with `status: "scheduled"`. The time must be at least 2 min ahead (the existing `MIN_LEAD_MIN`).

## POST /api/albums/release/cancel  (studio)

Body: `{"album": "<slug>"}`. Allowed only while `scheduled` or `missed`: it goes back to `draft` and revokes the approvals the confirm gave. In any other state → **409**.

## POST /api/albums/release/retry  (studio)

Body: `{"album": "<slug>", "song": "<slug>"}`. For a released album, this resets the attempt count of the song's `go_public` (`failed` after 3 tries) so the scheduler tries again.

## POST /api/albums/save  (existing, extended)

New optional field: `announced: boolean`. Saving a changed song list on a `scheduled` album disarms it (status `draft`) and returns `"disarmed": true`.

## GET /api/catalog/album/<slug>  (listener, existing, extended)

- Published: unchanged.
- Announced and unreleased:

```json
{"slug": "...", "title": "...", "kind": "album", "coming_soon": true, "release_at": "2026-12-01T12:30:00Z",
 "art": {...}, "teasers": [{"platform": "youtube_short|instagram", "url": "..."}]}
```

It has no `tracks` key.
- Otherwise: 404 (as today).

## Run exit codes (`navaan.py run`)

- rc 7 with `held: album <slug>`, or `held: no album`, for a music `go_public` that has not been released (the same code as "scheduled", so existing callers treat it as waiting, not failed).
