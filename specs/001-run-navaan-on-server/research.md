# Research: Run NAVAAN on the Oracle VM

Each entry: Decision, Rationale, Alternatives considered.

## R1 Runtime packaging
- **Decision**: One Docker image built from the repo at a given commit, linux/arm64: `python:3.13-slim-bookworm` base, Node 22 copied from the official node image, ffmpeg and Chromium shared libraries from apt, `claude` CLI from npm, the plugin installed from the repo's local marketplace (`.claude-plugin/marketplace.json`) at build time. Data and config are mounted, never baked in.
- **Rationale**: Matches the VM's other apps (Docker), keeps Mac and server on the same commit, and the portal already shells out to `claude -p "Use the <skill> skill..."`, which needs the plugin installed for the skill names to resolve.
- **Alternatives**: bare systemd service with host Python (pollutes the shared host, needs apt on the host, harder rollback); building on the Mac with buildx (works, but slower and needs a registry).

## R2 Routing and TLS
- **Decision**: Reuse `engagehub-nginx`. Add one bind-mounted `navaan.conf` and the external network `navaan-network` to its compose service, same pattern Relayent uses. Issue a single-host certificate with certbot webroot (`/var/www/certbot`, already mounted). Use `resolver 127.0.0.11` with a variable `proxy_pass` so nginx still starts if the NAVAAN container is down.
- **Rationale**: Ports 80 and 443 are owned by that container. Webroot issuance needs no downtime. The variable upstream stops a stopped NAVAAN container from taking down the other apps' proxy (constitution X).
- **Alternatives**: second nginx or Caddy on other ports (browsers would need a port in the URL); wildcard certificate (needs a Vercel API token on the VM, out of scope); Tailscale only (rejected earlier by Nj in favour of a shared password).

## R3 Shared-password gate (FR-017)
- **Decision**: nginx `auth_basic` on the 443 vhost with an htpasswd file mounted into the nginx container. The bcrypt hash is generated on the VM and stored in Vault as the source of truth. A `limit_req` zone keyed on client IP applies only to requests without a `navaan_session` cookie (via a `map`), 30 per minute with burst 20.
- **Rationale**: Zero new components, the browser caches basic credentials for same-origin fetches, and the studio keeps its own cookie-based login behind it. The map keeps signed-in use unthrottled.
- **Alternatives**: auth service via `auth_request` (more moving parts); Cloudflare Access (domain is not on Cloudflare); fail2ban on nginx logs (extra host component).

## R4 Secrets (FR-009 to FR-011)
- **Decision**: Vault mount `navaan/` (kv-v2), policy limited to it, AppRole `navaan`. `deploy/vault_sync.py` logs in with the role id and the secret id (Docker secret), pulls every key under `navaan/data/` into files on a tmpfs mounted at `~/.config/navaan`, and polls every 30 s to push any file whose hash changed (refreshed Google tokens). It writes `secrets.status` (`ok`, `waiting`, `sealed`) which the portal reads.
- **Rationale**: The code already reads credential files from `~/.config/navaan`, so nothing else changes. tmpfs means no secret reaches disk. Status lets the sign-in page say what is wrong when Vault is sealed.
- **Alternatives**: rewrite every script to read Vault directly (large, risky); Vault Agent sidecar (another image, no write-back); Docker secrets only (no write-back for refreshed tokens).

## R5 Claude steps (FR-018)
- **Decision**: `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`, stored at `navaan/data/claude.env`, exported by the entrypoint. `ANTHROPIC_API_KEY` may be placed in the same file instead and wins if present. Chrome-driven steps are disabled with `NAVAAN_HEADLESS=1`.
- **Rationale**: Matches Nj's choice and keeps the switch to an API key to one secret edit. The portal's existing `NAVAAN_CLAUDE_CMD` and `NAVAAN_CLAUDE_FLAGS` overrides need no change.
- **Alternatives**: API key first (Nj chose the subscription). Terms of always-on subscription use are Nj's to check; the plan records the risk and the switch.

## R6 Scheduler ownership (FR-008)
- **Decision**: New env `NAVAAN_SCHEDULER` (`on` default, `off`). The cutover checklist sets it to `off` on the Mac before the server's schedules are enabled. The server copy of `meta.json` carries the schedule, so the Mac copy of any scheduled item is cleared at cutover.
- **Rationale**: Each studio instance only knows its own `meta.json`, so "at most once" has to come from having one owner of the schedule, not from a distributed lock.
- **Alternatives**: a lock object in Vault or the OCI bucket (more machinery than one user needs).

## R7 Data, database and backup (FR-014, FR-016, FR-019)
- **Decision**: One bind-mounted data directory `/opt/navaan/data` holding `songs/`, `state/analytics.db` and `navaan.config.json`. First load by `rsync` from the Mac. SQLite stays. Nightly `backup.sh` tars the directory (SQLite copied with `.backup`) to the existing OCI bucket using instance principals, 14 days retention.
- **Rationale**: Smallest change, matches Nj's database decision, and a restore is one `tar -x`.
- **Alternatives**: Postgres now (deferred by Nj); Vault for song data (wrong tool).

## R8 Rendering on ARM
- **Decision**: Remotion's headless Chrome for linux-arm64 with the apt libraries it lists; render concurrency 4. Prove with one real render in the first tasks before anything else depends on it.
- **Rationale**: This is the highest technical risk and cheap to test early.
- **Alternatives**: keep rendering on the Mac and sync results (loses SC-008 and the Mac-off scheduling story for new songs).

## R9 Operations
- **Decision**: `restart: unless-stopped`, json-file logs with size rotation, a healthcheck on `/auth/state`, certificate renewal through the existing snap timer with a deploy hook that runs `nginx -s reload` in `engagehub-nginx`.
- **Rationale**: Same operational model as the existing apps. The earlier Relayent expiry is a reminder that renewal must be tested with `certbot renew --dry-run` right after issuance.
- **Alternatives**: systemd units around compose (extra layer).

## R10 VM facts (T002, T003; read over ssh as `ods`, 2026-10-13)
- **Vault network**: `engagehub-vault` (172.18.0.2:8200, plain HTTP) is on `engagehub-network` only, a bridge shared with `engagehub-app`, `engagehub-addin`, `engagehub-postgres` and `engagehub-nginx`. **Decision**: the navaan container joins `engagehub-network` as an external network (`VAULT_NETWORK=engagehub-network`). Alternatives rejected: adding Vault to a second network means recreating the Vault container (it would come back sealed) and editing a neighbour's compose; publishing Vault's port on the host exposes it more widely. Cost: navaan can reach postgres and the app on that bridge (they need their own credentials), and they can reach navaan:8765 (behind the studio login). The AppRole policy stays limited to `navaan/`.
- **certbot**: snap, timer `snap.certbot.renew.timer` (twice daily). All renewal hook folders are empty and no renewal config has a `renew_hook`, so **nginx is not reloaded after a renewal today**. NAVAAN's cert gets `--deploy-hook "docker exec engagehub-nginx nginx -s reload"` (stored in its own renewal file); the neighbours still have no reload hook (not ours; a global script in `renewal-hooks/deploy/` would fix all, offered to Nj).
- **Neighbour cert problem (not ours; the cert itself has since been renewed to 2027-01-11, only the `standalone` setting may remain)**: `relayent.ignorelist.com` is configured `authenticator = standalone`, so renewal fails every run ("Could not bind TCP port 80", journal 11:37 and 15:12 UTC) and the cert expires **2026-10-14 21:04 UTC**. engagehub (to Nov 18) and relayent-demo (to Oct 17) use webroot. Fix for Nj: `sudo certbot certonly --webroot -w /var/www/certbot -d relayent.ignorelist.com --force-renewal --deploy-hook "docker exec engagehub-nginx nginx -s reload"` (rewrites its renewal file to webroot).
- **Compose**: Docker Compose v5.1.4. `/opt/engagehub/docker-compose.yml` service `nginx` (container `engagehub-nginx`, nginx:alpine) mounts vhosts as absolute host paths into `/etc/nginx/conf.d/<name>.conf:ro`, mounts all of `/etc/letsencrypt` and `/var/www/certbot` read only, and joins Relayent's network as `relayent-network: {external: true, name: relayent-network}`. NAVAAN copies exactly that style. `nginx.conf` includes `conf.d/*.conf` inside `http {}`; existing zones are `api` and `login`, so the `navaan_*` names do not collide. Server names in use: engagehub, relayent, relayent-demo `.ignorelist.com`.
- **Host**: Ubuntu aarch64, user `ods` (sudo, docker groups), 123 GB free, `/opt/navaan` does not exist yet, `navaan.njlabs.dev` resolves to 163.192.110.178.
