# Data Model: NAVAAN platform foundation

PostgreSQL 17. Six schemas. Reviewed 2026-10-15 (13 findings applied below). The `analytics` schema already shipped as migration `analytics/0001` (NAV-3); the other schemas get their migration only after their own phase starts.

## Conventions

- Primary keys are `uuid` (`gen_random_uuid()`; `uuidv7()` when on PG 18). Existing human slugs (`song-001`, `insp-001`) stay as a unique `slug` so URLs and file paths still map.
- All times are `timestamptz` in UTC. Flags are `boolean`. Open payloads (raw API responses) are `jsonb`; everything else is typed columns.
- States are `text` with a `CHECK` list. Every foreign key has an index. Mutable rows carry `created_at` and `updated_at`.
- Soft delete (`deleted_at`) only where a person can restore. Triggers only maintain `updated_at`.
- Extensions: `citext`, `pg_trgm`, `unaccent` now; `vector` later. Anything that only grows (`login_attempts`, `play_events` detail, `audit_log`) has a stated prune or partition rule and a `jobs` kind that runs it.
- Every catalog, studio and analytics row carries `artist_id`; every listener row carries `user_id`. Queries are always scoped by one of them (constitution XII).

## core

| Table | Key columns | Rules |
|-------|-------------|-------|
| `users` | id, username, email (lower-case, unique on lower(email); no `citext` extension, so no superuser is needed), display_name, status, email_verified_at, locale, preferences jsonb | one row per person; `preferences.appearance` holds `{tone: 0..10, accent: key, match_device: bool}`, `preferences.personalise` holds the taste on/off switch, notifications go here too |
| `user_profiles` | user_id (pk), display_name, avatar_asset_id, bio, country, languages text[], updated_at | no date of birth or phone number (constitution XV) |
| `credentials` | user_id, kind (`password`/`passkey`/`totp`/`recovery`), hash or public key or secret, label, last_used_at | owner's existing auth migrates here |
| `identities` | user_id, provider (`google`/`apple`/...), subject, email, linked_at | unique (provider, subject); empty until those providers are added |
| `sessions` | token_hash (pk), user_id, csrf_token, ip, user_agent, expires_at, revoked_at | replaces `sessions.json` and the global CSRF token |
| `roles` | id, name (`owner`/`editor`/`listener`) | |
| `user_roles` | user_id, role_id, artist_id (nullable) | artist-scoped roles for later |
| `role_permissions` | role_id, permission | e.g. `studio.approve`, `library.view`, `playlists.write` |
| `audit_log` | actor_id, action, subject, at, detail jsonb | approvals, publishes, role changes |
| `login_attempts` | key (account or ip), at, ok | replaces in-memory throttle; the worker prunes rows older than 30 days (`jobs` kind `prune_login_attempts`) |
| `schema_migrations` | schema_name, version, name, applied_at | already exists (NAV-3); primary key (schema_name, version); written by `db_migrate.py` |

## catalog

| Table | Key columns | Rules |
|-------|-------------|-------|
| `artists` | id, slug, name, status, theme jsonb | NAVAAN is the only row at first; `theme` can override a few accent tokens for a per-artist look later |
| `tracks` | artist_id, slug, title, language, duration_ms, explicit, lyrics_text, status, published_at, origin, license_status, studio_item_id | `license_status` must be `confirmed` before any entitlement-gated use (FR-017) |
| `albums` | artist_id, slug, title, kind (`album`/`ep`/`single`), status (`draft`/`scheduled`/`published`), release_date, description, cover_asset_id | |
| `album_tracks` | album_id, track_id, position | unique (album_id, position), deferrable, so reorder is one transaction |
| `assets` | owner_kind, owner_id, role (`audio`/`cover`/`video`/`reel`/`lyrics_timed`), storage_key, mime, bytes, sha256, duration_ms, width, height, dominant_colour, blurhash, derived_from | several renditions per track or cover; object storage is the source of truth; `lyrics_timed` holds line timings (from the caption timing step) for highlighted lyrics; plain text stays in `tracks.lyrics_text` |
| `genres`, `track_genres` | name; track_id, genre_id | the only place a track's genres live (no `tracks.genre` column, so there is one source) |

**Search** (also in `catalog`): `search_documents` (kind `track`/`album`/`playlist`/`short`, subject_id, artist_id, title_native, title_roman, tags text[], lyrics_excerpt, search_text, tsv tsvector, embedding vector(384) null until semantic search is built, updated_at). `search_text` joins the native title, the Roman transliteration and tags, normalised (unaccent, lower-case, Devanagari nukta and chandrabindu variants folded). Indexes: GIN on `tsv` and GIN `gin_trgm_ops` on `search_text`. Extensions: `pg_trgm`, `unaccent`; `vector` later. Rebuilt by the worker when a track, album or playlist changes; playlists are only indexed when `visibility` is not `private`.

## library (listener data)

| Table | Key columns | Rules |
|-------|-------------|-------|
| `playlists` | user_id, name, description, visibility (`private`/`unlisted`/`public`), cover_asset_id | count limited via `can()` |
| `playlist_tracks` | playlist_id, track_id, position (fractional text `COLLATE "C"`), added_at | fractional ordering so concurrent edits do not renumber; `COLLATE "C"` makes ORDER BY byte-wise so every client and the database agree |
| `saved_tracks`, `saved_albums` | user_id, track_id or album_id, saved_at | composite primary key |
| `share_links` | token (unique), subject_kind (`track`/`album`/`playlist`), subject_id, created_by, start_ms, created_at, expires_at, revoked_at, opens | public path `/s/<token>`; resolves only published subjects with `license_status = confirmed`; a private playlist needs `visibility` raised to `unlisted` first; open counts feed analytics |
| `user_tastes` | user_id, kind (`genre`/`language`/`mood`/`interest`), key, weight, created_at | composite primary key (user_id, kind, key); keys validated against vocabularies (`catalog.genres`, language and mood lists); read only for that user's recommendations; exported and deleted with the account |
| `follows` | user_id, artist_id, followed_at | |
| `play_events` | user_id, track_id, started_at, ms_played, source_kind, source_id, device, country | partitioned by month; the worker creates next month's partition ahead of time (`jobs` kind `partition_maintenance`) because a missing partition makes inserts fail; retention drops old detail |
| `play_stats_daily` | artist_id, track_id, day, plays, listeners, ms_played | rebuilt from events |

## billing

| Table | Key columns | Rules |
|-------|-------------|-------|
| `plans` | id, key (`free`/`premium`), name, price_minor, currency, interval, active | |
| `plan_entitlements` | plan_id, feature, enabled, limit_int | feature keys such as `playlists.max`, `audio.quality_hi`, `offline` |
| `subscriptions` | user_id, plan_id, status (`trialing`/`active`/`past_due`/`canceled`), period_start, period_end, cancel_at, provider, provider_customer_id, provider_subscription_id | provider columns empty until a provider is chosen |
| `entitlement_overrides` | user_id, feature, value, reason, expires_at | owner-granted exceptions |
| view `v_user_entitlements` | user_id, feature, enabled, limit_int | the only input to `entitlements.can()` |

## studio (replaces `meta.json`)

**Stage 1 (NAV-4, shipped as `studio/0001`):** `items.doc` (jsonb) is the canonical, lossless copy of the old `meta.json`, plus `export_sha` and `version`; `item_history`, `approvals`, `publications` and `schedules` are projections of it, rebuilt in the same transaction on each save. `jobs` and `workers` shipped in stage 2 (`studio/0002`): one active job per item (a partial unique index on `slug` for queued and running, stricter than the per-kind key below), `progress` and `status_text` carry what the portal showed from the old RUN and STATUS dictionaries, a lease (`locked_until`) with retry up to `max_attempts` (default 2), `cancel_requested` for Stop. `steps` and `item_settings` remain for later; a field moves from `doc` to a typed table only when its readers move. Until then `doc` wins (constitution III).

| Table | Key columns | Rules |
|-------|-------------|-------|
| `items` | artist_id, slug (unique across all artists), type (`music`/`inspiration`/`podcast`), title, state, track_id, created_at, updated_at | `track_id` set when published. `slug` is globally unique (true today: `song-001` is one namespace) so `analytics` can reference it without an artist; `updated_at` drives the `meta.json` write-through export and conflict detection |
| `item_history` | item_id, at, actor_id, event, detail jsonb | the old `history` list; a "changes requested" event carries the reviewer's note (FR-023) |
| `approvals` | item_id, gate, content_hash (nullable), approved_at, approved_by | invalid when the content hash changes (constitution III). **Backfill rule:** approvals in `meta.json` carry no hash, so they are imported with `content_hash = NULL` meaning *legacy-approved*: valid until the content next changes, after which the gate needs a fresh approval. Without this every published song would come back unapproved |
| `steps` | item_id, step, status, attempts, started_at, finished_at, error | unique (item_id, step); `attempts` is a counter, as `meta.json` keeps it today |
| `schedules` | item_id, platform, run_at, status (`waiting`/`done`/`missed`/`blocked`), attempts, done_at | scheduler claims with `FOR UPDATE SKIP LOCKED` |
| `publications` | item_id, platform, kind (`video`/`short`/`reel`/`feed`), external_id, url, published_at | unique (item_id, platform, kind). One per platform **and kind**: prod `song-001` has `published.youtube` plus `youtube_items` x2 (the full video and the Short), and Instagram feed and reel can differ the same way |
| `item_settings` | item_id, key, value jsonb | visuals options, generator ids, cloud and cleanup records |
| `jobs` | id, item_id (nullable), kind, status (`queued`/`running`/`done`/`failed`), run_at, attempts, max_attempts, locked_by, locked_until, started_at, finished_at, error, payload jsonb | the queue for the worker: claimed with `FOR UPDATE SKIP LOCKED`, retried up to `max_attempts`, a partial unique index on (kind, item_id) `WHERE status IN ('queued','running')` stops duplicates (two schedulers cannot both enqueue the same work); replaces the in-process job dictionary |

## analytics

Shipped in NAV-3 as `plugins/navaan-studio/db/migrations/analytics/0001_analytics.sql`: the 28 tables the SQLite file had (including `yt_hashtag_posts` and `comment_replies`), with `bigint` and `double precision`, **timestamps still UTC ISO text, flags 0/1, JSON as text**, so no query changed. Typed columns are a later migration, `analytics/0002`: ISO text times to `timestamptz`, `hidden`/`is_own` to `boolean`, `raw_json`/`stats_json` to `jsonb`, shipped in the same release as the code changes that stop comparing flags to 0/1. Account tables gain `artist_id`. `media.slug` and `yt_videos.slug` become foreign keys to `studio.items(slug)` after the studio backfill (possible because `items.slug` is globally unique).

## Migration notes

- Migrations are per schema: `plugins/navaan-studio/db/migrations/<schema>/NNNN_name.sql`, applied by `db_migrate.py` and recorded in `core.schema_migrations (schema_name, version, name)`. Order of work: `analytics/0001` (done), `studio/0001` (P2), `core/0001` (P3), `catalog/0001` (P4), `library/0001` and `billing/0001` (P5).
- Analytics data copy: done, automatic at the first start, verified by row count and checksum (NAV-3); the SQLite file is the rollback copy.
- Studio backfill: reads every `songs/*/meta.json`, idempotent, dry-run first, reports unmapped keys. Top-level scalars (`lyrics_loops`, `suno_url`, `suno_model`) and the `cloud` and `cleanup` blocks go to `item_settings`; `approvals` import with `content_hash = NULL` (legacy-approved).
- Every migration works with the previous release (expand now, contract in a later release). The release pipeline rolls back the image, not the schema.
