# Data Model: NAVAAN platform foundation

PostgreSQL 17. Six schemas. Draft for review with Nj; no migration is written until this is approved.

## Conventions

- Primary keys are `uuid` (`gen_random_uuid()`; `uuidv7()` when on PG 18). Existing human slugs (`song-001`, `insp-001`) stay as a unique `slug` so URLs and file paths still map.
- All times are `timestamptz` in UTC. Flags are `boolean`. Open payloads (raw API responses) are `jsonb`; everything else is typed columns.
- States are `text` with a `CHECK` list. Every foreign key has an index. Mutable rows carry `created_at` and `updated_at`.
- Soft delete (`deleted_at`) only where a person can restore. Triggers only maintain `updated_at`.
- Every catalog, studio and analytics row carries `artist_id`; every listener row carries `user_id`. Queries are always scoped by one of them (constitution XII).

## core

| Table | Key columns | Rules |
|-------|-------------|-------|
| `users` | id, email (citext, unique), display_name, status, email_verified_at, locale, preferences jsonb | one row per person; `preferences.appearance` holds `{tone: 0..10, accent: key, match_device: bool}`, `preferences.personalise` holds the taste on/off switch, notifications go here too |
| `user_profiles` | user_id (pk), display_name, avatar_asset_id, bio, country, languages text[], updated_at | no date of birth or phone number (constitution XV) |
| `credentials` | user_id, kind (`password`/`passkey`/`totp`/`recovery`), hash or public key or secret, label, last_used_at | owner's existing auth migrates here |
| `identities` | user_id, provider (`google`/`apple`/...), subject, email, linked_at | unique (provider, subject); empty until those providers are added |
| `sessions` | token_hash (pk), user_id, csrf_token, ip, user_agent, expires_at, revoked_at | replaces `sessions.json` and the global CSRF token |
| `roles` | id, name (`owner`/`editor`/`listener`) | |
| `user_roles` | user_id, role_id, artist_id (nullable) | artist-scoped roles for later |
| `role_permissions` | role_id, permission | e.g. `studio.approve`, `library.view`, `playlists.write` |
| `audit_log` | actor_id, action, subject, at, detail jsonb | approvals, publishes, role changes |
| `login_attempts` | key (account or ip), at, ok | replaces in-memory throttle |
| `schema_migrations` | version, applied_at | written by the runner |

## catalog

| Table | Key columns | Rules |
|-------|-------------|-------|
| `artists` | id, slug, name, status, theme jsonb | NAVAAN is the only row at first; `theme` can override a few accent tokens for a per-artist look later |
| `tracks` | artist_id, slug, title, language, genre, duration_ms, explicit, lyrics_text, status, published_at, origin, license_status, studio_item_id | `license_status` must be `confirmed` before any entitlement-gated use (FR-017) |
| `albums` | artist_id, slug, title, kind (`album`/`ep`/`single`), status (`draft`/`scheduled`/`published`), release_date, description, cover_asset_id | |
| `album_tracks` | album_id, track_id, position | unique (album_id, position), deferrable, so reorder is one transaction |
| `assets` | owner_kind, owner_id, role (`audio`/`cover`/`video`/`reel`/`lyrics_timed`), storage_key, mime, bytes, sha256, duration_ms, width, height, dominant_colour, blurhash, derived_from | several renditions per track or cover; object storage is the source of truth; `lyrics_timed` holds line timings (from the caption timing step) for highlighted lyrics; plain text stays in `tracks.lyrics_text` |
| `genres`, `track_genres` | name; track_id, genre_id | |

**Search** (also in `catalog`): `search_documents` (kind `track`/`album`/`playlist`/`short`, subject_id, artist_id, title_native, title_roman, tags text[], lyrics_excerpt, search_text, tsv tsvector, embedding vector(384) null until semantic search is built, updated_at). `search_text` joins the native title, the Roman transliteration and tags, normalised (unaccent, lower-case, Devanagari nukta and chandrabindu variants folded). Indexes: GIN on `tsv` and GIN `gin_trgm_ops` on `search_text`. Extensions: `pg_trgm`, `unaccent`; `vector` later. Rebuilt by the worker when a track, album or playlist changes; playlists are only indexed when `visibility` is not `private`.

## library (listener data)

| Table | Key columns | Rules |
|-------|-------------|-------|
| `playlists` | user_id, name, description, visibility (`private`/`unlisted`/`public`), cover_asset_id | count limited via `can()` |
| `playlist_tracks` | playlist_id, track_id, position (fractional text), added_at | fractional ordering so concurrent edits do not renumber |
| `saved_tracks`, `saved_albums` | user_id, track_id or album_id, saved_at | composite primary key |
| `share_links` | token (unique), subject_kind (`track`/`album`/`playlist`), subject_id, created_by, start_ms, created_at, expires_at, revoked_at, opens | public path `/s/<token>`; resolves only published subjects with `license_status = confirmed`; a private playlist needs `visibility` raised to `unlisted` first; open counts feed analytics |
| `user_tastes` | user_id, kind (`genre`/`language`/`mood`/`interest`), key, weight, created_at | composite primary key (user_id, kind, key); keys validated against vocabularies (`catalog.genres`, language and mood lists); read only for that user's recommendations; exported and deleted with the account |
| `follows` | user_id, artist_id, followed_at | |
| `play_events` | user_id, track_id, started_at, ms_played, source_kind, source_id, device, country | partitioned by month; retention removes detail |
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

| Table | Key columns | Rules |
|-------|-------------|-------|
| `items` | artist_id, slug, type (`music`/`inspiration`/`podcast`), title, state, track_id, created_at | `track_id` set when published |
| `item_history` | item_id, at, actor_id, event, detail jsonb | the old `history` list; a "changes requested" event carries the reviewer's note (FR-023) |
| `approvals` | item_id, gate, content_hash, approved_at, approved_by | invalid when the content hash changes (constitution III) |
| `steps` | item_id, step, status, attempts, started_at, finished_at, error | |
| `schedules` | item_id, platform, run_at, status (`waiting`/`done`/`missed`/`blocked`), attempts, done_at | scheduler claims with `FOR UPDATE SKIP LOCKED` |
| `publications` | item_id, platform, external_id, url, published_at | one per platform per item |
| `item_settings` | item_id, key, value jsonb | visuals options, generator ids, cloud and cleanup records |
| `jobs` | id, item_id (nullable), kind, status (`queued`/`running`/`done`/`failed`), run_at, attempts, max_attempts, locked_by, locked_until, started_at, finished_at, error, payload jsonb | the queue for the worker: claimed with `FOR UPDATE SKIP LOCKED`, retried up to `max_attempts`, a unique key per (kind, subject) stops duplicates; replaces the in-process job dictionary |

## analytics

The 27 existing tables move as they are into schema `analytics` with typed columns: ISO text times to `timestamptz`, `hidden`/`is_own` to `boolean`, counts to `bigint`, rates to `numeric`, `raw_json`/`stats_json` to `jsonb`. Keys and indexes are kept. Account tables gain `artist_id`. `media.slug` and `yt_videos.slug` become foreign keys to `studio.items(slug)` after the studio backfill.

## Migration notes

- Order: `0001_core`, `0002_analytics` (from `analytics_schema.sql`), `0003_studio`, `0004_catalog`, `0005_library_billing`.
- Analytics data copy: per-table `COPY`, row count and column checksum comparison, SQLite file kept 14 days.
- Studio backfill: reads every `songs/*/meta.json`, idempotent, dry-run first, reports unmapped keys.
- Every migration works with the previous release (expand now, contract in a later release).
