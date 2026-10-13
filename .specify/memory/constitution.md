# NAVAAN Studio Constitution

Applies to the plugin `plugins/navaan-studio`, the local portal, and the server deployment. Owner: Nj (Navjyot Nishant).

## Core Principles

### I. Humans own the gates
Approving a gate, publishing, making a video public, deleting, and any spend are human decisions. Automation, scheduling, and Claude never approve a gate on the user's behalf. Scheduling only picks a time; missing approvals mean wait, then give up visibly.

### II. Secrets stay out of sight
No token, password, key, or recovery code in the repo, the Claude project, chat, logs, images, or compose files. Secrets live in Vault (server) or `~/.config/navaan` with mode 600 (Mac). Each component gets the least access it needs.

### III. Files are the state
Steps are derived from files plus recorded approvals, so any run can be repeated or resumed safely. A step is idempotent. Approvals tied to content (a hash) become invalid when the content changes.

### IV. Local first, no hidden spend
Prefer local rendering and tools. Credit-based or paid services are optional, clearly labelled, and behind a gate.

### V. Safe by default, explicit to open up
The portal listens on localhost with no change in behaviour. Public hosting, proxy trust, and headless mode are turned on only by explicit environment settings. A public portal always sits behind login with a second factor, CSRF protection, and per-IP rate limits.

### VI. One plugin, many places to run it
The plugin is the single source of truth for skills and scripts. Server files (Dockerfile, compose, nginx, Vault sync) live under `deploy/`, outside the plugin. Config and data are never baked into an image. The server image is built from a known commit.

### VII. Small dependency surface
Standard library first. Each new dependency needs a reason and must work on Mac and on ARM Linux.

### VIII. Prove it before saying done
Changes are checked by running them: scripted tests, syntax checks, a real render, a dry run. A claim of success states what was actually run and what was not.

### IX. Don't clobber shared work
Never discard uncommitted changes. Commit only your own hunks. Touch other people's or other sessions' files only as far as needed, and say so.

### X. Recoverable and visible
Every action leaves a history line. Retries are bounded. Each deployment step has a rollback. Changes to shared infrastructure (EngageHub nginx, Vault) are minimal, backed up, and made at a quiet time.

### XI. Honest data
Test with synthetic or the user's own material, never someone else's personal photos. Do not reproduce copyrighted lyrics, art, or characters.

## Working Agreements

- Replies are terse and concrete. Questions to the user are full sentences.
- Do not restart the local portal while a pipeline job runs; scheduled jobs live in that process.
- Continuity notes are written for decisions, blockers, and unfinished work.
- Server files (Dockerfile, compose, nginx, Vault sync) live under `deploy/`, never inside the plugin.

## Governance

This constitution supersedes other practices for this repository. Amendments are proposed in a spec or plan, approved by Nj, and recorded with a new version and date. A plan that conflicts with a principle must name the principle and the reason, and needs Nj's approval before work starts. Every plan and review checks compliance.

**Version**: 1.0.0 | **Ratified**: 2026-10-13 | **Last Amended**: 2026-10-13
