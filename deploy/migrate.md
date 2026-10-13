# Move your existing work to the server (task T036, run T037)

Run on the Mac, from the repo root. Credentials do not travel this way: they go through Vault (`deploy/vault/setup.md`, section 4). `navaan.config.json` holds only paths such as `~/.config/navaan/instagram_inspiration.env`, which resolve inside the container to the same names Vault delivers, so it is safe to copy.

Replace `ods@njPRD` with however you reach the VM. `songs/` is about 1.6 GB on the Mac; add `--exclude='*.mp4'` if the finished videos already live in the bucket.

## 0. Stop writers
Stop the Mac portal (or at least make sure no step is running: `job.running` false for every song) so nothing changes mid copy.

## 1. Dry run first
```sh
rsync -avn --delete-excluded songs/ ods@njPRD:/opt/navaan/data/songs/
```
Read the list. `-n` copies nothing.

## 2. Copy
```sh
rsync -av songs/ ods@njPRD:/opt/navaan/data/songs/
scp navaan.config.json ods@njPRD:/opt/navaan/data/navaan.config.json

# the analytics database: take a consistent copy, then send it
sqlite3 ~/.local/share/navaan/analytics.db ".backup /tmp/analytics.db"
ssh ods@njPRD 'mkdir -p /opt/navaan/data/state'
scp /tmp/analytics.db ods@njPRD:/opt/navaan/data/state/analytics.db && rm /tmp/analytics.db
```
Then on the VM: `sudo chown -R 10001 /opt/navaan/data` (the container user) and `docker restart navaan`.

## 3. Compare (VM)
```sh
ls /opt/navaan/data/songs | wc -l                                  # same as: ls songs | wc -l   (Mac)
sqlite3 /opt/navaan/data/state/analytics.db 'select count(*) from media'   # same as the Mac's
```
Open the studio, open one migrated song and play it.

## 4. Scheduler hand-over
Any item with a schedule exists on both machines now. Follow `deploy/README.md`, "Scheduler ownership": Mac off first, server on second. Never both.

The Mac keeps working untouched; it is just no longer the one that publishes.
