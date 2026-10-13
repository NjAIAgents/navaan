# Contract: HTTP edge for navaan.njlabs.dev

| Request | Behaviour |
|---------|-----------|
| `http://navaan.njlabs.dev/.well-known/acme-challenge/*` | served from `/var/www/certbot`, no auth |
| any other `http://` | 301 to `https://` |
| `https://` without the shared password | 401 with basic-auth challenge, nothing from the studio |
| `https://` with the shared password, no session cookie | studio sign-in page only; `/api/*` and media return 401 JSON `{"error":"sign in","login":true}` |
| `/auth/state` GET | JSON `{"state": "setup"\|"login"\|"authed", ...}` plus `secrets` status |
| `/auth/*` POST | login, mfa, passkey, logout, password, recovery endpoints as in `docs/AUTH.md` |
| unauthenticated clients | at most 30 requests a minute per IP (burst 20) |
| any request | headers `Strict-Transport-Security`, `X-Frame-Options DENY`, `X-Content-Type-Options nosniff`, `Referrer-Policy no-referrer`; `client_max_body_size 30M`; `proxy_read_timeout 300s` |

Upstream receives `Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto https`. The studio trusts these only when `NAVAAN_TRUST_PROXY=1`, and listens only on the private Docker network.
