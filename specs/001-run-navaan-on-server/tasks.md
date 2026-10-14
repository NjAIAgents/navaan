# Tasks: Run NAVAAN on the Oracle VM at navaan.njlabs.dev

**Input**: `specs/001-run-navaan-on-server/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md)

**Format**: `- [ ] T### [P?] [US?] Description with file path`. `[P]` means different files, no dependency on unfinished tasks. Paths are repo-relative. Plugin means `plugins/navaan-studio`.

**Who runs what**: Tasks marked `(VM)` are commands Nj runs on the server and pastes back, because the sandbox cannot reach it. Tasks marked `(Nj)` need a human decision or secret that Claude must never handle. Everything else is code or docs Claude writes.

**Tests**: Plan asks for the promoted auth suite and the quickstart checks. No other TDD.

## Phase 1: Setup

- [X] T001 Commit only the auth hunks of `plugins/navaan-studio/scripts/navaan_ui.py` and `plugins/navaan-studio/scripts/ui.html`, leaving the other session's analytics hunks unstaged (constitution IX). Use `git add -p`, never `git checkout`.
  - Status: done. The other session's analytics hunks in `ui.html` went in their own commit (e31ac73), then this work in one commit; no `git add -p` was possible (non-interactive), so hunks were split by patch.
- [X] T002 [P] (VM) Verify open item 1: which Docker network `engagehub-vault` is on (`docker inspect engagehub-vault`). Record answer in `specs/001-run-navaan-on-server/research.md`.
- [X] T003 [P] (VM) Verify open items 2 and 3: certbot deploy hook (`cat /etc/letsencrypt/renewal/*.conf`), `docker compose version`, and how `/opt/engagehub/docker-compose.yml` declares Relayent's external network. Record in `research.md`.
- [X] T004 [P] Create `deploy/` skeleton with `deploy/README.md` (install, update, rollback outline) and empty subfolders `deploy/nginx`, `deploy/backup`, `deploy/vault`.

## Phase 2: Foundational (blocks all stories)

- [X] T005 Add env-driven switches to `plugins/navaan-studio/scripts/navaan_ui.py` per `contracts/environment.md`: `NAVAAN_PUBLIC_HOST` (extra allowed Host and https-aware Origin check), `NAVAAN_TRUST_PROXY` (client IP from `X-Real-IP`, scheme from `X-Forwarded-Proto`), `NAVAAN_BIND`. Defaults keep localhost behaviour.
- [X] T006 Pass `ip=` and `https=` from `navaan_ui.py` into `auth.state()` and `auth.handle_post()` in `plugins/navaan-studio/scripts/navaan_ui.py` so throttle keys on the real client and cookies get `Secure`.
- [X] T007 [P] Promote the scratch auth suite into `plugins/navaan-studio/tests/test_auth.py`: setup code, password plus TOTP, replay, recovery code, throttle per IP, cookie flags under `https=True`, 12 h and 2 h expiry.
- [X] T008 Run `python3 plugins/navaan-studio/tests/test_auth.py` and fix failures. Must pass before any story starts.
- [X] T009 Write `deploy/Dockerfile` (arm64: python 3.13, node 22, ffmpeg, Chrome libs, `claude` CLI, plugin installed from the repo, `cryptography`; no config or data baked in).
- [X] T010 Write `deploy/compose.yml` (project `navaan`, service `navaan`, network `navaan-network`, named volume for data, tmpfs for secrets, Docker secret for the AppRole secret id, no credentials in the file, port bound to the internal network only).
- [X] T011 (VM) Build the image on the VM and render the synthetic test song (quickstart step 2). Confirms headless Chrome on ARM (open item 4). Expect mp4 with audio under 10 minutes for 30 s.
  - Done 2026-10-13 on the VM: image built (about 5 minutes), 30 s synthetic render in 148 s with `--cpus 2 --memory 4g`, h264 1080x1920 plus aac, 30.0 s. Headless Chrome for linux-arm64 works (open item 4 closed).
  - Status: image built and a 30 s synthetic render passed in Docker on an arm64 Mac (19 s, h264 + aac). The real check on the VM is still Nj's.

**Checkpoint**: portal code is env-safe, tests pass, image builds and renders.

## Phase 3: User Story 1, open NAVAAN and sign in safely (P1)

**Goal**: only the sign-in page is visible at https://navaan.njlabs.dev, behind a shared password, over valid TLS.
**Independent test**: quickstart steps 4 to 8.

- [X] T012 [P] [US1] Write `deploy/nginx/navaan.conf`: port 80 ACME webroot plus redirect, port 443 vhost for `navaan.njlabs.dev` only, `auth_basic` with `/run/navaan/htpasswd`, per-IP rate limit (30 req/min without session cookie), proxy headers `X-Real-IP` and `X-Forwarded-Proto`, long timeouts for uploads.
  - Note: two throttle zones (strict without a session-shaped cookie, loose for everyone) so a forged cookie cannot bypass the gate throttle. Tested in nginx:alpine: 401 without gate, 200 with, 429 after the burst.
- [X] T013 [P] [US1] Write `deploy/nginx/README.md`: exact edit to `/opt/engagehub/docker-compose.yml` (one bind mount, one network), backup command, `nginx -t` check, rollback.
  - Note: two mounts (vhost and htpasswd) plus one network, not one mount; nginx reads the hash from a file. Stage-1 `navaan-acme.conf` lets certbot issue the cert before the full vhost needs it.
- [X] T014 [US1] (VM) Back up `/opt/engagehub/docker-compose.yml`, apply the README edit, `docker compose up -d nginx`, `docker exec engagehub-nginx nginx -t`, confirm EngageHub and Relayent health URLs still answer.
  - Done 2026-10-13 23:5x UTC. Rehearsed `nginx -t` in a throwaway container with the same mounts and networks, backed up the compose file to `/opt/engagehub/docker-compose.yml.bak-2026-10-13`, `docker compose up -d --dry-run nginx` showed only nginx recreated, then recreated it. Neighbour snapshot after: identical (`/opt/navaan/before.txt` vs `after1.txt`, `after2.txt`). The navaan container (`up -d` from `/opt/navaan/repo`) runs healthy, pulled 9 files from Vault, wrote the gate hash.
- [X] T015 [US1] (VM) Issue the cert: `certbot certonly --webroot -w /var/www/certbot -d navaan.njlabs.dev --deploy-hook "docker exec engagehub-nginx nginx -s reload"`, then `certbot renew --cert-name navaan.njlabs.dev --dry-run`.
  - Done: cert for navaan.njlabs.dev issued with webroot and the deploy hook (valid to 2027-01-11); `certbot renew --dry-run` for it succeeded. Full vhost switched on after `nginx -t` passed (stage 1 file kept as `/opt/navaan/nginx/navaan.conf.stage1`). Edge checks without the gate password: 401 on `/` and `/api/songs`, 301 http to https, HSTS and frame headers present, 45 wrong-password requests gave 21 x 401 then 24 x 429.
- [X] T016 [US1] (Nj) Create the shared gate password and store it in Vault per `contracts/vault-layout.md`. Never paste it in chat.
- [ ] T017 [US1] (VM) Bring up the container, run quickstart steps 6 to 8: 401 without gate, 200 with gate, API 401 without session, cookie flags, first-time setup with the code from the container, sign in with TOTP, recovery code, passkey on the real domain, throttle test.

**Checkpoint**: MVP. Studio reachable and protected, no publishing yet.

## Phase 4: User Story 3, credentials in Vault (P2, placed early because US2 needs it)

**Goal**: platform tokens and the Claude token live in Vault, refreshed tokens persist.
**Independent test**: quickstart steps 3 and 9.

- [X] T018 [P] [US3] Write `deploy/vault/setup.md`: enable `navaan/` kv-v2 mount, policy `navaan`, AppRole `navaan` (token TTL 1 h, max 4 h), write role id and secret id to `/opt/navaan/secrets/` with mode 600. Commands only, no values.
- [X] T019 [P] [US3] Write `deploy/vault_sync.py` (urllib only): AppRole login, pull `navaan/data/*` to tmpfs with stored mode, watch files and push changed ones back, write status file, retry with backoff when Vault is sealed or unreachable.
- [X] T020 [US3] Write `deploy/entrypoint.sh`: wait for Vault, pull secrets, build htpasswd from the gate secret, start the watcher, export `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY`, start the portal.
  - Note: `claude.env` is not exported by the entrypoint; the portal reads it each time a Claude step starts (`navaan_common.load_claude_env`), so a late or renewed token needs no restart.
- [X] T021 [US3] Add secrets status to `plugins/navaan-studio/scripts/navaan_ui.py`: read `NAVAAN_SECRETS_STATUS`, expose on `/auth/state` and the status area so the sign-in page shows "secrets waiting" when sealed.
- [X] T022 [US3] Add a Claude credential indicator in `plugins/navaan-studio/scripts/ui.html` and `settings_api.py`: show token type in use, and missing, expired or rate limited states (FR-012, FR-018).
- [X] T023 [US3] (Nj) Run the Vault setup from `deploy/vault/setup.md` with own admin login. Have 2 unseal keys ready.
  - Done 2026-10-13: mount `navaan/` (kv-v2), policy `navaan`, AppRole `navaan` created with the stored admin login; role id and secret id in `/opt/navaan/secrets/` (uid 10001, mode 400, never printed). Checked by an AppRole login and `vault_sync.py pull` from the `navaan:local` image on `engagehub-network`: `secrets: ok (0 files)`. The admin token file was removed from the Vault container afterwards.
- [X] T024 [US3] (Nj) Push secrets from the Mac using `vault_sync.py push`. Confirm no credential files in the data volume.
  - Done 2026-10-13/14: 7 platform files pushed from the Mac; `claude.env` (one `CLAUDE_CODE_OAUTH_TOKEN` line, generated on the server) pushed from the VM as the navaan AppRole with a one-off container (`vault_sync.py pull` pushes a local known file Vault lacks). A clean container then pulled all 8 files, mode 600. `gate.htpasswd` is in Vault too (user `gate`). The server copy `/home/ods/.config/navaan/claude.env` is outside Vault and can be deleted.
- [ ] T025 [US3] (VM) Sealed-Vault drill (quickstart step 9): seal, restart container, page shows waiting, unseal, status `ok` within 1 minute.

## Phase 5: User Story 2, scheduled posts with the Mac off (P1)

**Goal**: server publishes on schedule exactly once.
**Independent test**: quickstart step 11.

- [X] T026 [US2] Add `NAVAAN_SCHEDULER` (`on` default, `off` stops the scheduler thread) in `plugins/navaan-studio/scripts/navaan_ui.py` and `navaan.py`; show scheduler state in the UI.
- [X] T027 [US2] Verify and, if needed, harden publish-once: check how a fired item is recorded so a second instance skips it. Add a test in `plugins/navaan-studio/tests/test_scheduler_once.py`.
- [X] T028 [US2] Document the cutover order in `deploy/README.md`: turn Mac scheduler off, then server on, never both.
- [ ] T029 [US2] (VM) Quickstart step 11: Mac scheduler off, schedule a test item minutes ahead, approve gates, sleep the Mac, confirm one publish and a history line. Check missed-approval case shows "waiting for approval".

## Phase 6: User Story 4, run the pipeline on the server (P2)

**Goal**: Claude steps and render work on the server, Mac-only steps are clearly marked.
**Independent test**: run a short song with own pictures from lyrics through render.

- [X] T030 [P] [US4] Add `NAVAAN_HEADLESS` handling in `plugins/navaan-studio/scripts/navaan.py`: Chrome-driven steps (Suno import, Flow visuals) print a Mac-only hint and the upload instructions instead of launching Chrome.
- [X] T031 [P] [US4] In `plugins/navaan-studio/scripts/settings_api.py` and `ui.html`, hide local-browser sign-in buttons when headless and show the Mac command instead.
- [X] T032 [US4] Show a "Do this on the Mac, then upload the result" card on the song page for Mac-only steps in `ui.html`, reusing the existing upload path.
- [ ] T033 [US4] (VM) Run a synthetic song end to end: Claude lyrics and caption step with the subscription token, render, check output. Confirm Mac-only steps show guidance.
- [ ] T034 [US4] (Nj) Check Anthropic terms for always-on subscription use (FR-018) and decide subscription vs API key. Documented switch lives in `deploy/README.md`.

## Phase 7: User Story 5, move existing work (P3)

**Goal**: all songs, approvals, schedules, config and analytics history on the server, Mac still works.
**Independent test**: quickstart steps 10 and 12.

- [X] T035 [P] [US5] Write `deploy/backup/backup.sh`: nightly tar of the data volume to the OCI bucket, retention 14 days, restore instructions in `deploy/README.md`.
- [X] T036 [P] [US5] Write `deploy/migrate.md` (or a section in `deploy/README.md`): rsync commands for `songs/`, `analytics.db`, `navaan.config.json` with a dry run first. Config contains credentials references, so route credentials through Vault, not rsync.
- [X] T037 [US5] (VM) Run the migration, compare `ls songs | wc -l` and `sqlite3 analytics.db 'select count(*) from media'` with the Mac, open and play a migrated song.
  - Done 2026-10-14: 8 song folders and 290 files (1.68 GB) copied with `rsync -a --rsync-path="sudo rsync"` (the data folder is owned by uid 10001, and the Mac's openrsync has no `--info`), `analytics.db` via `sqlite3 .backup`, config copied. Counts match the Mac: 8 dirs, 290 files, 6 media rows. Container restarted healthy, scheduler still off. Still to do by hand: open and play one migrated song in the studio.
- [ ] T038 [US5] (VM) Install the backup cron or timer, run once, restore to a scratch dir, compare file counts.
- [ ] T039 [US5] Refresh platform tokens: YouTube token before about Oct 19, Instagram renewal around Dec 12. Confirm refreshed values land in Vault.

## Phase 8: User Story 6, share the VM safely (P3)

**Goal**: other apps untouched, NAVAAN removable.
**Independent test**: before/after health and cert checks, rollback drill.

- [X] T040 [P] [US6] Add a before/after snapshot script `deploy/check-neighbours.sh`: health URLs and cert fingerprints for EngageHub and Relayent.
- [ ] T041 [US6] (VM) Run snapshot before T014 and after T017; diff must be empty.
- [ ] T042 [US6] (VM) Rollback drill (quickstart step 13): remove mount and network, `docker compose up -d nginx`, neighbours answer, Mac studio works.
- [ ] T043 [US6] (Nj) Check the `relayent.ignorelist.com` cert (expires 2026-10-14 21:04 UTC, renewal looked broken). Not ours, flagged only.
  - Update 2026-10-13: the cert was renewed in the meantime (now valid to 2027-01-11, snapshot in `/opt/navaan/before.txt`). The renewal config may still say `standalone`; check with `sudo grep authenticator /etc/letsencrypt/renewal/relayent.ignorelist.com.conf`.

## Phase 9: Polish

- [X] T044 [P] Update `plugins/navaan-studio/docs/DEPLOY_HANDOFF.md` and `docs/AUTH.md` to match what was built.
- [X] T045 [P] Finish `deploy/README.md` (install, update, rollback, env table, VM reboot note: Vault seals, 2 unseal keys needed).
- [ ] T046 Run all quickstart steps 1 to 13 top to bottom and record results in `specs/001-run-navaan-on-server/quickstart.md`.
- [ ] T047 Run `/speckit-analyze` for a consistency pass across spec, plan and tasks.

## Dependencies

- Phase 1 before all. Phase 2 blocks all stories.
- US1 (Phase 3) first: MVP. US3 (Phase 4) next because US2 and US4 need secrets. US2 after US3. US4 after US3. US5 after US1 and US3. US6 spans US1; its snapshot (T041) wraps T014 and T017.
- Within a story: scripts and docs [P] first, then app edits, then VM verification.
- `navaan_ui.py` edits (T005, T006, T021, T026) touch one file: do them in order, not in parallel.

## Parallel examples

- Phase 1: T002, T003, T004.
- US1: T012 and T013 together.
- US3: T018 and T019 together.
- US4: T030 and T031 together.
- US5: T035 and T036 together.

## Implementation strategy

1. **MVP**: Phases 1, 2, 3. Reachable, gated, signed in. No credentials on the server yet, so nothing can publish.
2. Add US3 (Vault), then US2 (scheduler): this is the point where the server is worth having.
3. US4, US5, US6, then polish.
4. Stop after each checkpoint and let Nj verify on the VM before going on.
