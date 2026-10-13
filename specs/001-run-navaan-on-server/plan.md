# Implementation Plan: Run NAVAAN on the Oracle VM at navaan.njlabs.dev

**Branch**: `001-run-navaan-on-server` (spec directory only, no git branch) | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-run-navaan-on-server/spec.md`

## Summary

Run the existing NAVAAN portal and scheduler in one container on Nj's Oracle VM, reached at https://navaan.njlabs.dev through the nginx that already fronts the other apps. A shared-password prompt at nginx stands in front of the studio's own login (password plus second factor). Platform credentials, the Claude subscription token and the shared password live in the existing Vault under a separate mount and are pulled into memory-only storage at start, with changed tokens pushed back. Songs, the analytics file database and `navaan.config.json` live on a persistent volume with a nightly backup to the existing OCI bucket. Server files live under `deploy/`; the plugin gains only a few environment-driven switches.

## Technical Context

**Language/Version**: Python 3.13 (portal, orchestrator, scripts), Node 22 (Remotion render), Bash for the entrypoint

**Primary Dependencies**: standard library first; `cryptography` (passkeys), ffmpeg, Remotion 4.0.535 with its headless Chrome (linux-arm64), `claude` CLI, nginx (existing container), HashiCorp Vault 1.17.6 (existing container), certbot (existing snap)

**Storage**: files on a persistent volume (`songs/`, `analytics.db` SQLite file, `navaan.config.json`); secrets in Vault; tmpfs for materialised secrets

**Testing**: scripted tests (`tests/` in the plugin, `/tmp`-style auth suite promoted into `plugins/navaan-studio/tests/`), shell checks in `quickstart.md`, one real ARM render

**Target Platform**: Ubuntu 22.04 aarch64 (Oracle), Docker compose, 4 cores, 23 GiB RAM

**Project Type**: web service (existing portal) plus deployment bundle

**Performance Goals**: sign-in page under 3 s; 30 s song renders in under 10 min (Mac does about 72 s)

**Constraints**: nothing may change for EngageHub or Relayent beyond one added mount, one added network and one added vhost on their nginx; Vault is Shamir manual unseal; the sandbox cannot reach the VM, so Nj runs server commands

**Scale/Scope**: one user, one login, a few songs per week

## Constitution Check

*GATE: passed before Phase 0, re-checked after Phase 1.*

| Principle | Status | How the plan satisfies it |
|-----------|--------|---------------------------|
| I Humans own the gates | Pass | No gate logic changes. The server scheduler only fires steps whose gates are approved. |
| II Secrets out of sight | Pass | Vault mount `navaan/`, AppRole limited to it, secret id as Docker secret, tmpfs materialisation, nothing in image or compose. Basic-auth hash file on disk is a hash only, source of truth is Vault. |
| III Files are state | Pass | State stays in `meta.json` and song folders on a volume. Data move is a copy of those files. |
| IV Local first, no hidden spend | Pass | Local Remotion render is used. Flow stays Mac-only. |
| V Safe by default | Pass | All public behaviour sits behind env vars (`NAVAAN_PUBLIC_HOST`, `NAVAAN_TRUST_PROXY`, `NAVAAN_BIND`, `NAVAAN_HEADLESS`). Defaults keep localhost behaviour. |
| VI One plugin, many places | Pass | Server files under `deploy/`, image built from a commit, config and data never baked in. |
| VII Small dependency surface | Pass | No new Python packages. The Vault client is a small `urllib` script. |
| VIII Prove it | Pass | `quickstart.md` lists runnable checks; tasks include an ARM render and a sealed-Vault drill. |
| IX Don't clobber | Pass with care | `navaan_ui.py` and `ui.html` hold another session's edits. Tasks start by committing only own hunks. |
| X Recoverable and visible | Pass | Bounded retries, history lines, nginx and compose backups, rollback in quickstart. |
| XI Honest data | Pass | Verification uses a synthetic song, not other people's media. |

## Project Structure

### Documentation (this feature)

```text
specs/001-run-navaan-on-server/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── http-edge.md
│   ├── environment.md
│   └── vault-layout.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
deploy/
├── Dockerfile                 # arm64 image: python 3.13, node 22, ffmpeg, chromium libs, claude CLI, plugin installed from the repo
├── compose.yml                # project "navaan": service navaan, network navaan-network, volumes, tmpfs, secrets
├── entrypoint.sh              # waits for Vault, pulls secrets to tmpfs, starts watcher, starts the portal
├── vault_sync.py              # pull, push-on-change, status file (urllib only)
├── nginx/
│   ├── navaan.conf            # port 80 ACME + redirect, port 443 vhost, auth_basic, rate limit, proxy headers
│   └── README.md              # exact edit to /opt/engagehub/docker-compose.yml, backup and rollback
├── backup/
│   └── backup.sh              # nightly tar of the data volume to the OCI bucket, retention 14 days
├── vault/
│   └── setup.md               # mount, policy, AppRole commands (Nj runs them)
└── README.md                  # install, update, rollback

plugins/navaan-studio/
├── scripts/
│   ├── navaan_ui.py           # NAVAAN_PUBLIC_HOST, NAVAAN_TRUST_PROXY, NAVAAN_BIND, NAVAAN_SCHEDULER, secrets status
│   ├── navaan.py              # chrome-only steps show a Mac-only hint when NAVAAN_HEADLESS=1
│   ├── settings_api.py        # hide local-browser sign-in buttons when headless, show the Mac command
│   └── auth.py                # done: per-IP lockout, https cookies
└── tests/
    └── test_auth.py           # promoted from the scratch suite
```

**Structure Decision**: deployment files go in a new top-level `deploy/` so the plugin stays shareable (constitution VI). Application changes are small, env-driven edits to the existing portal.

## Phases

- **Phase 0** produced [research.md](research.md): each unknown resolved as decision, rationale, alternatives.
- **Phase 1** produced [data-model.md](data-model.md), [contracts/](contracts/) and [quickstart.md](quickstart.md).

## Open items to verify on the VM (tasks start here)

1. Which Docker network `engagehub-vault` is on, and whether NAVAAN may join it or needs a dedicated network.
2. How certbot reloads nginx after renewal today (deploy hook), so NAVAAN's cert is picked up the same way.
3. `docker compose` version and whether `/opt/engagehub/docker-compose.yml` already uses external networks for Relayent (copy that exact style).
4. Whether `chrome-headless-shell` for linux-arm64 runs in the image (first render is the test).

## Complexity Tracking

| Deviation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| The shared-password gate throttles unauthenticated clients per IP instead of counting failed attempts and locking out (FR-017 wording) | nginx cannot count failed basic-auth attempts | A custom auth service in front would be a new component to maintain. The throttle (30 requests a minute per IP without a session cookie) limits guessing to a rate that a strong password survives. |
| NAVAAN's container joins the Vault network | The sync script needs to reach Vault | Publishing Vault's port on the host would expose it more widely. Task 1 above may replace this with a dedicated network. |
