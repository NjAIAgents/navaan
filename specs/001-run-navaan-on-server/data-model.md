# Data Model: Run NAVAAN on the Oracle VM

## Server file layout

| Path (host) | Mounted at | Contents | Backed up |
|-------------|-----------|----------|-----------|
| `/opt/navaan/data/songs/` | `/app/songs` | song folders, `meta.json`, media | yes |
| `/opt/navaan/data/state/` | `/home/navaan/.local/share/navaan` | `analytics.db` | yes |
| `/opt/navaan/data/navaan.config.json` | `/app/navaan.config.json` | accounts, bucket, publish options (no secrets) | yes |
| tmpfs | `/home/navaan/.config/navaan` | materialised secrets, `auth.json`, `secrets.status` | no (source of truth is Vault) |
| `/opt/navaan/secrets/` | Docker secrets | `vault_role_id`, `vault_secret_id` | no |
| `/opt/navaan/nginx/htpasswd` | into nginx | bcrypt hash of the shared password | recreate from Vault |

## Entities (from the spec)

- **Owner account**: `auth.json` fields `user`, `pw` (scrypt), `totp`, `recovery[]` (hashes), `passkeys[]`. Stored in Vault key `auth.json`; written back after changes.
- **Session**: in memory only, token, created, last seen. Lost on restart by design.
- **Platform credential**: one Vault key per file: `instagram.env`, `instagram_inspiration.env`, `youtube_token.json`, `youtube_token_inspiration.json`, `youtube_analytics_token.json`, `youtube_token_inspiration_analytics.json`, `youtube_client_secret.json`, `claude.env`, `gate.htpasswd`. Each has an expiry note in its metadata where known (Instagram market keys 2026-12-12, Google tokens weekly in Testing mode).
- **Schedule**: unchanged, `meta.schedule` inside each song's `meta.json`.
- **Studio data set**: the first three rows of the table above.

## State transitions

- Secrets status: `waiting` (Vault unreachable) -> `sealed` (Vault up, sealed) -> `ok` (pulled). Any state returns to `waiting` if Vault drops later. The scheduler runs only in `ok`; the portal serves in every state.
- Token write-back: file hash changes on tmpfs -> within 30 s pushed as a new Vault version; failures retry, never delete.
