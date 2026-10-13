# Portal login

The portal needs a sign in: password, then a second step (authenticator app code, passkey, or a one time recovery code).

- First run: open the portal. It asks for the setup code in `~/.config/navaan/auth_setup_code` (`cat` it, or run `auth.py setup-code`). Then scan the QR code with an authenticator app and save the 10 recovery codes.
- Stored only in `~/.config/navaan/auth.json` (mode 600): scrypt password hash, TOTP secret, recovery code hashes, passkey public keys. Nothing goes in the project.
- Sessions: 12 hours at most, 2 hours idle, in memory (a portal restart signs you out). Scheduled publishing does not need a session.
- Five wrong tries lock sign in for 15 s, doubling up to 15 min.
- Passkeys: open the portal as `http://localhost:8765` (not the IP address). Needs the Python package `cryptography`. Add or remove them in Settings, Security.
- Lost phone: use a recovery code, then make new codes in Settings. Lost everything: `python3 plugins/navaan-studio/scripts/auth.py reset`, restart the portal, set up again.
- Dev only: `NAVAAN_AUTH=off` runs without login.
