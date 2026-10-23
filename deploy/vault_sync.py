#!/usr/bin/env python3
"""vault_sync.py  keep NAVAAN's credential files in step with HashiCorp Vault (kv-v2 mount "navaan"). Standard library only.

Author: Navjyot Nishant
Created: 2026-10-13
Last updated: 2026-10-18
Description: pull secrets to a memory-only folder, push refreshed tokens back, report status for the portal.

  watch     (server) AppRole login, pull everything, then every 30 s push files that changed and pull ones changed in Vault.
            Writes the status file the portal reads. Retries every 15 s while Vault is sealed or unreachable; keeps the last good files.
  pull      one pass of the same, then exit (status ok, or a non zero exit).
  push [f]  (your Mac) upload files from ~/.config/navaan with YOUR token: env VAULT_TOKEN or ~/.vault-token. Default: every known file present.
  set-gate  (your Mac) ask for the shared password (hidden), store its htpasswd line as gate.htpasswd. The password is never printed or stored.

Environment: NAVAAN_VAULT_ADDR (or VAULT_ADDR), NAVAAN_VAULT_ROLE_ID_FILE, NAVAAN_VAULT_SECRET_ID_FILE, NAVAAN_VAULT_MOUNT (navaan),
NAVAAN_SECRETS_DIR (~/.config/navaan), NAVAAN_SECRETS_STATUS (<dir>/secrets.status), NAVAAN_GATE_FILE (where gate.htpasswd is written, in place).
Layout: specs/001-run-navaan-on-server/contracts/vault-layout.md. Nothing here prints a secret value, role id, secret id or token."""
import os, re, sys, json, time, base64, hashlib, getpass, subprocess, urllib.request, urllib.error

ADDR = (os.environ.get("NAVAAN_VAULT_ADDR") or os.environ.get("VAULT_ADDR") or "").rstrip("/")
MOUNT = os.environ.get("NAVAAN_VAULT_MOUNT", "navaan")
DIR = os.environ.get("NAVAAN_SECRETS_DIR") or os.path.expanduser("~/.config/navaan")
STATUS = os.environ.get("NAVAAN_SECRETS_STATUS") or os.path.join(DIR, "secrets.status")
GATE_FILE = os.environ.get("NAVAAN_GATE_FILE", "")
POLL, RETRY = 30, 15
# Files that belong in Vault. Anything else in DIR (setup code, the status file) is never pushed.
KNOWN = ["instagram.env", "instagram_inspiration.env", "youtube_token.json", "youtube_token_inspiration.json", "youtube_analytics_token.json",
         "youtube_token_inspiration_analytics.json", "youtube_client_secret.json", "claude.env", "openai.env", "muse.env", "elevenlabs.env", "media.json", "gates.json", "auth.json",
         "licence.json", "devto.env", "linkedin.env", "slack.env", "slack.json"]   # licence.json: the standing licence statement (licence_cfg); it was lost at every restart because it was not listed (NAV-140)
GATE = "gate.htpasswd"
# Each content type has its own login files (accounts.<type> in navaan.config.json), named after the type: they belong in Vault too,
# or a new channel's sign-in stays in the one container that took it and is lost on the next restart.
ACCOUNT_FILE = re.compile(r"(youtube_token_[a-z][a-z0-9_]{0,40}\.json|instagram_[a-z][a-z0-9_]{0,40}\.env)")


def is_known(name): return name in KNOWN or bool(ACCOUNT_FILE.fullmatch(name))


def local_known():
    try: return {n for n in os.listdir(DIR) if is_known(n)}
    except OSError: return set()   # expected: the folder does not exist yet before the first pull


class Sealed(Exception): pass
class Down(Exception): pass


def log(msg): print("secrets: " + msg, flush=True)


def call(method, path, body=None, token=None):
    req = urllib.request.Request(ADDR + "/v1/" + path, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("X-Vault-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        if e.code == 503: raise Sealed()
        if e.code == 404: return None
        raise Down(f"HTTP {e.code} on {path.split('?')[0]}")
    except (urllib.error.URLError, OSError, ValueError) as e: raise Down(type(e).__name__)


def read_first_line(path):
    with open(path, encoding="utf-8") as f: return f.read().strip()


def approle_login():
    rid, sid = read_first_line(os.environ["NAVAAN_VAULT_ROLE_ID_FILE"]), read_first_line(os.environ["NAVAAN_VAULT_SECRET_ID_FILE"])
    r = call("POST", "auth/approle/login", {"role_id": rid, "secret_id": sid})
    if not r or "auth" not in r: raise Down("approle login refused")
    return r["auth"]["client_token"], time.time() + int(r["auth"].get("lease_duration", 3600)) * 0.8


def sha(b): return hashlib.sha256(b).hexdigest()


def dest(name):
    if name == GATE: return GATE_FILE or None
    return os.path.join(DIR, name)


def write_file(path, data, mode, inplace=False):
    """Atomic replace, or in place (same inode) for a single file that is bind mounted into another container."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if inplace:
        with open(path, "wb") as f: f.write(data)
    else:
        tmp = path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f: f.write(data)
        os.replace(tmp, path)
    os.chmod(path, mode)


def names(token):
    r = call("GET", f"{MOUNT}/metadata/?list=true", token=token)
    return list(((r or {}).get("data") or {}).get("keys") or [])


def fetch(name, token):
    r = call("GET", f"{MOUNT}/data/{name}", token=token)
    d = ((r or {}).get("data") or {}).get("data")
    if not d: return None
    return base64.b64decode(d["content_b64"]), int(d.get("mode", "600"), 8)


def store(name, data, mode, token):
    call("POST", f"{MOUNT}/data/{name}", {"data": {"content_b64": base64.b64encode(data).decode(), "mode": format(mode, "o")}}, token)


def set_status(state, detail=""):
    os.makedirs(os.path.dirname(STATUS), exist_ok=True)
    tmp = STATUS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump({"status": state, "detail": detail, "at": int(time.time())}, f)
    os.replace(tmp, STATUS)


def cycle(token, known):
    """One pass. known: name -> sha of the content last in step with Vault. Returns a one line summary."""
    pulled = pushed = 0
    remote = names(token)
    for name in sorted(set(remote) | local_known()):
        path = dest(name)
        if not path: continue
        local = open(path, "rb").read() if os.path.exists(path) else None
        if local is not None and known.get(name) not in (None, sha(local)):  # changed here since the last sync: push
            store(name, local, os.stat(path).st_mode & 0o777, token); known[name] = sha(local); pushed += 1; continue
        if name in remote:
            got = fetch(name, token)
            if got and (local is None or sha(got[0]) != sha(local)):
                write_file(path, got[0], got[1], inplace=(name == GATE)); known[name] = sha(got[0]); pulled += 1
            elif got: known[name] = sha(got[0])
        elif local is not None and is_known(name):  # new here, not in Vault yet
            store(name, local, os.stat(path).st_mode & 0o777, token); known[name] = sha(local); pushed += 1
    return f"{len(known)} files, pulled {pulled}, pushed {pushed}"


def watch(once=False):
    if not ADDR: print("NAVAAN_VAULT_ADDR is not set", file=sys.stderr); return 2
    token, exp, known, last = None, 0, {}, ""
    while True:
        try:
            if not token or time.time() > exp: token, exp = approle_login()
            summary = cycle(token, known)
            if last != "ok": log("ok (" + summary + ")")
            last = "ok"; set_status("ok", summary)
            if once: return 0
            time.sleep(POLL)
        except Sealed:
            if last != "sealed": log("Vault is sealed, waiting")
            last, token = "sealed", None; set_status("sealed")
            if once: return 1
            time.sleep(RETRY)
        except (Down, KeyError, OSError) as e:
            detail = e.__class__.__name__ if not isinstance(e, Down) else str(e)
            if last != "waiting": log("Vault not reachable, waiting (" + detail + ")")
            last, token = "waiting", None; set_status("waiting", detail)
            if once: return 1
            time.sleep(RETRY)


# ---------- your Mac ----------
def admin_token():
    t = os.environ.get("VAULT_TOKEN")
    if not t:
        try: t = read_first_line(os.path.expanduser("~/.vault-token"))
        except OSError: pass
    if not t: sys.exit("No Vault token. Run `vault login` or set VAULT_TOKEN (your own admin login).")
    return t


def push(files):
    if not ADDR: sys.exit("Set VAULT_ADDR (for example through an ssh tunnel to the Vault port).")
    t = admin_token()
    for n in files or sorted(n for n in local_known() if n != "auth.json"):
        p = n if os.path.isabs(n) else os.path.join(DIR, n)
        name = os.path.basename(p)
        if not (is_known(name) or name == GATE): print(f"skip {name}: not a known credential file"); continue
        store(name, open(p, "rb").read(), os.stat(p).st_mode & 0o777, t); print(f"pushed {name}")


def htpasswd_line(pw):
    for cmd in (["htpasswd", "-niB", "gate"], ["openssl", "passwd", "-apr1", "-stdin"]):  # password goes in on stdin, never argv
        try:
            out = subprocess.run(cmd, input=pw + "\n", capture_output=True, text=True, timeout=30).stdout.strip()
        except OSError: continue
        if out: return out if cmd[0] == "htpasswd" else "gate:" + out
    sys.exit("Need `htpasswd` (apache2-utils) or `openssl` to hash the password.")


def set_gate():
    if not ADDR: sys.exit("Set VAULT_ADDR (for example through an ssh tunnel to the Vault port).")
    t = admin_token()
    a, b = getpass.getpass("Shared gate password: "), getpass.getpass("Again: ")
    if a != b or len(a) < 16: sys.exit("They differ, or shorter than 16 characters. Nothing stored.")
    store(GATE, (htpasswd_line(a) + "\n").encode(), 0o644, t); print("stored gate.htpasswd (user: gate)")


def main(a):
    if not a or a[0] in ("-h", "--help"): print(__doc__); return 0
    try:
        if a[0] == "watch": return watch()
        if a[0] == "pull": return watch(once=True)
        if a[0] == "push": push(a[1:]); return 0
        if a[0] == "set-gate": set_gate(); return 0
    except (Down, Sealed) as e: print("Vault error: " + (str(e) or "sealed"), file=sys.stderr); return 1
    print(__doc__); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
