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
| `NAVAAN_SCHEDULER` | `off` until cutover, then `on` | which machine publishes on schedule |
| `NAVAAN_VAULT_*` | see `compose.yml` | Vault address and the AppRole files |

## Install (first time)
1. **Vault**: `vault/setup.md` (mount, policy, AppRole, secret files), then push the secrets from the Mac.
2. **Data folder**: `sudo install -d -o 10001 /opt/navaan/data/songs /opt/navaan/data/state`, then `migrate.md`.
3. **Network and container**: `cd /opt/navaan/repo && VAULT_NETWORK=<network of engagehub-vault> docker compose -f deploy/compose.yml up -d --build`. Find the Vault network with `docker inspect engagehub-vault --format '{{json .NetworkSettings.Networks}}'`.
4. **nginx and certificate**: `nginx/README.md`.
5. **First sign in**: `docker exec navaan cat /home/navaan/.config/navaan/auth_setup_code`, open the site, enter the shared password, then create the login. Save the recovery codes. The login is written to Vault within 30 seconds.

## Update
```sh
cd /opt/navaan/repo && git pull
VAULT_NETWORK=... docker compose -f deploy/compose.yml up -d --build
```
Data, secrets and the Vault login survive (they are outside the image). Sessions end (they live in memory).

## Scheduler ownership
Only one portal may run the scheduler. Cutover order, exactly:
1. On the Mac: start the portal with `NAVAAN_SCHEDULER=off` (or stop it).
2. On the server: set `NAVAAN_SCHEDULER=on` (`NAVAAN_SCHEDULER=on docker compose -f deploy/compose.yml up -d`).
Never both. The header chip in the studio shows `scheduler on|off|paused`. `paused` means Vault is sealed or unreachable: nothing publishes until it is back, because the tokens are not there.

## Claude credential
The `claude` steps use `CLAUDE_CODE_OAUTH_TOKEN` (a subscription token from `claude setup-token`) or `ANTHROPIC_API_KEY`, both read from the Vault file `claude.env`; if both are present the API key is used. Switch by editing that one secret (push a new `claude.env` from the Mac); no restart is needed, the next Claude step reads it. Whether always-on subscription use fits Anthropic's terms is yours to check (T034); the API key is the fallback. Settings shows which one is in use and whether the last step was refused or rate limited.

## Mac-only steps
Steps that drive Chrome (Suno import and generate, Flow visuals, the YouTube Short in Studio) cannot run on the server. The studio shows "Do this on the Mac, then upload the result". Copy the song folder to the Mac, run the step there, copy the new files back:
```sh
rsync -av ods@njPRD:/opt/navaan/data/songs/<slug>/ songs/<slug>/     # fetch
# ... run the step on the Mac ...
rsync -av songs/<slug>/ ods@njPRD:/opt/navaan/data/songs/<slug>/     # return; then press Run on the server
```
Google sign in is also Mac only: run `publish_youtube.py auth` on the Mac, then `python3 deploy/vault_sync.py push`.

## Backup and restore
Nightly (as a user that can read `/opt/navaan/data` and use the bucket through instance principals):
```sh
echo '17 3 * * * NAVAAN_BACKUP_BUCKET=<bucket> /opt/navaan/repo/deploy/backup/backup.sh >> /var/log/navaan-backup.log 2>&1' | crontab -
```
Restore to a scratch folder and compare:
```sh
oci os object get --auth instance_principal --bucket-name <bucket> --name navaan-backup/<file>.tar.gz --file /tmp/restore.tar.gz
mkdir /tmp/restore && tar -C /tmp/restore -xzf /tmp/restore.tar.gz
find /tmp/restore/navaan-data/songs -type f | wc -l ; find /opt/navaan/data/songs -type f | wc -l
```
To restore for real: stop the container, replace `/opt/navaan/data` with `navaan-data/`, `chown -R 10001`, start it.

## After a VM reboot
Vault comes back sealed. Enter two unseal keys (have them ready before rebooting). Until then the sign-in page says "secrets waiting", the scheduler is `paused`, and a new login cannot be created. The container notices within 15 seconds of the unseal.

## Rollback
Remove the two navaan mounts and the `navaan-network` network from the `engagehub-nginx` service, `cd /opt/engagehub && docker compose up -d nginx`, delete `/opt/navaan/nginx/navaan.conf`. DNS and the certificate can stay. `docker compose -f deploy/compose.yml down` stops NAVAAN. The Mac portal keeps working; set its `NAVAAN_SCHEDULER` back to `on` only after the server's is `off`.
