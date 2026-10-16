# Implementation Plan: NAVAAN platform foundation

**Branch**: `002-platform-foundation` (not created; do not `git checkout` in the main worktree, use a worktree) | **Date**: 2026-10-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification plus the approved platform plan (`~/.claude/plans/i-feel-the-webiste-smooth-rabbit.md`, approved 2026-10-15). Mockup for sign-off: https://claude.ai/artifact/GZKYF63xtJS2EgpQpTthpv

## Summary

Move analytics (SQLite) and song/pipeline state (`meta.json`) into one Postgres 17 database running as a container on the VM, add users, roles, catalog, albums, playlists and plan/entitlement tables, serve audio by short-lived signed links, and rebuild the front end as a mobile-first React app with a Studio / Library / Albums / Settings structure. The Python API stays; state lives in Postgres, bytes in object storage, disk is scratch.

## Technical Context

**Language/Version**: Python 3.13 (existing stdlib server), TypeScript 5 / React 18 for the web app
**Primary Dependencies**: FastAPI + uvicorn (listener API first, studio routes ported gradually), `psycopg[binary,pool]` v3, Postgres extensions `pg_trgm`, `unaccent` (and `pgvector` later), OCI SDK (signed URLs), Pillow (existing, image variants); web build only: Vite, React, Tailwind, shadcn/ui (Radix), Motion, TanStack Query
**Storage**: PostgreSQL 17 (container, volume `/opt/navaan/data/pg`); OCI Object Storage for audio, video, covers; pipeline workdir on disk
**Testing**: existing `plugins/navaan-studio/tests` moved onto Postgres (CI service container); migration lint; negative-access tests; Playwright at 390x844 and 1280x800; axe-core; Lighthouse
**Target Platform**: Oracle VM (ARM Linux, Docker) plus Mac for local development
**Project Type**: web application (API + SPA) with a pipeline plugin
**Performance Goals**: see SC-006 (placeholders under 1 s, play under 3 s on throttled mobile)
**Design**: Midnight Cinema (dark) and Ivory & Gold (light) with soft glass; Cormorant Garamond + Noto Serif Devanagari for titles, Manrope + Noto Sans Devanagari for the interface; mockup https://claude.ai/artifact/GZKYF63xtJS2EgpQpTthpv
**Constraints**: rollback of image without rollback of schema (expand/contract); VM memory shared with other apps; secrets only through Vault
**Scale/Scope**: one artist, hundreds of tracks, thousands of listeners at most in the first year; `play_events` partitioned monthly

## Constitution Check

Gate against `.specify/memory/constitution.md` v2.0.0.

| Principle | Status | Note |
|-----------|--------|------|
| I Humans own the gates | Pass | Approval undo window applies only to routine gates; spend and go-public keep explicit confirmation (FR-006). Pricing/charging stays a human decision. |
| II Secrets | Pass | DB password and DSN through Vault tmpfs; no payment key stored. |
| III Postgres is the state | Pass (this plan implements it) | Migration is one area at a time: analytics (P1), studio state (P2). Source of truth named per phase; `meta.json` write-through for one release. |
| IV No hidden spend | Pass | No paid service added. Email provider and payment provider are separate decisions. |
| V Safe by default | Gate | Listener signup stays closed until rate limits, email verification and `/security-deep-review` are done. Studio routes unreachable by listener role (negative tests). |
| VI One plugin | Pass | DB service, backup and migrations runner under `deploy/` and `db/`, not in the plugin. |
| VII Dependencies | Pass | New dependencies are the named allowed ones only. |
| VIII Prove it | Pass | Row-count/checksum comparison, restore drill, rollback rehearsal in the verification plan. |
| IX Don't clobber | Watch | Main worktree has others' uncommitted changes; work in a worktree and commit only own hunks. |
| X Recoverable | Pass | Daily `pg_dump`, pre-release dump, SQLite file kept 14 days after cutover. |
| XI Rights | Gate | Suno commercial-use check by Nj before any track goes behind a subscription (FR-017). |
| XII Many users | Pass | `user_id`/`artist_id` scoping, per-route permissions, negative tests. |
| XIII Schema discipline | Pass | Numbered SQL migrations, expand/contract, backup before migrating releases. |
| XVI Start simple | Pass | One VM, one database, search and queue inside Postgres, Cloudflare free tier in front; triggers below. PITR, error tracking and uptime check gate public listener signup. |
| XIV Mobile-first, themes | Pass | 390 px first; three token layers (primitive, semantic, component), one file per theme under `web/src/themes/`, Tailwind and shadcn mapped to the semantic variables, colour-literal lint in the build (FR-022, SC-010). |
| XV People's data | Pass | Export/delete endpoints, no PII in logs, no card data. |

No violations that need a Complexity Tracking entry.

## Project Structure

### Documentation (this feature)

```text
specs/002-platform-foundation/
├── spec.md
├── plan.md          # this file
├── data-model.md    # tables, keys, rules
└── tasks.md         # created by /speckit-tasks (not yet)
```

### Source code (repository root)

```text
db/migrations/                      # 0001_core.sql ... numbered, plain SQL, one runner
plugins/navaan-studio/
├── scripts/
│   ├── analytics_db.py             # psycopg, same connect/rows/one surface
│   ├── repo/                       # items.py, users.py, catalog.py, library.py
│   ├── entitlements.py             # can(user, feature)
│   ├── auth.py                     # primitives kept, storage moved to core.*
│   └── navaan_ui.py                # routes by permission, signed play URLs, album API
├── web/                            # Vite app: studio + listener route trees
└── tests/                          # on Postgres
deploy/
├── compose.yml                     # + postgres service
├── backup/backup.sh                # + pg_dump to OCI bucket
└── Dockerfile                      # + postgresql-client
docs/DATA_MODEL.md                  # ER diagram and rationale (via /arch-diagram)
```

**Structure decision**: keep the plugin as the single source of scripts; the web app is a build-time subfolder that ships static files the Python server serves; deployment files stay under `deploy/`.

## Hostnames and edge (domain `navaan.online`, bought 2026-10-15)

| Host | Serves | Notes |
|------|--------|-------|
| `navaan.online` | everything public: listener app, songs, albums, playlists, `/s/<token>` share links, public preview | `www.` redirects here; HSTS; listener signup stays closed until reviewed |
| `studio.navaan.online` (confirmed) | studio (owner) app and `/api/studio/*` | separate host so cookies, CSP and rate limits are separate; same container, routed by Host |
| `navaan.njlabs.dev` | current studio | stays during the transition, then 301 to the studio host |

- **DNS** (at the registrar, done by Nj): A/AAAA for the apex, `www` and `studio` to the VM (163.192.110.178 per spec 001); plus mail records below.
- **nginx** (`deploy/nginx/`): one vhost per host in the shared engagehub-nginx, own certificates per host through the existing certbot webroot flow, listener and studio throttle zones separate; changes to the shared nginx stay minimal and backed up (constitution X).
- **App**: `NAVAAN_PUBLIC_HOST` becomes a list; the server picks the surface from the Host header and refuses studio routes on the listener host and the reverse; `_host_ok` in `navaan_ui.py` and the deploy smoke checks (`deploy/deploy-run.sh`, `.github/workflows/deploy-prod.yml`) learn the new hosts.
- **Passkeys**: the WebAuthn relying-party id is the host name (`auth.py:rp_of`), so owner passkeys registered on `navaan.njlabs.dev` do not work on the studio host; re-register them. TOTP and recovery codes are unaffected.
- **Email**: sending domain `navaan.online` with SPF, DKIM and DMARC records; provider still to choose (OCI Email Delivery, SES or similar).
- **Later**: Google and Apple sign-in need the domain's verified redirect URIs; this is why the final listener host should be settled now.

## Logging and observability (FR-034, FR-035, constitution XVII)

Today: no use of the `logging` module anywhere; `print()` for output (about 60 calls in `navaan.py` alone); per-step files under `songs/<slug>/logs/*.log` (about 9 per song); business history lines in `meta.json`; about 110 handlers that swallow an exception (`except ...: pass`, `return` or `continue`, 26 in `navaan_ui.py`, 10 in `auth.py`); 19 empty `catch(e){}` blocks in `ui.html`; the release log `/var/log/navaan-deploy.log`.

Design (all stdlib, no new dependency):
- **One module** `navaan_log.py` on `logging` with a JSON formatter, `contextvars` carrying `request_id`, `job_id`, `item`, `step`, `user_id`; `get_logger(component)`; `log_exception(...)` helper used in every handler.
- **Sinks:** JSON lines to stdout (Docker's json-file driver, already rotated in `deploy/compose.yml`, limits raised for the app) and a rotated file `/var/log/navaan/app.jsonl` on a mounted volume (14 days). Later, Grafana Alloy or Promtail tails stdout and ships to Loki; labels stay low-cardinality (`service`, `env`, `level`, `component`) and ids stay in the record body.
- **Requests:** a middleware (the stdlib handler now, FastAPI later) logs method, route, status, duration, bytes, `request_id`; the id is returned as `X-Request-Id` and shown in the UI error toast so a report can be traced.
- **Pipeline runs:** the step runner streams each subprocess's stdout and stderr line by line into the logger with `job_id`, `item`, `step`; one consolidated run log (`runs/<job_id>.jsonl`, referenced by `studio.jobs.log_ref`) holds the whole run in order. The small per-step `.log` files stay as artifacts.
- **Browser:** `reportError()` plus `window.onerror`, `unhandledrejection`, failed API calls and a React error boundary post to `/api/client-log` (size-capped, rate-limited, scrubbed, same-site). The `api()` helper gets the missing `.catch`.
- **No silent catch:** a CI test walks the code (Python `ast`, ESLint `no-empty` and a custom rule for JS) and fails on an empty handler without a `# expected: <reason>` comment plus a debug log. The existing ~110 Python and 19 JS handlers are triaged one by one: log, handle, or justify.
- **Scrubbing:** a filter masks tokens, `Authorization` and cookie values, passwords, email addresses and query strings before anything is written; a test feeds known secrets through every path.
- **Not in business history:** `studio.item_history` keeps owner-meaningful events; technical logs never go there.
- **Sequencing:** the logger and the no-empty-catch check are small and independent, so do them first, before P1, so the Postgres migration and later work are debuggable.

## Scale ladder (constitution XVI): the trigger for each next step

| Area | Now (1 to 100 users) | Next step | Trigger |
|------|----------------------|-----------|---------|
| Search | Postgres full-text + trigram + unaccent, Roman transliteration column | Meilisearch or Typesense | over ~1M documents, or p95 search over 200 ms, or facets Postgres cannot serve |
| Semantic | none | `pgvector` in the same database, local embedding model | product wants "songs like this"; catalog over a few thousand tracks |
| API | stdlib studio server + FastAPI listener API | all routes on FastAPI, 2+ uvicorn workers | listener API p95 over 300 ms or CPU over 70% sustained |
| Jobs | worker process on a Postgres queue | Redis queue or similar | over ~50 jobs/s or need for fan-out workflows |
| Database | one Postgres container | bigger VM, PgBouncer, read replica, then managed | connections near the limit, or CPU/IO saturated, or recovery objective tighter than a nightly dump + WAL |
| Delivery | OCI signed URLs, Cloudflare free tier for images and static files | HLS renditions, paid CDN | audio start over 3 s on mobile, or egress cost rising |
| Events | partitioned `play_events` in Postgres | separate events database (ClickHouse, BigQuery) | hundreds of millions of rows or analytics queries slowing listeners |
| Compute | one ARM VM | second VM behind a load balancer | single-VM CPU/RAM saturated, or availability target above one VM |

## Phases

| Phase | Delivers | Spec stories |
|-------|----------|--------------|
| P0 | Mockup sign-off (dark + light, desktop + 390 px, studio + listener) | 2, 3, 4, 5 (look and flow) |
| P1 | Postgres container, backup, migration runner, analytics moved | 1 |
| P2 | Studio state in Postgres, `jobs` queue and separate worker (FR-031), scheduler claim, `meta.json` write-through | 1 |
| P3 | Users, sessions, roles, permissions, per-session CSRF, `/api/me`; listener API skeleton on FastAPI/uvicorn | 4 (access), FR-011, FR-020 |
| P4 | Catalog, albums, assets, image variants, signed play URLs, share links with preview cards, `search_documents` and the search module (FR-030) | 3, 6 |
| P5 | Playlists, saves, play events, plans and entitlements; PITR, error tracking, uptime check before opening signup (FR-032) | 4, 5 |
| UI | Shell, design system, Studio screens, Library, Albums, listener app | 2, 3, 4, 6 |

Each phase is one release through the existing pipeline (feat/* -> develop -> main). The data model is reviewed with Nj before any migration is written.

## Risks

- Rights to generated songs (FR-017) must be confirmed before charging.
- Public listener signup is new attack surface; keep it closed until reviewed.
- Rollback restores the image, not the schema; migrations must be expand/contract.
- VM capacity unknown; measure before adding Postgres.
- Email and payment providers undecided.
