#!/usr/bin/env python3
"""auth.py  login for the NAVAAN portal: password, then a second factor (authenticator app code, passkey, or a recovery code).

The owner's credentials live in ~/.config/navaan/auth.json (mode 600), never in the project and never in the database (so not in its backups): a scrypt password hash, the TOTP secret,
hashes of the recovery codes and the passkey public keys. Sessions last 7 days and survive a restart: a row in Postgres (core.sessions, see core_store.py) keyed by a hash of the
session token, with its own CSRF token, the person's roles and permissions. Sign-in attempts and the audit trail are there too. The older sessions.json (env NAVAAN_SESSIONS_DIR) is read once and moved aside.
Standard library only; passkeys also need the `cryptography` package (the rest works without it).

First run: the portal shows a setup page. It asks for the setup code that is written to ~/.config/navaan/auth_setup_code
(so only someone who can read your files can create the login). The code file is deleted when setup finishes.

CLI:  auth.py status | setup-code | reset      reset deletes the login, the next portal start asks for a setup code again.
Dev only: NAVAAN_AUTH=off turns the login off for that process."""
import os, sys, json, time, hmac, hashlib, base64, secrets, struct, threading, re
import navaan_log as L
import core_store as CS
LOG = L.get("auth")

DIR = os.environ.get("NAVAAN_AUTH_DIR") or os.path.expanduser("~/.config/navaan")
FILE = os.path.join(DIR, "auth.json")
CODE_FILE = os.path.join(DIR, "auth_setup_code")
COOKIE = "navaan_session"
SESSION_MAX = 7 * 24 * 3600   # the browser stays signed in for a week
SESSION_IDLE = 7 * 24 * 3600
TICKET_TTL = 300
LOCK = threading.Lock()
_LEGACY_DONE = False
_GC_AT = 0.0
PERMISSIONS = ("studio.access", "studio.approve", "studio.settings", "library.view", "playlists.write", "account.manage")   # what NAVAAN_AUTH=off grants (development only)
TICKETS = {}    # ticket -> {"exp", "user", "tries", "challenge"}
PENDING = {}    # setup in progress: {"exp", "user", "pw", "secret"}
CTX = threading.local()  # per request: .ip and .https, set by state() and handle_post()


def disabled(): return os.environ.get("NAVAAN_AUTH", "").lower() == "off"
def now(): return time.time()
def clean_user(u): return re.sub(r"[^A-Za-z0-9._@+-]", "", str(u or "").strip())[:64]  # what is stored at setup; an email address is fine
def user_key(u): return re.sub(r"[^A-Za-z0-9._-]", "", str(u or "").strip().lower())[:64]  # what sign in compares: lenient, so an email works whether or not the stored name kept its @ (older logins stored it without)
def b64u(b): return base64.urlsafe_b64encode(b).rstrip(b"=").decode()
def unb64u(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ---------- store ----------
def load():
    try:
        with open(FILE, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError) as _e: L.ignored(LOG, "load: OSError/ValueError (optional or expected)", _e); return None


def save(d):
    os.makedirs(DIR, exist_ok=True)
    tmp = FILE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f: json.dump(d, f, indent=2)
    os.replace(tmp, FILE); os.chmod(FILE, 0o600)


def configured(): return bool((load() or {}).get("pw"))


def ensure_setup_code():
    """Create the one-time setup code when there is no login yet. Returns the file path or None."""
    if configured() or disabled(): return None
    if not os.path.exists(CODE_FILE):
        os.makedirs(DIR, exist_ok=True)
        fd = os.open(CODE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f: f.write("-".join(secrets.token_hex(2) for _ in range(3)) + "\n")
    return CODE_FILE


def setup_code():
    try: return open(CODE_FILE).read().strip()
    except OSError as _e: L.ignored(LOG, "setup_code: OSError (optional or expected)", _e); return ""


# ---------- passwords ----------
def hash_pw(pw, salt=None):
    salt = salt or os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)
    return {"salt": b64u(salt), "hash": b64u(h), "n": 14}


def check_pw(pw, rec):
    try:
        h = hashlib.scrypt(pw.encode(), salt=unb64u(rec["salt"]), n=2 ** int(rec.get("n", 14)), r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(b64u(h), rec["hash"])
    except Exception as _e: L.soft(LOG, "check_pw_error"); return False


def pw_problem(pw):
    if len(pw) < 12: return "Use at least 12 characters."
    if len(set(pw)) < 5: return "Use more different characters."
    return ""


# ---------- TOTP (RFC 6238, SHA1, 6 digits, 30 s) ----------
def new_secret(): return base64.b32encode(os.urandom(20)).decode().rstrip("=")


def totp(secret, step):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    mac = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    o = mac[-1] & 15
    return "%06d" % ((struct.unpack(">I", mac[o:o + 4])[0] & 0x7FFFFFFF) % 1000000)


def totp_check(secret, code, last_step=0, at=None):
    """Returns the matching step (more than last_step) or 0."""
    code = re.sub(r"\D", "", str(code or ""))
    if len(code) != 6: return 0
    cur = int((at or now()) // 30)
    for s in (cur, cur - 1, cur + 1):
        if s > last_step and hmac.compare_digest(totp(secret, s), code): return s
    return 0


def otpauth(secret, user): return f"otpauth://totp/NAVAAN:{user}?secret={secret}&issuer=NAVAAN"


# ---------- recovery codes ----------
def new_recovery():
    codes = [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(10)]
    return codes, [hashlib.sha256(c.encode()).hexdigest() for c in codes]


def use_recovery(d, code):
    h = hashlib.sha256(re.sub(r"\s", "", str(code or "").lower()).encode()).hexdigest()
    for x in d.get("recovery", []):
        if hmac.compare_digest(x, h): d["recovery"].remove(x); return True
    return False


# ---------- throttle ----------
# One counter per client address, in Postgres (core.login_attempts): a stranger cannot lock you out, and it survives a restart.
def _ip(): return getattr(CTX, "ip", "") or "local"


def locked():
    n, last = CS.failures(_ip())
    return max(0, int(last + min(900, 15 * 2 ** (n - 5)) - now())) if n >= 5 else 0


def fail():
    CS.record_attempt(_ip(), False)
    n, last = CS.failures(_ip())
    until = last + min(900, 15 * 2 ** (n - 5)) if n >= 5 else 0
    L.event(LOG, "warning", "auth_failed", ip=_ip(), fails=n, locked_seconds=max(0, int(until - now())))   # a failed sign-in is not an error in the app, but it is worth seeing
    _audit("login_failed", ip=_ip(), fails=n)


def ok_reset(): CS.record_attempt(_ip(), True)


def _audit(action, user=None, **detail):
    """A line in the audit trail. It must never break signing in, so a failure is logged and swallowed."""
    try:
        CS.audit(action, actor_id=(user or {}).get("id") if isinstance(user, dict) else None, subject=(user or {}).get("username") if isinstance(user, dict) else user, ip=detail.pop("ip", _ip()), detail=detail)
    except Exception:
        L.exc(LOG, "audit_failed", action=action)


# ---------- sessions ----------
def skey(token): return hashlib.sha256(token.encode()).hexdigest()


def sess_file(): return os.path.join(os.environ.get("NAVAAN_SESSIONS_DIR") or os.path.expanduser("~/.local/share/navaan"), "sessions.json")


def _import_legacy_sessions():
    """Once per process: sessions.json from before Postgres is taken in (so a deploy does not sign you out), then moved aside."""
    global _LEGACY_DONE
    if _LEGACY_DONE: return
    _LEGACY_DONE = True
    p = sess_file()
    try:
        with open(p, encoding="utf-8") as f: old = json.load(f)
    except (OSError, ValueError) as _e: L.ignored(LOG, "no sessions.json to import", _e); return
    n = now(); taken = 0
    for h, v in (old or {}).items():
        if not isinstance(v, dict) or n - v.get("created", 0) > SESSION_MAX or n - v.get("last", 0) > SESSION_IDLE: continue
        u = CS.ensure_user(clean_user(v.get("user")) or "navaan", role="owner")
        CS.import_session(h, u["id"], secrets.token_urlsafe(24), v.get("created", n), v.get("last", n), SESSION_MAX); taken += 1
    try: os.replace(p, p + ".imported")
    except OSError as _e: L.ignored(LOG, "cannot move sessions.json aside", _e)
    L.event(LOG, "info", "legacy_sessions_imported", sessions=taken)


def start_session(user):
    t = secrets.token_urlsafe(32)
    u = CS.ensure_user(clean_user(user) or user, role="owner")
    CS.create_session(skey(t), u["id"], secrets.token_urlsafe(24), _ip(), getattr(CTX, "ua", None), SESSION_MAX)
    _audit("login", u, ip=_ip())
    return t


def cookie_header(token, clear=False):
    sec = "; Secure" if getattr(CTX, "https", False) else ""
    if clear: return f"{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0{sec}"
    return f"{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSION_MAX}{sec}"


def token_from(cookie_hdr):
    for part in (cookie_hdr or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE: return v
    return ""


def session(cookie_hdr):
    """The live session for this Cookie header, or None: {"user", "user_id", "csrf", "roles", "permissions"}. Touches the idle clock. A database error means no session (closed, not open)."""
    if disabled():   # development only. NAVAAN_AUTH_OFF_ROLE=listener signs the one local person in as a listener (the browser checks use it to see the listener side)
        if os.environ.get("NAVAAN_AUTH_OFF_ROLE", "").lower() == "listener": return {"user": "listener", "user_id": "", "csrf": "", "roles": ["listener"], "permissions": ["library.view", "playlists.write", "account.manage"]}
        return {"user": "local", "user_id": "", "csrf": "", "roles": ["owner"], "permissions": list(PERMISSIONS)}
    tok = token_from(cookie_hdr)
    if not tok: return None
    try:
        _import_legacy_sessions()
        return CS.get_session(skey(tok), SESSION_IDLE)
    except Exception:
        L.exc(LOG, "session_lookup_failed"); return None


def can(sess, permission):
    """Whether this session may do `permission` (a route asks for a permission, never for a role name)."""
    return bool(sess) and permission in (sess.get("permissions") or ())


def end_session(cookie_hdr):
    tok = token_from(cookie_hdr)
    if tok: CS.revoke_session(skey(tok))


def _gc():
    global _GC_AT
    n = now()
    with LOCK:
        for k in [k for k, v in TICKETS.items() if v["exp"] < n]: TICKETS.pop(k, None)
        if PENDING.get("exp", 1e18) < n: PENDING.clear()
    if n - _GC_AT > 600:   # the database part is cheap but not free: every ten minutes is enough
        _GC_AT = n
        try: CS.gc(SESSION_IDLE)
        except Exception: L.exc(LOG, "auth_gc_failed")


# ---------- CBOR (just enough for WebAuthn) ----------
def cbor(b, i=0):
    ib = b[i]; mt, ai = ib >> 5, ib & 31; i += 1
    if ai < 24: val = ai
    elif ai == 24: val = b[i]; i += 1
    elif ai == 25: val = struct.unpack(">H", b[i:i + 2])[0]; i += 2
    elif ai == 26: val = struct.unpack(">I", b[i:i + 4])[0]; i += 4
    elif ai == 27: val = struct.unpack(">Q", b[i:i + 8])[0]; i += 8
    else: raise ValueError("unsupported cbor")
    if mt == 0: return val, i
    if mt == 1: return -1 - val, i
    if mt == 2: return bytes(b[i:i + val]), i + val
    if mt == 3: return bytes(b[i:i + val]).decode(), i + val
    if mt == 4:
        out = []
        for _ in range(val): x, i = cbor(b, i); out.append(x)
        return out, i
    if mt == 5:
        out = {}
        for _ in range(val): k, i = cbor(b, i); v, i = cbor(b, i); out[k] = v
        return out, i
    raise ValueError("unsupported cbor type")


# ---------- passkeys (WebAuthn, ES256, no attestation) ----------
def _ec():
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.exceptions import InvalidSignature
        return ec, hashes, serialization, InvalidSignature
    except ImportError as _e: L.ignored(LOG, "_ec: ImportError (optional or expected)", _e); return None


def passkeys_available(): return _ec() is not None


def rp_of(host_hdr):
    """(rp id, origin) from the Host header, or (None, None) when the host is an IP (passkeys need a name such as localhost)."""
    h = (host_hdr or "").strip(); name = h.split(":")[0]
    if re.match(r"^\d+\.\d+\.\d+\.\d+$", name): return None, None
    return name, ("https://" if getattr(CTX, "https", False) else "http://") + h


def _client_check(cd_b64, want_type, challenge, origin):
    cd_raw = unb64u(cd_b64); cd = json.loads(cd_raw)
    if cd.get("type") != want_type: raise ValueError("wrong type")
    if not hmac.compare_digest(cd.get("challenge", ""), challenge): raise ValueError("challenge mismatch")
    if cd.get("origin") != origin: raise ValueError("origin mismatch")
    return cd_raw


def _flags_ok(auth_data, rp):
    if auth_data[:32] != hashlib.sha256(rp.encode()).digest(): raise ValueError("rp mismatch")
    fl = auth_data[32]
    if not (fl & 1 and fl & 4): raise ValueError("user presence and verification are required")
    return fl


def reg_options(d, host, user):
    rp, _ = rp_of(host)
    if not rp: raise ValueError("Open the portal as http://localhost:8765 to use passkeys (an IP address cannot be used).")
    if not passkeys_available(): raise ValueError("Passkeys need the Python package 'cryptography' (pip3 install cryptography).")
    ch = b64u(os.urandom(32))
    tk = secrets.token_urlsafe(16)
    with LOCK: TICKETS[tk] = {"exp": now() + TICKET_TTL, "user": user, "challenge": ch, "tries": 0, "kind": "reg"}
    return {"ticket": tk, "publicKey": {"challenge": ch, "rp": {"id": rp, "name": "NAVAAN"}, "user": {"id": b64u(hashlib.sha256(user.encode()).digest()[:16]), "name": user, "displayName": user},
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}], "timeout": 120000, "attestation": "none",
            "authenticatorSelection": {"userVerification": "required", "residentKey": "preferred"},
            "excludeCredentials": [{"type": "public-key", "id": p["id"]} for p in d.get("passkeys", [])]}}


def reg_verify(d, host, body):
    ec, hashes, ser, _ = _ec()
    rp, origin = rp_of(host)
    with LOCK: t = TICKETS.pop(body.get("ticket", ""), None)
    if not t or t["exp"] < now() or t.get("kind") != "reg": raise ValueError("expired, try again")
    _client_check(body["clientDataJSON"], "webauthn.create", t["challenge"], origin)
    att, _ = cbor(unb64u(body["attestationObject"]))
    ad = att["authData"]; _flags_ok(ad, rp)
    if not ad[32] & 0x40: raise ValueError("no credential data")
    n = struct.unpack(">H", ad[53:55])[0]; cid = ad[55:55 + n]
    key, _ = cbor(ad, 55 + n)
    if key.get(1) != 2 or key.get(3) != -7 or key.get(-1) != 1: raise ValueError("only ES256 passkeys are supported")
    pub = ec.EllipticCurvePublicNumbers(int.from_bytes(key[-2], "big"), int.from_bytes(key[-3], "big"), ec.SECP256R1()).public_key()
    der = pub.public_bytes(ser.Encoding.DER, ser.PublicFormat.SubjectPublicKeyInfo)
    if any(p["id"] == b64u(cid) for p in d.get("passkeys", [])): raise ValueError("this passkey is already added")
    d.setdefault("passkeys", []).append({"id": b64u(cid), "pub": b64u(der), "count": struct.unpack(">I", ad[33:37])[0], "name": (str(body.get("name") or "Passkey")[:40]), "added": int(now())})
    save(d)


def assert_options(d, host, tk):
    rp, _ = rp_of(host)
    if not rp or not passkeys_available() or not d.get("passkeys"): raise ValueError("no passkey available here")
    ch = b64u(os.urandom(32))
    with LOCK:
        t = TICKETS.get(tk)
        if not t or t["exp"] < now(): raise ValueError("expired, sign in again")
        t["challenge"] = ch
    return {"challenge": ch, "rpId": rp, "timeout": 120000, "userVerification": "required", "allowCredentials": [{"type": "public-key", "id": p["id"]} for p in d["passkeys"]]}


def assert_verify(d, host, tk, body):
    ec, hashes, ser, InvalidSignature = _ec()
    rp, origin = rp_of(host)
    with LOCK:
        t = TICKETS.get(tk)
        if not t or t["exp"] < now() or not t.get("challenge"): raise ValueError("expired, sign in again")
        ch = t["challenge"]; t["challenge"] = ""
    pk = next((p for p in d.get("passkeys", []) if p["id"] == body.get("id")), None)
    if not pk: raise ValueError("unknown passkey")
    cd_raw = _client_check(body["clientDataJSON"], "webauthn.get", ch, origin)
    ad = unb64u(body["authenticatorData"]); _flags_ok(ad, rp)
    pub = ser.load_der_public_key(unb64u(pk["pub"]))
    try: pub.verify(unb64u(body["signature"]), ad + hashlib.sha256(cd_raw).digest(), ec.ECDSA(hashes.SHA256()))
    except InvalidSignature: raise ValueError("bad signature")
    cnt = struct.unpack(">I", ad[33:37])[0]
    if (cnt or pk.get("count")) and cnt <= pk.get("count", 0): raise ValueError("passkey counter went backwards")
    pk["count"] = cnt; save(d)


# ---------- request handling ----------
def state(cookie_hdr, host="", ip="", https=False):
    CTX.ip = ip; CTX.https = https
    d = load() or {}
    rp, _ = rp_of(host)
    if disabled(): return {"state": "authed", "user": "local", "off": True}
    s = session(cookie_hdr)
    if not d.get("pw"): return {"state": "setup"}
    if s: return {"state": "authed", "user": s["user"], "passkeys": [{"id": p["id"], "name": p["name"], "added": p.get("added")} for p in d.get("passkeys", [])],
                  "recovery_left": len(d.get("recovery", [])), "passkey_ok": bool(rp and passkeys_available()), "passkey_host_hint": "" if rp else "Open http://localhost:8765 instead of the IP address to use passkeys.",
                  "idle_min": SESSION_IDLE // 60}
    try: lk = locked()
    except Exception: L.exc(LOG, "locked_check_failed"); lk = 0   # the health check reads this: a database outage must not make the portal look dead
    return {"state": "login", "passkey_ready": bool(d.get("passkeys") and rp and passkeys_available()), "locked": lk}


def handle_post(path, body, cookie_hdr, host, ip="", https=False):
    """-> (status, json, [Set-Cookie values])"""
    CTX.ip = ip; CTX.https = https
    _gc()
    d = load() or {}
    def err(code, msg, **kw): return code, dict({"error": msg}, **kw), []
    authed = session(cookie_hdr)
    try:
        # ---- first run ----
        if path == "/auth/setup/start":
            if d.get("pw"): return err(403, "already set up")
            if locked(): return err(429, f"Too many tries. Wait {locked()} s.")
            code = setup_code()
            if not code or not hmac.compare_digest(code.encode(), str(body.get("code", "")).strip().encode()): fail(); return err(403, "Wrong setup code. It is in the file ~/.config/navaan/auth_setup_code on this computer.")
            user = clean_user(body.get("user")) or "navaan"
            pw = str(body.get("password", "")); prob = pw_problem(pw)
            if prob: return err(400, prob)
            sec = new_secret()
            PENDING.clear(); PENDING.update({"exp": now() + 900, "user": user, "pw": hash_pw(pw), "secret": sec})
            import qr
            uri = otpauth(sec, user)
            return 200, {"secret": sec, "uri": uri, "qr": qr.svg(uri)}, []
        if path == "/auth/setup/finish":
            if d.get("pw"): return err(403, "already set up")
            if not PENDING: return err(400, "Start again.")
            if not totp_check(PENDING["secret"], body.get("code")): fail(); return err(400, "That code is wrong. Check the phone clock and try the next code.")
            codes, hashes = new_recovery()
            nd = {"user": PENDING["user"], "pw": PENDING["pw"], "totp": {"secret": PENDING["secret"], "last": int(now() // 30)}, "recovery": hashes, "passkeys": [], "created": int(now())}
            save(nd); user = PENDING["user"]; PENDING.clear()
            try: os.remove(CODE_FILE)
            except OSError as _e: L.ignored(LOG, "handle_post: OSError (optional or expected)", _e); pass
            ok_reset(); _audit("owner_setup", user)
            return 200, {"ok": True, "recovery": codes}, [cookie_header(start_session(user))]
        if not d.get("pw"): return err(403, "not set up")
        # ---- sign in ----
        if path == "/auth/login":
            if locked(): return err(429, f"Too many tries. Wait {locked()} s.", locked=locked())
            if hmac.compare_digest(user_key(body.get("user")).encode(), user_key(d["user"]).encode()) & check_pw(str(body.get("password", "")), d["pw"]):
                tk = secrets.token_urlsafe(24)
                with LOCK: TICKETS[tk] = {"exp": now() + TICKET_TTL, "user": d["user"], "tries": 0, "challenge": "", "kind": "login"}
                return 200, {"ticket": tk, "passkeys": bool(d.get("passkeys"))}, []
            fail(); return err(401, "Wrong user or password.")
        if path == "/auth/mfa":
            if locked(): return err(429, f"Too many tries. Wait {locked()} s.", locked=locked())
            with LOCK:
                t = TICKETS.get(body.get("ticket", ""))
                if not t or t["exp"] < now() or t.get("kind") != "login": return err(401, "Session expired. Sign in again.")
                t["tries"] += 1
                if t["tries"] > 6: TICKETS.pop(body.get("ticket"), None); return err(401, "Too many wrong codes. Sign in again.")
            code = str(body.get("code", ""))
            step = totp_check(d["totp"]["secret"], code, d["totp"].get("last", 0))
            method = "totp"
            if step: d["totp"]["last"] = step; save(d)
            elif re.search(r"[a-f]|-", code.lower()) and use_recovery(d, code): save(d); method = "recovery_code"
            else: fail(); return err(401, "Wrong code.")
            with LOCK: TICKETS.pop(body["ticket"], None)
            ok_reset(); _audit("login_method", d["user"], method=method)
            return 200, {"ok": True, "recovery_left": len(d.get("recovery", []))}, [cookie_header(start_session(d["user"]))]
        if path == "/auth/passkey/begin":  # sign in with a passkey alone: it proves who you are (device + Touch ID or PIN), so no password or code
            if locked(): return err(429, f"Too many tries. Wait {locked()} s.", locked=locked())
            if not d.get("passkeys"): return err(400, "no passkey is set up")
            if len(TICKETS) > 500: return err(429, "busy, try again in a minute")
            tk = secrets.token_urlsafe(24)
            with LOCK: TICKETS[tk] = {"exp": now() + TICKET_TTL, "user": d["user"], "tries": 0, "challenge": "", "kind": "login"}
            return 200, dict(assert_options(d, host, tk), ticket=tk), []
        if path == "/auth/passkey/login-options":
            return 200, assert_options(d, host, body.get("ticket", "")), []
        if path == "/auth/passkey/login":
            if locked(): return err(429, f"Too many tries. Wait {locked()} s.", locked=locked())
            try: assert_verify(d, host, body.get("ticket", ""), body)
            except Exception as e: L.event(LOG, "warning", "passkey_failed", reason=str(e)[:100]); fail(); return err(401, "Passkey failed: " + str(e)[:100])
            with LOCK: TICKETS.pop(body.get("ticket", ""), None)
            ok_reset(); _audit("login_method", d["user"], method="passkey")
            return 200, {"ok": True}, [cookie_header(start_session(d["user"]))]
        # ---- everything below needs a session ----
        if not authed: return err(401, "sign in")
        if path == "/auth/logout":
            end_session(cookie_hdr); _audit("logout", authed.get("user")); return 200, {"ok": True}, [cookie_header("", clear=True)]
        if path == "/auth/passkey/register-options": return 200, reg_options(d, host, d["user"]), []
        if path == "/auth/passkey/register":
            reg_verify(d, host, body); _audit("passkey_added", authed.get("user")); return 200, {"ok": True}, []
        if path == "/auth/passkey/remove":
            before = len(d.get("passkeys", []))
            d["passkeys"] = [p for p in d.get("passkeys", []) if p["id"] != body.get("id")]
            if len(d["passkeys"]) != before: save(d); _audit("passkey_removed", authed.get("user"))
            return 200, {"ok": True}, []
        if path in ("/auth/password", "/auth/recovery"):
            if locked(): return err(429, f"Too many tries. Wait {locked()} s.")
            if not check_pw(str(body.get("password", "")), d["pw"]): fail(); return err(401, "Wrong current password.")
            ok_reset()
            if path == "/auth/password":
                new = str(body.get("new", "")); prob = pw_problem(new)
                if prob: return err(400, prob)
                d["pw"] = hash_pw(new); save(d)
                gone = CS.revoke_others(authed["user_id"], skey(token_from(cookie_hdr)))  # other sessions are signed out
                _audit("password_changed", authed.get("user"), other_sessions_ended=gone)
                return 200, {"ok": True}, []
            codes, hashes = new_recovery(); d["recovery"] = hashes; save(d); _audit("recovery_codes_renewed", authed.get("user"))
            return 200, {"ok": True, "recovery": codes}, []
        return err(404, "unknown")
    except ValueError as e: L.ignored(LOG, "handle_post: ValueError (optional or expected)", e); return err(400, str(e))
    except KeyError as _e: L.ignored(LOG, "handle_post: KeyError (optional or expected)", _e); return err(400, "missing field")


def main(a):
    if not a or a[0] in ("-h", "--help"): print(__doc__); return 0
    if a[0] == "status":
        d = load() or {}
        print("login:", "set up" if d.get("pw") else "not set up", "| user:", d.get("user", "-"), "| passkeys:", len(d.get("passkeys", [])), "| recovery codes left:", len(d.get("recovery", [])), "| file:", FILE)
        return 0
    if a[0] == "setup-code":
        if configured(): print("login is already set up; use `reset` first if you lost access"); return 1
        ensure_setup_code(); print(setup_code()); return 0
    if a[0] == "reset":
        for f in (FILE, sess_file()):  # the login and every remembered session
            try: os.remove(f)
            except OSError as _e: L.ignored(LOG, "main: OSError (optional or expected)", _e); pass
        try: CS.revoke_all()
        except Exception as e: print("note: could not end the sessions in the database:", e)
        print("login removed. The next portal start asks for a new setup code; restart the portal."); return 0
    print(__doc__); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
