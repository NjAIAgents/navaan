<!--
Sync Impact Report
Version: 1.0.0 -> 2.4.0 (2.4.0 MINOR: new XVII nothing fails silently (structured, consolidated, Loki-ready logging, no empty catch). 2.3.0 MINOR: VII allows FastAPI/uvicorn, pg_trgm, unaccent, pgvector; new XVI start simple, scale on evidence. 2.2.0 MINOR: XIV allows user personalisation within automatically checked contrast limits. 2.0.0 MAJOR: principles III and V redefined, VII relaxed; four principles added. 2.1.0 MINOR: XIV now requires token-based, swappable themes)
Modified: III "Files are the state" -> "Postgres is the state, files are scratch"; V "Safe by default" now separates the owner studio from listener surfaces; VII names allowed dependencies; XI adds rights and origin of tracks
Added: XII Many users, least privilege; XIII Schema discipline; XIV Mobile-first and accessible; XV People's data; XVI Start simple, scale on evidence; XVII Nothing fails silently
Templates to check: plan-template.md (Constitution Check lists XII-XVII), spec-template.md, tasks-template.md
Follow-up: specs/001-run-navaan-on-server FR-019 and its "single owner" assumption are superseded by specs/002-platform-foundation
-->
# NAVAAN Constitution

Applies to the plugin `plugins/navaan-studio`, the studio (owner) app, the listener app, the database, and the server deployment. Owner: Nj (Navjyot Nishant).

## Core Principles

### I. Humans own the gates
Approving a gate, publishing, making a video public, deleting, and any spend are human decisions. Automation, scheduling, and Claude never approve a gate on the user's behalf. Scheduling only picks a time; missing approvals mean wait, then give up visibly. Charging a listener or changing a price is also a human decision.

### II. Secrets stay out of sight
No token, password, key, or recovery code in the repo, the Claude project, chat, logs, images, or compose files. Secrets live in Vault (server) or `~/.config/navaan` with mode 600 (Mac). Each component gets the least access it needs. This includes the database password and any payment-provider key.

### III. Postgres is the state, files are scratch
Durable state (items, approvals, schedules, users, catalog, playlists, subscriptions, analytics) lives in Postgres. Bytes (audio, video, covers) live in object storage. Working files on disk (lyrics, timings, renders) are scratch and can be rebuilt. A step is idempotent and is derived from recorded state plus recorded approvals, so any run can be repeated or resumed safely. Approvals tied to content (a hash) become invalid when the content changes. Until an area is migrated, its files remain the state; a migration moves one area at a time and names which side is the source of truth during the move.

### IV. Local first, no hidden spend
Prefer local rendering and tools. Credit-based or paid services are optional, clearly labelled, and behind a gate.

### V. Safe by default, explicit to open up
The studio listens on localhost with no change in behaviour. Public hosting, proxy trust, and headless mode are turned on only by explicit environment settings. Every studio (owner) surface sits behind login with a second factor, CSRF protection, and per-IP rate limits. Listener surfaces are a separate surface with their own controls (verified email, per-account and per-IP rate limits, CSRF, optional passkey or second factor); no studio route is reachable by a listener role, and listener signup stays closed until those controls are in place and reviewed.

### VI. One plugin, many places to run it
The plugin is the single source of truth for skills and scripts. Server files (Dockerfile, compose, nginx, Vault sync, database backup) live under `deploy/`, outside the plugin. Config and data are never baked into an image. The server image is built from a known commit.

### VII. Small dependency surface
Standard library first. Each new dependency needs a reason and must work on Mac and on ARM Linux. Allowed by name, with reason: a PostgreSQL driver (`psycopg`); the OCI SDK for signed URLs; an ASGI web framework and server (FastAPI with uvicorn) for the listener API, and for the studio API as routes are ported; the web build toolchain (React, TypeScript, Vite, Tailwind), which runs at build time and ships static files; and the PostgreSQL extensions `pg_trgm`, `unaccent` and, when semantic features are built, `pgvector`. A separate search engine (Meilisearch or Typesense) is allowed only after a named trigger in the plan is hit. Anything else needs a note in the plan.

### VIII. Prove it before saying done
Changes are checked by running them: scripted tests, syntax checks, a real render, a dry run. A claim of success states what was actually run and what was not. Database changes are proved on a copy of real data with row counts and a restore drill.

### IX. Don't clobber shared work
Never discard uncommitted changes. Commit only your own hunks. Touch other people's or other sessions' files only as far as needed, and say so.

### X. Recoverable and visible
Every action leaves a history line. Retries are bounded. Each deployment step has a rollback. Changes to shared infrastructure (EngageHub nginx, Vault) are minimal, backed up, and made at a quiet time.

### XI. Honest data and clear rights
Test with synthetic or the user's own material, never someone else's personal photos. Do not reproduce copyrighted lyrics, art, or characters. Before a track is placed behind a subscription or sold, its origin and licence (for generated music, the generator and the plan tier in force when it was made) are recorded and checked by Nj.

### XII. Many users, least privilege
Every row a user can reach is scoped by owner (`user_id`) or tenant (`artist_id`). Every route declares the permission it needs and is checked on the server; the UI only mirrors it. Each new scoped table ships with a test that user A cannot read or change user B's data. Feature limits and paid features are decided in one place (`can(user, feature)`), never by scattered plan-name checks.

### XIII. Schema discipline
All schema changes are versioned SQL migrations applied by one runner. A migration must work with the previous release too (expand, then contract in a later release), because a failed release rolls the image back but not the schema. Take a backup before any release that carries a migration. Backups are tested by restoring them.

### XIV. Mobile-first and accessible
Screens are designed at 390 px first and scaled up. Touch targets are at least 44 px, text at least 12 px, keyboard focus is visible, controls are real buttons and links, and motion respects reduced-motion settings. Appearance comes from named themes built from design tokens (palette, surfaces, text, accents, material such as blur, depth); screens and components use tokens only and never contain colour literals, so a theme can be changed or added without touching a screen. At least a dark and a light theme ship. Users may personalise within limits (a dark-to-light tone and an accent from a fixed palette); any choice they can make must keep text, buttons and status colours at 4.5:1 contrast or better, and this is checked automatically across all combinations.

### XV. People's data
Collect the least personal data that works. Listeners can export and delete their account. No personal data or secrets in logs. Card data is never stored; payment details stay with the payment provider.

### XVI. Start simple, scale on evidence
Run the simplest thing that serves today's users (one VM, one database, one search index inside the database, a Postgres-backed job queue) and write down the measurable trigger that justifies the next step (a separate search engine, a read replica, a second server, an events database). Each external capability (search, object storage, email, payments, error tracking) sits behind one module with one interface, so replacing it later changes one place. Before real listeners are admitted there must be tested point-in-time recovery, error tracking and an uptime check.

### XVII. Nothing fails silently
Every failure is caught on purpose and logged once, as a structured record with enough context to act on (what, where, which request, job or item, how long, the error type and stack). An empty `except` or `catch` is not allowed; a handler that deliberately ignores an error says why in a comment and still logs at debug level. Logs go to one consolidated stream that can be shipped to a log service (Loki or similar) without changing the code, never contain secrets or more personal data than an id, and are kept long enough to investigate a release.

## Working Agreements

- Replies are terse and concrete. Questions to the user are full sentences.
- Do not restart the local portal while a pipeline job runs; scheduled jobs live in that process.
- Continuity notes are written for decisions, blockers, and unfinished work.
- Server files (Dockerfile, compose, nginx, Vault sync, database backup) live under `deploy/`, never inside the plugin.
- Work is tracked in the project tracker; a phase of the platform plan is one story.

## Governance

This constitution supersedes other practices for this repository. Amendments are proposed in a spec or plan, approved by Nj, and recorded with a new version and date. A plan that conflicts with a principle must name the principle and the reason, and needs Nj's approval before work starts. Every plan and review checks compliance.

**Version**: 2.4.0 | **Ratified**: 2026-10-13 | **Last Amended**: 2026-10-15
