# Portal login

The portal needs a sign in: password, then a second step (authenticator app code, passkey, or a one time recovery code).

- First run: open the portal. It asks for the setup code in `~/.config/navaan/auth_setup_code` (`cat` it, or run `auth.py setup-code`). Then scan the QR code with an authenticator app and save the 10 recovery codes.
- Stored only in `~/.config/navaan/auth.json` (mode 600): scrypt password hash, TOTP secret, recovery code hashes, passkey public keys. Nothing goes in the project.
- Sessions: the browser stays signed in for 7 days, also across portal restarts and server updates. Only a hash of each session token is stored, in `~/.local/share/navaan/sessions.json` (mode 600, next to `analytics.db`; `NAVAAN_SESSIONS_DIR` moves it). Sign out, a password change (other sessions) and `auth.py reset` end them. Scheduled publishing does not need a session.
- Five wrong tries lock sign in for 15 s, doubling up to 15 min. The count is per client address, so a stranger cannot lock you out.
- Once a passkey is added, the sign-in page shows **Sign in with passkey**: Touch ID, Windows Hello or the security key alone signs you in, with no user name, password or code. The passkey itself requires on-device verification (biometrics or PIN), so it is two factors in one. The password path keeps working beside it.
- Passkeys: open the portal as `http://localhost:8765` (not the IP address). Needs the Python package `cryptography`. Add or remove them in Settings, Security.
- Lost phone: use a recovery code, then make new codes in Settings. Lost everything: `python3 plugins/navaan-studio/scripts/auth.py reset`, restart the portal, set up again.
- Dev only: `NAVAAN_AUTH=off` runs without login.

## On the server (https://navaan.njlabs.dev)

- One gate, the studio's own login above (password plus a second step, lockout per client IP). The shared nginx password (`auth_basic`, user `gate`) was switched off on 2026-10-14 because it added little next to the second factor and made the browser prompt twice; nginx still throttles per IP (30 requests a minute without a session cookie, 300 with). To switch it back on, see the note in `deploy/nginx/navaan.conf`. The user name may be an email address (new logins keep the `@`); sign in ignores case and punctuation like `@`, so an older login stored as `name.gmail.com` still accepts the email.
- `NAVAAN_PUBLIC_HOST` lets the portal accept that host name. `NAVAAN_TRUST_PROXY=1` takes the client address from `X-Real-IP` (so the lockout is per real visitor) and the scheme from `X-Forwarded-Proto` (so cookies get `Secure` and passkeys use `https://navaan.njlabs.dev`). Set it only behind nginx on a private network; with it off the headers are ignored.
- `auth.json` lives in Vault (`navaan/data/auth.json`) and is copied to the container's memory-only folder; changes (new recovery codes, a passkey) are written back within 30 seconds. First run: `docker exec navaan cat /home/navaan/.config/navaan/auth_setup_code`.
- If Vault is sealed after a reboot, the sign-in page shows "Secrets waiting" and creating a new login is refused until Vault is unsealed, so a fresh login can never replace the real one.
- Passkeys are bound to the host name: add them on `navaan.njlabs.dev`, not on localhost.
- Tests: `python3 plugins/navaan-studio/tests/test_auth.py`.
