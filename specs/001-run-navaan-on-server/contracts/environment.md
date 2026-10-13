# Contract: environment switches

| Variable | Default | Effect |
|----------|---------|--------|
| `NAVAAN_PUBLIC_HOST` | unset | extra allowed Host value, for example `navaan.njlabs.dev` |
| `NAVAAN_TRUST_PROXY` | `0` | `1` reads client IP from `X-Real-IP` and scheme from `X-Forwarded-Proto` |
| `NAVAAN_BIND` | `127.0.0.1` | `0.0.0.0` inside the container only |
| `NAVAAN_SCHEDULER` | `on` | `off` stops the scheduler thread (Mac after cutover) |
| `NAVAAN_HEADLESS` | `0` | `1` marks Chrome-driven steps and local-browser sign-ins as Mac-only |
| `NAVAAN_AUTH` | on | `off` disables login (development only, never on the server) |
| `NAVAAN_SECRETS_STATUS` | `~/.config/navaan/secrets.status` | file the portal reads for Vault status |
| `CLAUDE_CODE_OAUTH_TOKEN` or `ANTHROPIC_API_KEY` | from Vault | credential for `claude -p` steps |
| `NAVAAN_CLAUDE_CMD`, `NAVAAN_CLAUDE_FLAGS` | existing | unchanged overrides |

Defaults keep today's localhost behaviour (constitution V).
