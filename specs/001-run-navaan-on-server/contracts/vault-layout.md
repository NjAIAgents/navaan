# Contract: Vault layout

- Mount `navaan/`, kv-v2. Keys under `navaan/data/<filename>`, value field `content_b64` (file bytes), field `mode` (octal string).
- Policy `navaan`: `create`, `read`, `update` on `navaan/data/*`; `list`, `read` on `navaan/metadata/*`. No delete, no other mount.
- AppRole `navaan`: token TTL 1 h, max 4 h. Role id and secret id live in `/opt/navaan/secrets/` as Docker secrets and are never printed.
- The sync script re-logs in when the token expires. If Vault is sealed it reports `sealed`, retries every 15 s, and keeps the last good tmpfs content.
