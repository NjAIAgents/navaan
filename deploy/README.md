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
| YouTube publishing and analytics | **Sign in with Google** in the popup: it opens Google in your own browser, you allow access, Google sends you to a `localhost` page that cannot open, and you paste that address back (the server needs no browser). Or, on a Mac terminal: `publish_youtube.py auth` / `yt_collect.py auth --account music`, then `cat ~/.config/navaan/<file> \| pbcopy` | the address, or the whole file | the code is exchanged here, then Google refreshes the token and returns the channel name |
| Instagram | nothing to run: **Refresh now** extends a login token by 60 days (shown 10 days before it ends) | | Instagram answers `/me` |

The inspiration account uses `NAVAAN_YT_TOKEN=~/.config/navaan/youtube_token_inspiration.json` in front of the YouTube command; the popup writes it out for you.

**Google ends sign ins every 7 days while the OAuth consent screen is in Testing.** To stop that, set the app to **In production** (Google Cloud console, APIs and Services, OAuth consent screen, Publish app). For one user's own account no review is needed; Google only shows an "unverified app" screen at sign in. Then the YouTube popup should rarely appear.

Whether always-on use of a Claude subscription token fits Anthropic's terms is yours to check (T034). An API key in the same box is the fallback; no other change is needed.

## Mac-only steps
Suno import of a public song no longer needs a browser: the server reads the public clip data and downloads the audio itself (`suno_import.py auto <slug>`). It falls back to the Chrome step, which cannot run on the server, only for a private song or when `suno.auto_failed` is set in meta.json. Steps that drive Chrome (Suno generate, Flow visuals, the YouTube Short in Studio, the Suno import fallback) cannot run on the server. The studio shows "Do this on the Mac, then upload the result". Copy the song folder to the Mac, run the step there, copy the new files back:
```sh
rsync -av ods@njPRD:/opt/navaan/data/songs/<slug>/ songs/<slug>/     # fetch
# ... run the step on the Mac ...
rsync -av songs/<slug>/ ods@njPRD:/opt/navaan/data/songs/<slug>/     # return; then press Run on the server
```
Google sign in is also Mac only: run `publish_youtube.py auth` on the Mac, then `python3 deploy/vault_sync.py push`.

## Cleaned songs: files come back from the bucket on demand
After a song is archived and cleaned locally, its pictures and audio are only in the bucket. The portal fetches a missing picture or audio file for a song that has a recorded cloud copy the first time something asks for it (covers in the library, `/media/...`), and the YouTube upload and thumbnail steps fetch the file they need. Each fetch is one `oci os object get` of that single file (about 2 s), the key comes from the song's own `cloud.prefix`, paths outside a song folder are refused, and a file that is not in the bucket is remembered for an hour so it is not asked for again. Videos are not fetched by the picture route (too big for a page load); the upload step still fetches the one video it needs. Fetched files stay on the server's disk until the next local cleanup.

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
