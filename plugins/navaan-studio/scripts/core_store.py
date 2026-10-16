"""core_store.py  people, roles, sessions, the audit trail and sign-in attempts, in Postgres (schema "core").

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: the database side of auth.py (NAV-5 stage 1): sessions with a per-session CSRF token, roles and permissions, login attempts, the audit log.

Rules
  a session is a row keyed by the sha256 of the cookie value (the token itself is never stored); it ends at expires_at, after idle seconds without a request, or when revoked
  a request touches last_seen_at at most once a minute, so polling does not write on every call
  roles come with permissions (core.role_permissions); a route asks for a permission (auth.can), never for a role name
  the audit log is append-only from the app and holds who, what, when and from where, never a secret
  login_attempts replaces the in-memory throttle: it survives a restart and works for more than one process
"""
import os, json, tempfile, threading
import navaan_log as L
import analytics_db as db
LOG = L.get("core_store")

_LOCAL = threading.local()
import pgconn; pgconn.register(_LOCAL)
TOUCH_EVERY_S = 60


def _jsonb(v):
    from psycopg.types.json import Jsonb
    return Jsonb(v)


def _conn():
    """One connection per thread, reused. A throwaway auth folder (tests) under the system temp directory gets its own throwaway schema."""
    import auth
    root = os.path.realpath(auth.DIR)
    c = getattr(_LOCAL, "conn", None)
    if c is not None and not c.closed and getattr(_LOCAL, "root", None) == root and c.info.transaction_status != 3:
        return c
    if c is not None and not c.closed: c.close()
    tmp = os.path.realpath(tempfile.gettempdir())
    _LOCAL.conn = db.connect(root, base="core", isolate=root.startswith(tmp + os.sep))
    _LOCAL.root = root
    return _LOCAL.conn


def _run(fn):
    """Run fn(connection) in a transaction: commit on success, roll back and re-raise on any error."""
    c = _conn()
    try:
        out = fn(c); c.commit(); return out
    except Exception:
        c.rollback(); raise


# ---- people ----------------------------------------------------------------------------------------------------------------
def ensure_user(username, role="owner", email=None):
    """The users row for this username (created with the role on first sight). Returns {"id", "username"}."""
    def f(c):
        r = c.execute("INSERT INTO users (username, email, display_name) VALUES (?, ?, ?) ON CONFLICT DO NOTHING RETURNING id, username", (username, email.lower() if email else None, username)).fetchone()
        if r:   # first sight: its role and a line in the audit trail (a concurrent first sight loses the insert and just reads the row)
            c.execute("INSERT INTO user_roles (user_id, role_id) SELECT ?::uuid, id FROM roles WHERE name = ?", (r["id"], role))
            c.execute("INSERT INTO audit_log (actor_id, action, subject, detail) VALUES (?, 'user_created', ?, ?)", (r["id"], username, _jsonb({"role": role})))
        else:
            r = c.execute("SELECT id, username FROM users WHERE lower(username) = lower(?)", (username,)).fetchone()
        return {"id": str(r["id"]), "username": r["username"]}
    return _run(f)


# ---- sessions --------------------------------------------------------------------------------------------------------------
def create_session(token_hash, user_id, csrf, ip=None, ua=None, ttl_s=7 * 86400):
    _run(lambda c: c.execute("INSERT INTO sessions (token_hash, user_id, csrf_token, ip, user_agent, expires_at) VALUES (?, ?, ?, ?, ?, now() + (? * interval '1 second'))",
                             (token_hash, user_id, csrf, ip, ua, ttl_s)))


def get_session(token_hash, idle_s=7 * 86400):
    """The live session with its user, roles and permissions, or None. Touches the idle clock at most once a minute."""
    def f(c):
        r = c.execute(
            "SELECT s.user_id, s.csrf_token, s.last_seen_at < now() - (? * interval '1 second') AS stale, u.username, "
            "COALESCE((SELECT array_agg(DISTINCT r.name ORDER BY r.name) FROM user_roles ur JOIN roles r ON r.id = ur.role_id WHERE ur.user_id = u.id), '{}') AS roles, "
            "COALESCE((SELECT array_agg(DISTINCT rp.permission ORDER BY rp.permission) FROM user_roles ur JOIN role_permissions rp ON rp.role_id = ur.role_id WHERE ur.user_id = u.id), '{}') AS perms "
            "FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > now() AND s.last_seen_at > now() - (? * interval '1 second') AND u.status = 'active'",
            (TOUCH_EVERY_S, token_hash, idle_s)).fetchone()
        if not r: return None
        if r["stale"]: c.execute("UPDATE sessions SET last_seen_at = now() WHERE token_hash = ?", (token_hash,))
        return {"user": r["username"], "user_id": str(r["user_id"]), "csrf": r["csrf_token"], "roles": list(r["roles"]), "permissions": list(r["perms"])}
    return _run(f)


def import_session(token_hash, user_id, csrf, created_epoch, last_epoch, ttl_s):
    """A session from the older sessions.json: same hash, so the cookie keeps working."""
    _run(lambda c: c.execute("INSERT INTO sessions (token_hash, user_id, csrf_token, created_at, last_seen_at, expires_at) "
                             "VALUES (?, ?, ?, to_timestamp(?), to_timestamp(?), to_timestamp(?)) ON CONFLICT DO NOTHING", (token_hash, user_id, csrf, created_epoch, last_epoch, created_epoch + ttl_s)))


def revoke_session(token_hash):
    _run(lambda c: c.execute("UPDATE sessions SET revoked_at = now() WHERE token_hash = ? AND revoked_at IS NULL", (token_hash,)))


def revoke_others(user_id, keep_hash):
    """After a password change: every other session of the person ends. Returns how many."""
    return _run(lambda c: c.execute("UPDATE sessions SET revoked_at = now() WHERE user_id = ? AND token_hash <> ? AND revoked_at IS NULL", (user_id, keep_hash)).rowcount)


def revoke_all():
    return _run(lambda c: c.execute("UPDATE sessions SET revoked_at = now() WHERE revoked_at IS NULL").rowcount)


def gc(idle_s=7 * 86400):
    """Sessions that can no longer be used, old sign-in attempts and old audit rows are removed."""
    def f(c):
        a = c.execute("DELETE FROM sessions WHERE expires_at < now() - interval '1 day' OR revoked_at < now() - interval '1 day' OR last_seen_at < now() - (? * interval '1 second') - interval '1 day'", (idle_s,)).rowcount
        c.execute("DELETE FROM login_attempts WHERE at < now() - interval '30 days'")
        c.execute("DELETE FROM audit_log WHERE at < now() - interval '400 days'")
        return a
    return _run(f)


# ---- sign-in attempts ------------------------------------------------------------------------------------------------------
def record_attempt(key, ok):
    _run(lambda c: c.execute("INSERT INTO login_attempts (key, ok) VALUES (?, ?)", (key, bool(ok))))


def failures(key):
    """(failed attempts since the last success within a day, epoch seconds of the latest failure)."""
    def f(c):
        r = c.execute("SELECT COUNT(*) AS n, EXTRACT(EPOCH FROM MAX(at)) AS last FROM login_attempts WHERE key = ? AND NOT ok AND at > now() - interval '1 day' "
                      "AND at > COALESCE((SELECT MAX(at) FROM login_attempts WHERE key = ? AND ok), 'epoch')", (key, key)).fetchone()
        return int(r["n"]), float(r["last"] or 0)
    return _run(f)


# ---- audit -----------------------------------------------------------------------------------------------------------------
def audit(action, actor_id=None, subject=None, ip=None, detail=None):
    _run(lambda c: c.execute("INSERT INTO audit_log (actor_id, action, subject, ip, detail) VALUES (?, ?, ?, ?, ?)", (actor_id, action, subject, ip, _jsonb(detail or {}))))


def delete_user(user_id):
    """Remove a person: their credentials, sessions, roles and profile go with the row (cascade); the audit trail keeps a line without the link to them. Returns the username, or None."""
    def f(c):
        r = c.execute("SELECT username FROM users WHERE id = ?::uuid", (user_id,)).fetchone()
        if not r: return None
        c.execute("INSERT INTO audit_log (actor_id, action, subject, detail) VALUES (NULL, 'user_deleted', ?, ?)", (r["username"], _jsonb({})))
        c.execute("DELETE FROM users WHERE id = ?::uuid", (user_id,))
        return r["username"]
    return _run(f)


def user_summary(user_id):
    """{"username", "email", "created_at"} for the account export, or None."""
    r = _run(lambda c: c.execute("SELECT username, email, created_at FROM users WHERE id = ?::uuid", (user_id,)).fetchone())
    return {"username": r["username"], "email": r["email"], "created_at": r["created_at"].isoformat()} if r else None
