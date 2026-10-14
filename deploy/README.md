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
| YouTube publishing | `python3 plugins/navaan-studio/scripts/publish_youtube.py auth`, on the Mac, then `cat ~/.config/navaan/youtube_token.json \| pbcopy` | the whole file | Google refreshes it and returns the channel name |
| YouTube analytics | `python3 plugins/navaan-studio/scripts/yt_collect.py auth --account music`, then the same for `youtube_analytics_token.json` | the whole file | the same |
| Instagram | nothing to run: **Refresh now** extends a login token by 60 days (shown 10 days before it ends) | | Instagram answers `/me` |

The inspiration account uses `NAVAAN_YT_TOKEN=~/.config/navaan/youtube_token_inspiration.json` in front of the YouTube command; the popup writes it out for you.

**Google ends sign ins every 7 days while the OAuth consent screen is in Testing.** To stop that, set the app to **In production** (Google Cloud console, APIs and Services, OAuth consent screen, Publish app). For one user's own account no review is needed; Google only shows an "unverified app" screen at sign in. Then the YouTube popup should rarely appear.

Whether always-on use of a Claude subscription token fits Anthropic's terms is yours to check (T034). An API key in the same box is the fallback; no other change is needed.

## Mac-only steps
Steps that drive Chrome (Suno import and generate, Flow visuals, the YouTube Short in Studio) cannot run on the server. The studio shows "Do this on the Mac, then upload the result". Copy the song folder to the Mac, run the step there, copy the new files back:
```sh
rsync -av ods@njPRD:/opt/navaan/data/songs/<slug>/ songs/<slug>/     # fetch
# ... run the step on the Mac ...
rsync -av songs/<slug>/ ods@njPRD:/opt/navaan/data/songs/<slug>/     # return; then press Run on the server
```
Google sign in is also Mac only: run `publish_youtube.py auth` on the Mac, then `python3 deploy/vault_sync.py push`.

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

## After a VM reboot
Vault comes back sealed. Enter two unseal keys (have them ready before rebooting). Until then the sign-in page says "secrets waiting", the scheduler is `paused`, and a new login cannot be created. The container notices within 15 seconds of the unseal.

## Rollback
Remove the two navaan mounts and the `navaan-network` network from the `engagehub-nginx` service, `cd /opt/engagehub && docker compose up -d nginx`, delete `/opt/navaan/nginx/navaan.conf`. DNS and the certificate can stay. `docker compose -f deploy/compose.yml down` stops NAVAAN. The Mac portal keeps working; set its `NAVAAN_SCHEDULER` back to `on` only after the server's is `off`.
