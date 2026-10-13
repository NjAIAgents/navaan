# NAVAAN studio: deploy to the Oracle VM (handoff)

Goal: run the portal (`plugins/navaan-studio/scripts/navaan.py serve`) on Nj's VM at https://navaan.njlabs.dev, in Docker, with credentials in the existing HashiCorp Vault, so scheduled publishing no longer needs the Mac awake. Postgres in a container is a possible later step.

Rules that still apply: no secrets in chat, the repo or the project; gates are human-only; never `git checkout` in this repo; do not commit another session's partial work; do not restart the local portal while a pipeline job runs. Reply style: terse, no double dashes.

## Already done
- DNS: A record `navaan.njlabs.dev` -> 163.192.110.178 (TTL 60) in Vercel DNS (team "Navjyot's Lab", record rec_dfacd7a6a0b451dc3b4b7da8). Other Vercel domains: navjyotnishant.com, the-whodunit.com. Wildcard `*` on njlabs.dev points at Vercel, the explicit A record overrides it for `navaan`.
- Portal login: `scripts/auth.py`, `qr.py`, `auth.html`, `docs/AUTH.md` (commit 1cd9700). Password (scrypt) + authenticator app / passkey / recovery codes, 12 h session, 2 h idle, store `~/.config/navaan/auth.json`, setup code `~/.config/navaan/auth_setup_code`.
- Hooks in `navaan_ui.py` and `ui.html` (auth gate, Security card in Settings) exist but are UNCOMMITTED, mixed with another session's analytics edits. Commit only your own hunks (`git add -p`).
- `auth.py` now has a per-IP lockout and https-aware cookies and passkey origin (`CTX.ip`, `CTX.https`; `state(...)` and `handle_post(...)` take `ip=` and `https=`). Tested with a scripted suite; not yet wired into `navaan_ui.py`.
- Analytics page tweaks in `ui.html` (confidence chips, sort by confidence, collapsed cards, scrollable list), also uncommitted.

## VM facts (checked by Nj over ssh; the Cowork sandbox cannot reach the VM, so Nj runs commands)
- Host: `njPRD`, user `ods`, Ubuntu 22.04.5 aarch64 (Oracle), 4 cores, 23 GiB RAM, 193 GB disk (37% used). Docker + compose present. Host has node v22, tailscale, no ffmpeg. "System restart required" is pending.
- `engagehub-nginx` (nginx:alpine) owns 80 and 443. Compose file: `/opt/engagehub/docker-compose.yml`. Each app has its own vhost file bind-mounted into `/etc/nginx/conf.d/` and its own external Docker network that nginx joins. Example to copy: `/opt/relayent/nginx/relayent.conf` (ACME location on :80, 301 to https, TLS block, security headers, `proxy_pass http://relayent-relay:8787`, X-Forwarded-Proto, long timeouts). Networks on nginx now: `engagehub-network`, `relayent-network`.
- TLS: certbot (snap), webroot `/var/www/certbot` mounted in nginx, certs in `/etc/letsencrypt`. Timer: `snap.certbot.renew.timer`.
- Vault: container `engagehub-vault`, hashicorp/vault 1.17.6, file storage, Shamir 3 shares threshold 2, currently unsealed. After any VM reboot it comes up sealed until two keys are entered.
- Not ours but urgent: cert `relayent.ignorelist.com` expires 2026-10-14 21:04 UTC and did not auto renew (issued with `--standalone`). Nj was told to run `sudo certbot renew --cert-name relayent.ignorelist.com --dry-run`.
- Do not modify EngageHub or Relayent config beyond the one added mount and network on nginx.

## Plan
1. Housekeeping. Commit the portal auth hooks and the analytics UI tweaks without the other session's hunks. Copy the tested `auth.py` (per-IP, https) into `scripts/`.
2. App changes in `navaan_ui.py` (env driven, defaults unchanged for localhost):
   - `NAVAAN_PUBLIC_HOST` added to the allowed Host values in `_host_ok`.
   - `NAVAAN_TRUST_PROXY=1`: https = `X-Forwarded-Proto == https`, client IP = `X-Real-IP`. Origin check becomes `https://host` when https. Pass `ip=` and `https=` to `auth.state` and `auth.handle_post`.
   - `NAVAAN_BIND` (default 127.0.0.1, `0.0.0.0` in the container). Only reachable on the internal Docker network.
   - `NAVAAN_HEADLESS=1`: hide Settings buttons that open a local browser (YouTube sign in) and show the Mac command instead.
3. Container (`/opt/navaan/`): Dockerfile for arm64 with python3, ffmpeg, node 22, Chromium for Remotion (npm install in `plugins/navaan-studio/remotion`), `cryptography`, the OCI CLI if used, and the `claude` CLI. Compose project `navaan` with its own network `navaan-network`, volumes for `songs/`, the analytics db and `navaan.config.json`, tmpfs for `~/.config/navaan`. Test a Remotion render on ARM early.
4. Vault. Mount `navaan/` (kv-v2), policy limited to `navaan/*`, AppRole `navaan`. Role id and secret id go to `/opt/navaan/secrets/` as Docker secrets, never printed. Entrypoint pulls the secrets into tmpfs files (instagram.env, instagram_inspiration.env, youtube_*.json, auth.json) so existing code is unchanged. A watcher pushes changed files back to Vault within a minute (Google tokens refresh and rewrite). If Vault is sealed or unreachable, wait and retry, do not crash. Setup commands were given to Nj to run with his own admin login.
5. nginx. Edit `/opt/engagehub/docker-compose.yml`: add the `navaan.conf` bind mount and external network `navaan-network` to the nginx service. Recreating nginx drops connections for a few seconds on EngageHub and Relayent, so back up the compose file first and do it in a quiet moment. Order: mount a port-80-only vhost, reload, issue the cert with `certbot certonly --webroot -w /var/www/certbot -d navaan.njlabs.dev`, then add the 443 block (copy relayent.conf, `proxy_pass http://navaan:8765`, `client_max_body_size 30M`, `proxy_read_timeout 300s`). Optional extra gate: nginx basic auth (htpasswd) in front of the app.
6. Credentials and data. YouTube tokens: sign in on the Mac, copy the token files into Vault (the server cannot open a browser). Instagram env files into Vault. OCI bucket: prefer instance principals (needs one IAM policy). Move `songs/`, `analytics.db` and `navaan.config.json` with rsync. Publish the Google OAuth app or tokens expire every 7 days in Testing mode.
7. Claude steps. `claude setup-token` on the Mac, token into Vault as `CLAUDE_CODE_OAUTH_TOKEN`. Check Anthropic's terms for always-on server use first; the alternative is an API key. Steps that drive Chrome (Suno import, Flow visuals) stay Mac-only.
8. Cut over. Create the login on the server first (setup code from the container), then stop the Mac portal scheduler so nothing publishes twice. Only one portal should run the scheduler.
9. Optional later: Postgres container. The analytics code has a placeholder switch (`db.PH`) but much SQL is SQLite-specific. Port, copy data, keep SQLite as fallback. Touches the other session's uncommitted analytics files, so settle those first.

## Verify
- `curl -sI https://navaan.njlabs.dev/` returns 200 with the sign-in page, HSTS header present, cookie has Secure and HttpOnly.
- `/api/settings` without a session returns 401.
- Setup, sign in with authenticator code, passkey on the real domain, recovery code, five wrong tries locks only that IP.
- Remotion render of a 30 s song on ARM, ffmpeg present, Claude step runs headless.
- Token refresh survives a container restart (Vault write-back), and the container recovers when Vault is sealed then unsealed.
- A scheduled test post fires from the server with the Mac off.

## Rollback
Remove the navaan mount and network from the nginx service, `docker compose up -d nginx`, delete the vhost file. The DNS record can stay. The Mac portal keeps working untouched.

## Open choices for Nj
Access gate (basic auth in front, or Tailscale only), Postgres yes or no, Claude subscription token versus API key.

## Spec Kit
Initialised in the repo root (`specify init --here --integration claude --script sh`): skills in `.claude/skills/speckit-*`, files in `.specify/`. The constitution (v1.0.0, 11 principles) is `.specify/memory/constitution.md`. Next: `/speckit-specify` for "Run NAVAAN on the Oracle VM at navaan.njlabs.dev", then `/speckit-clarify`, `/speckit-plan` (start from the plan above), `/speckit-tasks`, `/speckit-implement`.
