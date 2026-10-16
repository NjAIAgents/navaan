# Changelog

All notable changes to NAVAAN Studio are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/) (0.y.z until the public listener app exists).
The version lives in `plugins/navaan-studio/.claude-plugin/plugin.json` and is mirrored in `.claude-plugin/marketplace.json` and `plugins/navaan-studio/web/package.json`; a test keeps them and this file in step.
Release steps are in `deploy/README.md` (Releasing). Only changes a person using or running the studio would notice are listed; refactors, tests and docs-only edits are in the git history.

## [Unreleased]

## [0.6.0] - 2026-10-16

### Added
- People, roles and permissions in Postgres (schema `core`). You are the `owner`; a `listener` role exists for the public app. The studio refuses any account without studio access, and `GET /api/me` says who you are and what you may do. The new app shows your name.
- An audit trail of sign-ins, failed sign-ins, sign-outs, password and passkey changes (who, what, when, from where, never a secret).

### Changed
- Sessions are in Postgres instead of `sessions.json` (existing sessions carry over, so the deploy does not sign you out), and each session has its own CSRF token instead of one for the whole server.
- The sign-in lockout (5 failures from one address, growing to 15 minutes) is in Postgres too, so it survives a restart. Your password, authenticator secret, passkeys and recovery codes stay in `auth.json` from Vault, out of database backups.

## [0.5.0] - 2026-10-16

### Added
- This changelog, and one version number across the plugin, the marketplace entry and the web app; the account menu in the new app shows it and the signed-in portal reports it. `deploy/bump-version.py` makes a release.
- A new app at `/app/` (React, Vite, TypeScript): Midnight Cinema and Ivory & Gold themes as data, glass panels with flat buttons, a mobile-first shell (sidebar and top bar on a desktop, header and floating tab bar on a phone), an account menu with the theme choice kept per device, and a Home screen on your real songs. The classic page stays at `/` and `/legacy` until every screen has moved over.

### Changed
- The sign-in page returns you to the page you asked for instead of always the classic page.

## [0.4.0] - 2026-10-15

### Added
- One structured JSON log for the whole app (web, pipeline and browser errors), a log per pipeline run, request ids on every reply, and a rule that no error is swallowed silently.
- Postgres as the database, in its own container with its own role: analytics moved over automatically at the first start, verified table by table, with the SQLite file kept as the rollback copy.
- The state of every song and inspiration (what `meta.json` held) in Postgres, with locked updates so the web page, the scheduler and a running step cannot overwrite each other; the scheduler claims a due step under that lock, so a post is published once. `meta.json` is still written as an export, and edits made to it outside the app are taken in.
- A job queue and a separate worker container: a run survives a deploy or a crash of the web server, an interrupted job is retried once, Stop works across processes, and the schedule runs in the worker.

### Changed
- Song and inspiration folders are local working data and are no longer tracked in git; media stays in the OCI bucket.
- The dev Postgres host port is configurable (`NAVAAN_PG_PORT`).

## [0.3.0] - 2026-10-15

### Added
- Music Short and Reel without a browser, with lyric captions on the reel; the reel is its own step and can be redone alone; watermark, reel fit and hook pick.
- Narration for inspiration shorts: upload a ready-made narration (audio plus subtitles), time lines from audio alone with Whisper, or have ElevenLabs speak it (voice choice, cache and cap).
- OpenAI pictures for inspiration shorts and for songs (director prompts, picture roles, cinematic look, matching people, 9:16), motion loops under the camera move, a Try the first 2 pictures card, a pictures-per-song setting with a run cap, and a Stop button.
- Restart Produce from a chosen step through the render.
- Gate switches in Settings, and media settings (voice, keys).

### Changed
- Faster: parallel speech recognition, a pre-blurred reel backdrop, an ffmpeg renderer for the Shots video and the reel (Remotion stays as the fallback), a cached caption-package check and media ETags (the song list went from about 2.3 s to 0.02 s).
- Instagram publishing on the server reads the OCI region from instance metadata; the song MP3 can be uploaded when Suno audio is unreadable.

### Fixed
- The song page no longer fails with `missing prompt_pack.json`; picture steps no longer repeat runs.

## [0.2.0] - 2026-10-13

### Added
- NAVAAN on the server: Docker deploy on the Oracle VM at `navaan.njlabs.dev`, secrets from Vault, nightly backup to the OCI bucket, and the server owning the publishing schedule.
- A release pipeline: CI on every pull request, deploy to production on a merge to `main` with an automatic roll back of the image when the health check fails.
- Sign-in with a password and authenticator code, passkeys alone, recovery codes, per-IP lockout, 7-day sessions that survive restarts; privacy and terms pages.
- Comment replies (Claude drafts, you approve and send each one) and best-time-to-publish suggestions for the schedule.

## [0.1.0]

### Added
- The studio plugin: lyrics, Suno song, visuals, synced captions, YouTube and Instagram publishing behind human approval gates, an analytics loop with recommendations, and a local web portal.

[Unreleased]: https://github.com/NjAIAgents/navaan/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/NjAIAgents/navaan/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/NjAIAgents/navaan/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/NjAIAgents/navaan/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/NjAIAgents/navaan/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/NjAIAgents/navaan/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/NjAIAgents/navaan/releases/tag/v0.1.0
