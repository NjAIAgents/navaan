# NAVAAN Studio server deploy (Oracle VM, https://navaan.njlabs.dev)

One container (`navaan`) runs the portal and the scheduler, behind the VM's existing `engagehub-nginx`. Credentials live in Vault and are pulled into memory-only storage; songs and the analytics database live on a persistent folder with a nightly backup. Design: `specs/001-run-navaan-on-server/`.

## Files
| Path | What |
|------|------|
| `Dockerfile`, `compose.yml`, `entrypoint.sh` | the container (arm64, Python 3.13, Node 22, ffmpeg, headless Chrome, `claude` CLI, the plugin) |
| `vault_sync.py`, `vault/setup.md` | secrets in Vault: server side `watch`, Mac side `push` and `set-gate` |
| `nginx/` | vhost, certificate steps, the edit to the shared nginx, rollback |
| `backup/backup.sh` | nightly backup to the OCI bucket |
| `migrate.md` | copy your existing songs, database and config to the server |
| `check-neighbours.sh` | before/after snapshot of the other apps |

## Environment (what the container sets; contract in `specs/001-run-navaan-on-server/contracts/environment.md`)
| Variable | Server value | Meaning |
|----------|--------------|---------|
| `NAVAAN_PUBLIC_HOST` | `navaan.njlabs.dev` | extra allowed Host |
| `NAVAAN_TRUST_PROXY` | `1` | take client IP and scheme from nginx (the port is only on `navaan-network`) |
| `NAVAAN_BIND` | `0.0.0.0` | inside the container only |
| `NAVAAN_HEADLESS` | `1` | Chrome-driven steps and local-browser sign-ins are Mac only |
| `NAVAAN_SCHEDULER` | `on` (cutover done 2026-10-14) | which machine publishes on schedule; the Mac must run with `off` |
| `NAVAAN_VAULT_*` | see `compose.yml` | Vault address and the AppRole files |

## Branches and the release pipeline
`feat/*` branches merge into **`develop`** (integration); **`main`** is production. A pull request from `develop` into `main`, once merged, releases to https://navaan.njlabs.dev. Nothing else touches production.

| Trigger | Workflow | What runs |
|---------|----------|-----------|
| pull request into `develop` (not a draft, not docs-only) | `.github/workflows/ci.yml` | the FAST checks, about 4 minutes: unit tests (`plugins/navaan-studio/tests`), the web tests and build, `bash -n` on the deploy scripts, `docker compose config`. A newer push cancels the older run. |
| push to `main` (a merge), or run by hand | `.github/workflows/deploy-prod.yml` | the same tests plus the BROWSER checks (Playwright, Lighthouse, about 12 more minutes), then the release: the runner sends `git archive` of the repo over SSH, the VM builds the image, rolls it out, waits for healthy, smoke tests `/auth/state` through nginx and **rolls back to the previous image if either fails**; finally the runner checks `/auth/state` and `/privacy` from outside |

Releases never overlap (`concurrency: prod-deploy`) and a running release is never cancelled. The last deployed commit is in `/opt/navaan/DEPLOYED` on the VM; the release log is `/var/log/navaan-deploy.log`.

**How the VM side is locked down.** The pipeline's SSH key belongs to the user `navaan-deploy` (no password, no shell). Its `authorized_keys` line is `restrict,command="/opt/navaan/bin/deploy-entry" ssh-ed25519 ...`, so the key can only run `ping` or `deploy <40 hex sha>`; anything else is refused, and port forwarding and a terminal are off. `deploy-entry` runs `sudo /opt/navaan/bin/deploy-run <sha>` (one sudoers line: `navaan-deploy ALL=(root) NOPASSWD: /opt/navaan/bin/deploy-run *`). Both scripts are **owned by root and are not updated by the pipeline**: the pipeline can change what is built, never the release script. After editing `deploy/deploy-run.sh` or `deploy/deploy-entry.sh`, an admin reinstalls them:
```sh
sudo install -m 755 -o root -g root deploy/deploy-run.sh   /opt/navaan/bin/deploy-run
sudo install -m 755 -o root -g root deploy/deploy-entry.sh /opt/navaan/bin/deploy-entry
```

**GitHub settings** (repo `NjAIAgents/navaan`): secret `DEPLOY_SSH_KEY` (the private key); variables `DEPLOY_HOST`, `DEPLOY_USER` (`navaan-deploy`) and `DEPLOY_KNOWN_HOSTS` (the VM's ed25519 host key, checked against `ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`; the runner refuses any other host).

**Rotate the key:** `ssh-keygen -t ed25519 -N "" -f key`, put the public half into `/home/navaan-deploy/.ssh/authorized_keys` behind the same `restrict,command=...` prefix, `gh secret set DEPLOY_SSH_KEY < key`, delete `key` locally.

**Free plan minutes:** a full run is about 16 minutes, so only the deploy gate (and a manual `gh workflow run ci.yml --ref <branch>`) runs the browser checks; a pull request runs the fast ones, a draft pull request runs nothing (mark stacked or unfinished branches as drafts), and there is no run on a push to `develop` or on the release pull request into `main`. Before opening a pull request run `npm test` (it includes the colour check) in `plugins/navaan-studio/web` and the unit tests locally.

**Known limit:** branch protection and rulesets need GitHub Pro for a private repo, so `main` is protected by convention (merge through a pull request) rather than by a rule. The deploy workflow still runs the tests before it releases anything.

**Manual release or rollback** (same path the pipeline uses, from a machine that has the key):
```sh
git archive HEAD .claude-plugin plugins deploy .dockerignore | ssh -i key navaan-deploy@163.192.110.178 "deploy $(git rev-parse HEAD)"
```
To go back to the previous image by hand on the VM: `docker tag navaan:previous navaan:local && cd /opt/navaan/repo && docker compose -f deploy/compose.yml up -d`.

## Install (first time)
1. **Vault**: `vault/setup.md` (mount, policy, AppRole, secret files), then push the secrets from the Mac.
2. **Data folder**: `sudo install -d -o 10001 /opt/navaan/data/songs /opt/navaan/data/state`, then `migrate.md`.
3. **Network and container**: `cd /opt/navaan/repo && docker compose -f deploy/compose.yml up -d --build`. The container joins `engagehub-network` (where `engagehub-vault` lives); override with `VAULT_NETWORK` if that ever changes.
4. **nginx and certificate**: `nginx/README.md`.
5. **First sign in**: `docker exec navaan cat /home/navaan/.config/navaan/auth_setup_code`, open the site, enter the shared password, then create the login. Save the recovery codes. The login is written to Vault within 30 seconds.

## Caption tools
The image already contains the caption timing tools (onnxruntime, librosa, scipy, the vocal separation model and Whisper small, about 700 MB, installed at build time into `~/.cache/navaan`). The `captions_setup` approval gate therefore does not appear on the server. The first build downloads them from GitHub and PyPI; later builds reuse the Docker layer until `setup_captions.py` changes.

## Update
```sh
cd /opt/navaan/repo && git pull
docker compose -f deploy/compose.yml up -d --build
```
Data, secrets and the Vault login survive (they are outside the image). Sessions end (they live in memory).

## Scheduler ownership
Only one portal may run the scheduler. Cutover order, exactly:
1. On the Mac: start the portal with `NAVAAN_SCHEDULER=off` (or stop it).
2. On the server: set `NAVAAN_SCHEDULER=on` (`NAVAAN_SCHEDULER=on docker compose -f deploy/compose.yml up -d`).
Never both. The header chip in the studio shows `scheduler on|off|paused`. `paused` means Vault is sealed or unreachable: nothing publishes until it is back, because the tokens are not there.

## Expiring logins: renew them in the portal
When a login stops working the portal opens a popup ("Logins that need you", also a header button, and **Settings**) that shows the command to run, a Copy button and a box to paste the result. Nothing is stored until the pasted value has been checked, so a wrong paste never replaces a working login. On the server the saved file goes to Vault within 30 seconds. No restart is needed.

| Login | Command (run where) | Paste | Check before saving |
|-------|---------------------|-------|---------------------|
| Claude (`claude.env`) | `claude setup-token`, on any computer where Claude Code is signed in | the token (`sk-ant-oat...`), or an API key (`sk-ant-api...`, which wins if both exist) | one tiny `claude -p` call with it |
| YouTube publishing and analytics | **Sign in with Google** in the popup: it opens Google in your own browser, you allow access, Google sends you to a `localhost` page that cannot open, and you paste that address back (the server needs no browser). Or, on a Mac terminal: `publish_youtube.py auth` / `yt_collect.py auth --account music`, then `cat ~/.config/navaan/<file> \| pbcopy` | the address, or the whole file | the code is exchanged here, then Google refreshes the token and returns the channel name |
| Instagram | nothing to run: **Refresh now** extends a login token by 60 days (shown 10 days before it ends) | | Instagram answers `/me` |

The inspiration account uses `NAVAAN_YT_TOKEN=~/.config/navaan/youtube_token_inspiration.json` in front of the YouTube command; the popup writes it out for you.

**Google ends sign ins every 7 days while the OAuth consent screen is in Testing.** To stop that, set the app to **In production** (Google Cloud console, APIs and Services, OAuth consent screen, Publish app). For one user's own account no review is needed; Google only shows an "unverified app" screen at sign in. Then the YouTube popup should rarely appear.

Whether always-on use of a Claude subscription token fits Anthropic's terms is yours to check (T034). An API key in the same box is the fallback; no other change is needed.

## The settings disk is 16 MB: keep files out of it (NAV-54)

`/home/navaan/.config/navaan` in the `navaan` container is a 16 MB memory disk (tmpfs) that holds the logins, tokens and settings delivered from Vault. Nothing in the app writes media there; keep it that way:

- One-off jobs (an image test, a download, a conversion) write to `/tmp` (about 2 GB) and stream the result out with `docker exec ... cat`. `docker cp` cannot read a tmpfs, so a file left there is also hard to get back.
- When the disk passes 80% Studio shows "The settings disk is N% full". Find the culprit with `docker exec navaan du -ah /home/navaan/.config/navaan | sort -h | tail` and move it to `/tmp`. A full disk makes the next token refresh fail.

## Mac-only steps
Suno import of a public song no longer needs a browser: the server reads the public clip data and downloads the audio itself (`suno_import.py auto <slug>`). It falls back to the Chrome step, which cannot run on the server, only for a private song or when `suno.auto_failed` is set in meta.json. The music Short and Instagram Reel no longer need Studio for songs that use your own pictures: the video step also renders `final_reel_9x16.mp4` (45 s from the first chorus, `shots_render.py <slug> --reel`; write `reel_start.json` {"start": seconds} to move it), the Short is uploaded with the API, and Instagram uses the same file. The full YouTube video has no burned in captions. Steps that drive Chrome (Suno generate, Flow visuals and the Studio Short for Flow songs, the Suno import fallback) cannot run on the server. The studio shows "Do this on the Mac, then upload the result". Copy the song folder to the Mac, run the step there, copy the new files back:
```sh
rsync -av ods@njPRD:/opt/navaan/data/songs/<slug>/ songs/<slug>/     # fetch
# ... run the step on the Mac ...
rsync -av songs/<slug>/ ods@njPRD:/opt/navaan/data/songs/<slug>/     # return; then press Run on the server
```
Google sign in is also Mac only: run `publish_youtube.py auth` on the Mac, then `python3 deploy/vault_sync.py push`.

## Cleaned songs: files come back from the bucket on demand
After a song is archived and cleaned locally, its pictures and audio are only in the bucket. The portal fetches a missing picture or audio file for a song that has a recorded cloud copy the first time something asks for it (covers in the library, `/media/...`), and the YouTube upload and thumbnail steps fetch the file they need. Each fetch is one `oci os object get` of that single file (about 2 s), the key comes from the song's own `cloud.prefix`, paths outside a song folder are refused, and a file that is not in the bucket is remembered for an hour so it is not asked for again. Videos are not fetched by the picture route (too big for a page load); the upload step still fetches the one video it needs. Fetched files stay on the server's disk until the next local cleanup.

## Logs

One structured log stream (JSON lines, one object per event) for the portal, the scheduler and every pipeline run (NAV-12; spec `specs/002-platform-foundation`, FR-034 and FR-035).

| Where | What | Kept |
|-------|------|------|
| `docker logs navaan` (stdout) | every event; Docker rotates it at 50 MB x 5 | until rotated |
| `/opt/navaan/data/state/logs/app.jsonl` | the same stream, rotated at midnight UTC | 14 days |
| `/opt/navaan/data/state/logs/runs/<job_id>.jsonl` | one whole pipeline run in order (every step, every output line) | 30 days |
| `songs/<slug>/logs/<step>.log` | the raw output of each step, as before | with the song |

Each record has `ts` (UTC), `level`, `service`, `component`, `event`, and the ids that apply: `request_id`, `job_id`, `item`, `step`, `user`, plus `error.type`, `error.message` and `error.stack` for errors. An error page names its request: look it up with
```sh
docker logs navaan 2>&1 | grep <request id>          # or: grep <id> /opt/navaan/data/state/logs/app.jsonl
```
Secrets, tokens, passwords, email addresses and query strings are masked before anything is written. The browser reports its own errors to `/api/client-log`, so a page that fails shows up here too. The same error is written at most once a minute; the next record says how many were held back (`suppressed`). `NAVAAN_LOG_LEVEL=DEBUG` adds the routine polls and every deliberately ignored error. The logs are not part of the nightly backup (they are not state).

**Loki later, no code change:** run Grafana Alloy or Promtail on the VM, tail the container's stdout (or `app.jsonl`), parse the JSON, and use only `service`, `env`, `level` and `component` as labels. Keep `request_id`, `job_id`, `item` and `step` in the record body, not as labels, so the index stays small.

## Backup and restore
`deploy/backup/backup.sh` runs nightly at 03:17 UTC as root (`/etc/cron.d/navaan-backup`, log `/var/log/navaan-backup.log`). It always keeps a local copy (newest 7 in `/opt/navaan/backups`, mode 700) and uploads to the OCI bucket `navaan` (prefix `navaan-backup/`, 14 days kept) through the VM's instance principal, using the `ghcr.io/oracle/oci-cli` container because the VM has no `oci` CLI. Exit code 3 means the local copy exists but the upload failed.

**OCI access (done 2026-10-14)**: the VM is covered by the existing dynamic group `ods-vm-instances` (all instances in the ODS sandbox compartment). The policy `navaan-vm-bucket-policy` in the root compartment (the bucket lives there) adds two statements, so the `ods-pg-backup-policy` and the others stay untouched:
```
Allow dynamic-group ods-vm-instances to manage objects in tenancy where target.bucket.name = 'navaan'
Allow dynamic-group ods-vm-instances to read buckets in tenancy where target.bucket.name = 'navaan'
```
First upload worked the same day (`navaan-backup/navaan-data-20261014T013724Z.tar.gz`, 1.67 GB). It does not allow bucket-level actions such as pre-authenticated links (the Cloud storage tab's "open a link" button), by design: that would need `manage buckets`.

The portal's Cloud storage tab runs `oci` inside the container with `OCI_CLI_AUTH=instance_principal` (the image contains `oci-cli`), so no API key lives on the server.

Restore (verified 2026-10-14: 291 files and the database, integrity ok, matched the live data):
```sh
sudo tar -C /tmp -xzf /opt/navaan/backups/navaan-data-<stamp>.tar.gz     # or fetch the archive from the bucket first
find /tmp/navaan-data/songs -type f | wc -l ; find /opt/navaan/data/songs -type f | wc -l
```
To restore for real: stop the container (`docker compose -f deploy/compose.yml down`), replace `/opt/navaan/data` with `navaan-data/`, `sudo chown -R 10001:10001 /opt/navaan/data`, start it.

## After a VM reboot, and the Vault drill
Vault comes back sealed (unseal with the existing script or your keys). Until then NAVAAN behaves like this (drilled 2026-10-14, see below):
- the site answers **502 for up to 60 seconds** after the container starts (the entrypoint waits that long for Vault so your login arrives before the portal starts);
- then the sign-in page shows **"Secrets waiting"**, creating a new login is refused (503), and the scheduler is `paused`;
- within about **16 seconds of Vault being reachable** the status is `ok`, your login (and passkey) are restored from Vault, and the scheduler resumes.

**Repeatable drill that does not touch Vault** (EngageHub shares it, so never seal it for a test): cut only NAVAAN's path to it, restart, look, restore.
```sh
docker network disconnect engagehub-network navaan && docker restart navaan
curl -s https://navaan.njlabs.dev/auth/state            # {"state": "setup", "secrets": {"status": "waiting"}} after the 60 s wait
docker network connect engagehub-network navaan         # recovers in about 16 s
```

## Rollback
Remove the two navaan mounts and the `navaan-network` network from the `engagehub-nginx` service, `cd /opt/engagehub && docker compose up -d nginx`, delete `/opt/navaan/nginx/navaan.conf`. DNS and the certificate can stay. `docker compose -f deploy/compose.yml down` stops NAVAAN. The Mac portal keeps working; set its `NAVAAN_SCHEDULER` back to `on` only after the server's is `off`.

## Postgres (NAV-3, spec 002)

Analytics lives in a Postgres container dedicated to this project, part of `compose.yml` like the app: `pg-init` (makes the two passwords once, each in its own volume; the app mounts only its own),
`postgres` (17, 512 MB cap, data in `/opt/navaan/data/pg`) and the app, which waits for it to be healthy. The database is on the internal `navaan-db` network only: no published
port, and nginx cannot reach it. Two roles: `postgres` (superuser, maintenance and the nightly dump) and **`navaan_app`**, which the app uses. It owns database `navaan`, cannot
create roles or databases, and is created by `deploy/postgres/init.sh` on the first start. There is nothing to prepare on the VM; check `free -m` first because the container adds up to 512 MB.

**Cutover from SQLite is automatic.** On the first start after the release, `navaan.py serve` copies the old `analytics.db` into Postgres in one transaction, checks every table's
row count and content checksum, and commits only if all match (log events `cutover_started`, `cutover_done`). If anything differs, nothing is written, the start fails, the container
never becomes healthy and the release pipeline rolls the image back; the SQLite file is never changed, so the old release runs on as before. After a good copy the SQLite file stays as
the rollback copy: delete it by hand after about 14 days. Rolling back after a good cutover returns to that file, so analytics collected since are only in Postgres.

**Where the app connects.** The compose file sets `NAVAAN_PG_HOST`, `NAVAAN_PG_USER` and `NAVAAN_PG_PASSWORD_FILE`. The same settings can live in `navaan.config.json`
(`NAVAAN_PG_*` environment variables win; `NAVAAN_DATABASE_URL` wins over both). The config holds the path of the password file, never the password:
```json
"database": {"host": "navaan-postgres", "port": 5432, "name": "navaan", "user": "navaan_app", "password_file": "/pgsecret/pg_app_password"}
```

**Development and tests.** `docker compose -f deploy/compose.dev.yml up -d` starts a Postgres on 127.0.0.1:5432 (role `navaan_app`, no password, database `navaan`), which is
what `analytics_db` uses with nothing configured. If another Postgres already holds 5432 (check `lsof -nP -iTCP:5432 -sTCP:LISTEN`), start it with `NAVAAN_PG_PORT=5440 docker compose -f deploy/compose.dev.yml up -d` and put `"database": {"port": 5440}` in `navaan.config.json` (or export `NAVAAN_PG_PORT`). Run the tests with `python -m unittest discover -s plugins/navaan-studio/tests`; each test gets its own throwaway schema.

**Check by hand** (prove an old file and Postgres agree, or redo a copy): `python3 plugins/navaan-studio/scripts/analytics_to_postgres.py --sqlite <file> [--replace] [--dry-run]`
prints rows and a checksum per table and exits 0 only when every table matches.

**Backup and restore.** The nightly `backup.sh` puts a `pg_dump -Fc` in the archive (the live `pg` folder is left out of the tarball). Restore drill, run once before relying on it
(a 115 KB analytics dump restored in 1 s on 2026-10-15):
```sh
tar -xzf navaan-data-<stamp>.tar.gz navaan-data/state/navaan.pgdump
docker exec navaan-postgres psql -U postgres -c 'CREATE DATABASE drill OWNER navaan_app'
docker exec -i navaan-postgres pg_restore -U postgres -d drill --no-owner --role=navaan_app < navaan-data/state/navaan.pgdump
docker exec navaan-postgres psql -U postgres -d drill -At -c 'select count(*) from analytics.yt_daily'
```
Migrations are numbered SQL in `plugins/navaan-studio/db/migrations/<schema>/`, applied once each when the app connects, recorded in `core.schema_migrations`. A release's migration must
work with the previous release too, because the pipeline rolls back the image but not the schema.

### Studio state (NAV-4)

What each song's `meta.json` held (state, approvals, history, published links, schedule, cloud and cleanup records) now lives in Postgres, schema `studio`, table `items` (the whole document, lossless) plus
projections (`approvals`, `item_history`, `publications`, `schedules`) that are rewritten in the same transaction on every save. **Source of truth: `studio.items.doc`.** The song folders keep their media and
step files; `meta.json` is still written after every save as a write-through export (temp file and rename, before the commit; if the write fails the save fails), so the bucket upload, the previous
release and anything that reads the file keep working.

**First start after the release:** `navaan.py serve` imports every `songs/*/meta.json` that Postgres does not have yet, reads each back and compares (`studio_import_done` in the log). If any file is unreadable or
differs after import, the start fails, the container never becomes healthy and the pipeline rolls the image back; the files are never changed by the import.

**Edits made outside the app** (a Claude step that follows a skill saying "record it in meta.json", a person, or the previous release after a rollback) are detected: when the file on disk is not the one we last wrote,
its content is taken in as the newer state (`meta_json_edited_outside`). A file that is not valid JSON is ignored and logged (`meta_json_invalid`), and the stored state is kept.

**Concurrency:** writes that read first (approve, answer, step results, the scheduler's claim) use `studio_store.update`, which locks the item's row, so the web page, the scheduler and a running step cannot overwrite
each other. The scheduler counts an attempt under that lock before it fires a step, so two schedulers never run the same step. Tested with 40 pairs of simultaneous ticks.

**Rollback:** the previous image reads the exported `meta.json` files, which are current. Anything it changes is taken back in by the next release through the outside-edit check.

### Accounts, sessions and roles (NAV-5 stage 1)

Schema `core` (migration `core/0001`): `users`, `roles` (owner, editor, listener), `role_permissions`, `user_roles`, `sessions`, `audit_log`, `login_attempts`, and `credentials`, `identities`, `user_profiles` (created for the listener stories, unused so far).

- **Your login** is unchanged: password, authenticator code, passkeys and recovery codes stay in `auth.json`, delivered by Vault into tmpfs, so they are never in a database dump. A `users` row for you (role owner) is created at your first sign-in so sessions, roles and the audit trail work the same for everyone.
- **Sessions** are rows in `core.sessions`, keyed by the SHA-256 of the cookie value, ending after 7 days or 7 idle days, or when revoked; a password change ends your other sessions. The older `sessions.json` is read once, moved to `sessions.json.imported`, and its live sessions carry over.
- **CSRF**: every session has its own token, filled into `index.html` and the classic page when they are served; a POST needs the token of the session it comes with.
- **Permissions**: a route asks for a permission (`studio.access`, `studio.approve`, ...), never a role name. Every studio route needs `studio.access`, which only owner and editor have; `GET /api/me` answers for any signed-in account.
- **Lockout**: 5 failed sign-ins from one address lock that address, growing to 15 minutes; kept in `core.login_attempts`, so a restart does not reset it.
- **Audit**: `core.audit_log` (`login`, `login_failed`, `logout`, `owner_setup`, `password_changed`, `passkey_added`, `passkey_removed`, `recovery_codes_renewed`, `user_created`); sign-in attempts older than 30 days and audit rows older than 400 days are pruned.
- **Database down**: `/auth/state` (the health check) still answers; signing in and every studio call fail closed.
- **Rollback**: the previous image reads `auth.json` and keeps its own sessions: you sign in again once, nothing else is lost.

### Jobs and the worker (NAV-4 stage 2)

The web server no longer runs steps or the publishing schedule. A click on Run, an approval that starts the next step, an answer, Redo or Restart **queues a job** in Postgres (`studio.jobs`); the
`worker` service (same image, `navaan.py worker`, container `navaan-worker`) claims it and runs it exactly as the web server used to, and publishes the progress the portal shows
(the old RUN and STATUS texts, through the job row). The schedule runs in the worker too, each step recorded as a job.

- **One active job per item.** A second trigger while one is queued or running is refused (the old "a run is in progress").
- **Lease and retry.** A running job has a lease its worker extends every 5 s. If the worker stops (deploy, crash, host restart) the lease runs out, `reap()` puts the job back in the queue and the next
  worker runs it again; after 2 attempts it fails with "the worker stopped before the job finished". A clean stop gives the lease back at once. A step that fails by itself is a failed job, not a retry.
- **Stop** from the portal sets a flag the worker sees at its next heartbeat, then stops the step and everything it started.
- **If the worker is down** the portal still queues jobs and `/api/status` reports `"worker": "down"`; they run when it is back. `docker logs navaan-worker`, and per-run files in `state/logs/worker/runs/`.
- **Slots.** `NAVAAN_WORKER_SLOTS` (default 2) items run in parallel; ffmpeg and Remotion are heavy, so watch memory before raising it.
- **Development.** `navaan.py serve` runs a worker in its own threads unless `NAVAAN_WORKER=external`, so one process is still enough on a laptop.
- **Rollback.** The previous image has no worker: its web server runs steps itself. After a rollback stop the worker container (`docker stop navaan-worker`); queued jobs wait in the table.

### The new app (NAV-8)

A React + Vite + TypeScript app in `plugins/navaan-studio/web/`, served by the portal at **`/app/`**; the classic page stays at `/` and `/legacy` until the new app has every screen. It is built in a separate stage of
`deploy/Dockerfile` (only `dist` enters the image; nothing to run on the VM) and in CI (`npm ci`, `npm test`, `npm run build`). nginx needs no change: it already proxies every path.

- **Themes are data.** `src/styles/themes/<id>.css` is one block of variables (`[data-theme="midnight-cinema"]`, `[data-theme="ivory-gold"]`); components read variables only. `npm test` fails on a colour literal
  outside those files and on a theme whose text falls under 4.5:1 contrast. Add a theme: copy a file, change the values, add its id to `src/theme/themes.ts` and the inline script in `index.html` (a test keeps them equal).
- **The choice** (Midnight Cinema, Ivory & Gold, or match the device) is kept per device in `localStorage` and applied before first paint. The full Appearance page (tone slider, accent palette) is NAV-17.
- **Auth is the portal's.** The same session cookie and the per-process token (a `<meta name="navaan-token">` filled in when `index.html` is served) as the classic page. A signed-out visit to `/app/` shows the sign-in page.
- **Screens not built yet** link to the classic view for that area, so nothing is lost while they move over (stories NAV-13 to NAV-19).
- **Development.** `cd plugins/navaan-studio/web && npm install && npm run dev` proxies `/api` and `/auth` to a portal on 127.0.0.1:8765.

## Releasing

One version, set in `plugins/navaan-studio/.claude-plugin/plugin.json`, mirrored in `.claude-plugin/marketplace.json` and `plugins/navaan-studio/web/package.json`; `CHANGELOG.md` (Keep a Changelog, SemVer, 0.y.z until the public listener app) names the latest release. `test_version.py` fails when they drift. The signed-in portal reports it (`/auth/state`, `version`) and the account menu of the new app shows it.

1. **While you work**: add entries under `## [Unreleased]` in `CHANGELOG.md` when a change is one a person using or running the studio would notice (a feature, a fix, a change, a removal, a security fix). Refactors, tests and docs-only edits are not listed. `/changelog` writes the entries from the commits.
2. **To release**: `python3 deploy/bump-version.py X.Y.Z` (patch for fixes, minor for features while 0.y.z). It refuses an empty `[Unreleased]`, edits the four version files and turns `[Unreleased]` into `[X.Y.Z] - <date>`, then prints the commit and tag commands. It never runs git.
3. Commit that on a branch, merge to `develop`, release `develop` to `main` as usual (the deploy is the release), then tag the release merge commit: `git tag -a vX.Y.Z -m "NAVAAN Studio X.Y.Z" <sha>` and `git push origin vX.Y.Z`. The GitHub Release body can be the changelog section (`/release-notes`).

## The nginx vhost is applied by hand
The deploy workflow ships the app, not `deploy/nginx/navaan.conf`: the file nginx runs is `/opt/navaan/nginx/navaan.conf` on the VM (mounted into `engagehub-nginx`). After you change the repo file, apply it yourself or prod keeps the old one (NAV-143: the public site was throttled as if it were the studio login for days after the fix was in the repo).
```sh
scp deploy/nginx/navaan.conf ods@<vm>:/tmp/navaan.conf.new
ssh ods@<vm> 'cp -a /opt/navaan/nginx/navaan.conf /opt/navaan/nginx/navaan.conf.bak-$(date +%Y%m%d); cat /tmp/navaan.conf.new > /opt/navaan/nginx/navaan.conf; sudo docker exec engagehub-nginx nginx -t && sudo docker exec engagehub-nginx nginx -s reload'
```
Write it in place with `cat >` (not `cp` or `install`): the mount is a single file, and replacing the file by a new one leaves the container looking at the old one. If `nginx -t` fails, put the backup back the same way. Then run `deploy/check-neighbours.sh` and compare with the snapshot.
