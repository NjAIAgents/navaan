# NAVAAN studio: deploy to the Oracle VM (handoff for Claude Code)

Updated 2026-10-13. Spec, plan and tasks are committed. All code and docs tasks are built (see `tasks.md`, 25 of 47 checked). What is left is the VM and Nj steps.

## Goal
Run the portal (`plugins/navaan-studio/scripts/navaan.py serve`) in Docker on Nj's Oracle VM at https://navaan.njlabs.dev. Credentials live in the existing HashiCorp Vault. Scheduled publishing then works with the Mac off.

## Read first, in this order
1. `.specify/memory/constitution.md` (v1.0.0, 11 principles). Every task must respect it.
2. `specs/001-run-navaan-on-server/spec.md` (6 user stories, FR-001 to FR-019, clarified).
3. `specs/001-run-navaan-on-server/plan.md` (structure, constitution check, deviations, open VM items).
4. `specs/001-run-navaan-on-server/tasks.md` (47 tasks, T001 to T047, commit 5c0995f).
5. `research.md`, `data-model.md`, `quickstart.md`, and `contracts/` (`http-edge.md`, `environment.md`, `vault-layout.md`) in the same folder.

Commits so far: 1cd9700 auth module, c013f68 per-IP and https auth, c5f5a1b Spec Kit and constitution, 77c611b spec, c382c76 plan, 5c0995f tasks.

## Rules that always apply
- No secrets in chat, the repo or the project. Never print tokens, setup codes, role ids or secret ids.
- Gates are human-only. Never approve one. The user does publishing and gate approvals.
- Never `git checkout` in this repo. Never restart the local portal while a pipeline job runs (check `/api/song/<slug>` for `job.running`).
- `navaan_ui.py` and `ui.html` hold another session's uncommitted analytics edits. Commit only your own hunks with `git add -p` (task T001).
- The sandbox cannot SSH to the VM. Tasks marked (VM) are commands Nj runs and pastes back. Tasks marked (Nj) need his decision or secret.
- No double dashes in replies. Terse style.
- Git on the Mac folder may leave stale `.git/*.lock` files. Rename them aside. Commit with `-c user.name=Navjyot -c user.email=navjyotnishant@gmail.com`.

## Decisions already made
- Scope is NAVAAN only. EngageHub and Relayent keep their ignorelist.com names and get no changes beyond one added mount and one added network on `engagehub-nginx`.
- Host `navaan.njlabs.dev`, one certificate for that host through certbot webroot `/var/www/certbot`. No wildcard, no Vercel API token on the VM. DNS A record already exists (163.192.110.178).
- Extra gate: shared password at nginx (`auth_basic`) in front of the portal login (FR-017). It throttles per IP instead of locking out. The password lives in Vault.
- Claude steps use a long-lived subscription token from Vault (FR-018), with a documented switch to an API key. Nj checks Anthropic terms for always-on use (T034).
- Database stays the current file based SQLite for now (FR-019). Postgres is a later feature.
- Portal login is built: scrypt password, TOTP, recovery codes, passkeys, 12 h session, 2 h idle. See `plugins/navaan-studio/docs/AUTH.md`.
- Server files go in a new top level `deploy/`. Plugin changes are small and env driven, defaults keep localhost behaviour.

## What is built (Mac side, tested locally)
- Portal env switches (`NAVAAN_PUBLIC_HOST`, `NAVAAN_TRUST_PROXY`, `NAVAAN_BIND`, `NAVAAN_SCHEDULER`, `NAVAAN_HEADLESS`), per-IP and https-aware auth, secrets status on `/auth/state` and the sign-in page, scheduler `on|off|paused`, Claude credential card, Mac-only step note. Tests: `plugins/navaan-studio/tests/` (`test_auth.py`, `test_scheduler_once.py`, `test_headless.py`).
- `deploy/`: Dockerfile and compose (built and run on arm64 Docker, 30 s Remotion render passed), `vault_sync.py` and `vault/setup.md` (run against a dev Vault: push, pull, write-back, seal and unseal), `entrypoint.sh`, `nginx/` (vhost tested in nginx:alpine: gate 401/200, throttle 429), `backup/backup.sh` (dry run), `migrate.md`, `check-neighbours.sh`, `README.md`.

## What is not done (needs the VM or Nj)
T014 to T017 (nginx edit, cert, gate password, first sign in), T023 to T025 (Vault setup, push, sealed drill on the real Vault), T029, T033, T034, T037 to T039, T041 to T043, T046, T047. Step by step: `deploy/README.md`.

Changes to the plan found while building: nginx gets two mounts (vhost and htpasswd) plus one network; the container needs a rw mount of the single htpasswd file; `claude.env` is read per Claude step, not exported at start; compose defaults `NAVAAN_SCHEDULER=off`.

Env contract is in `contracts/environment.md`. Vault layout is in `contracts/vault-layout.md`.

## VM facts (checked by Nj over ssh)
- Host `njPRD`, user `ods`, Ubuntu 22.04.5 aarch64, 4 cores, 23 GiB RAM, 193 GB disk. Docker and compose present. A reboot is pending.
- `engagehub-nginx` (nginx:alpine) owns 80 and 443. Compose file `/opt/engagehub/docker-compose.yml`. Each app has its own bind-mounted vhost and its own external network that nginx joins. Copy the style of `/opt/relayent/nginx/relayent.conf`.
- certbot is a snap, webroot `/var/www/certbot`, certs in `/etc/letsencrypt`, timer `snap.certbot.renew.timer`.
- Vault: container `engagehub-vault`, hashicorp/vault 1.17.6, file storage, Shamir 2 of 3, manual unseal. After a reboot it is sealed until two keys are entered. Nj must have two keys ready before rebooting.
- Not ours: cert `relayent.ignorelist.com` expires 2026-10-14 21:04 UTC and renewal looked broken. Nj was told to check.

## VM facts (T002, T003 done 2026-10-13, details in `specs/001-run-navaan-on-server/research.md` R10)
- Vault is only on `engagehub-network`; NAVAAN joins it (compose default). Compose is v5.1.4, nginx vhosts are mounted by absolute host path, certbot has no reload hooks (NAVAAN's cert gets one). T011 done: image builds on the VM and a 30 s render takes 148 s with 2 CPUs.
- Not ours: `relayent.ignorelist.com` was on `standalone` renewal; its cert has been renewed since (valid to 2027-01-11) but check the setting (T043).

## Other pending items for Nj
- YouTube token refresh before about Oct 19. Instagram token renewal around Dec 12.
- Create the Vault mount, policy and AppRole with his own admin login, then put role id and secret id in `/opt/navaan/secrets/`.
- Create the NAVAAN login through the setup code (local portal first, server later).

## Verify and roll back
Runnable checks are in `specs/001-run-navaan-on-server/quickstart.md` (13 steps). Rollback: remove the navaan mount and network from the nginx service, `docker compose up -d nginx`, delete the vhost file. DNS can stay. The Mac portal keeps working untouched, but only one portal may run the scheduler at a time.
