"""entitlements.py  what a plan includes and which plan a person is on, behind one question: can(user, feature).

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: NAV-7 (FR-015, SC-008). Screens and endpoints never look at a plan name; they ask can(). What Free and Premium include is data in schema billing, so changing a limit is an update
to a row, not a release. A person with no subscription row starts on Free the first time they are asked about. The owner role is never limited. No payment provider (FR-021).
"""
import datetime
import pgconn
import navaan_log as L
LOG = L.get("entitlements")
_conn, _tx = pgconn.make("billing")
FREE = "free"
LIVE = ("trialing", "active", "past_due")


class Decision:
    """The answer: truthy when allowed. limit and plan say why; message() is what to show a person."""
    def __init__(self, allowed, feature, plan, limit=None, reason=""):
        self.allowed, self.feature, self.plan, self.limit, self.reason = allowed, feature, plan, limit, reason
    def __bool__(self): return self.allowed
    def message(self):
        if self.allowed: return ""
        if self.reason == "limit": return f"Your {self.plan.title()} plan includes {self.limit} {self.feature.split('.')[0]}. A higher plan has more."
        return f"This is not part of your {self.plan.title()} plan."
    def as_dict(self): return {"allowed": self.allowed, "feature": self.feature, "plan": self.plan, "limit": self.limit, "reason": self.reason, "message": self.message()}


def _ensure_live(c, user_id):
    """The person's live subscription row, created on Free if they have none (every new listener starts on Free)."""
    r = c.execute("SELECT s.id, p.key, p.name, s.status FROM subscriptions s JOIN plans p ON p.id = s.plan_id WHERE s.user_id = ?::uuid AND s.status = ANY(?)", (user_id, list(LIVE))).fetchone()
    if r: return r
    c.execute("INSERT INTO subscriptions (user_id, plan_id, status) SELECT ?::uuid, id, 'active' FROM plans WHERE key = ? ON CONFLICT DO NOTHING", (user_id, FREE))
    return c.execute("SELECT s.id, p.key, p.name, s.status FROM subscriptions s JOIN plans p ON p.id = s.plan_id WHERE s.user_id = ?::uuid AND s.status = ANY(?)", (user_id, list(LIVE))).fetchone()


def plan_for(user_id):
    return _tx(lambda c: (lambda r: {"key": r["key"], "name": r["name"], "status": r["status"]})(_ensure_live(c, user_id)))


def entitlements(user_id):
    """{feature: {"enabled", "limit"}} for this person: their plan with their overrides."""
    def go(c):
        _ensure_live(c, user_id)
        return {r["feature"]: {"enabled": r["enabled"], "limit": r["limit_int"], "plan": r["plan"]} for r in c.execute("SELECT plan, feature, enabled, limit_int FROM v_user_entitlements WHERE user_id = ?::uuid", (user_id,)).fetchall()}
    return _tx(go)


def can(user, feature, used=None):
    """May this person use the feature? user is {"user_id", "roles"} (a session). For a limited feature pass used, how many they already have: allowed while used < limit."""
    uid = user["user_id"]; roles = user.get("roles") or []
    if "owner" in roles: return Decision(True, feature, "owner")
    e = entitlements(uid).get(feature); plan = (e or {}).get("plan") or plan_for(uid)["key"]
    if not e or not e["enabled"]: return Decision(False, feature, plan, reason="not_in_plan")
    if e["limit"] is not None and used is not None and used >= e["limit"]: return Decision(False, feature, plan, e["limit"], "limit")
    return Decision(True, feature, plan, e["limit"])


def plans():
    """Every active plan with what it includes, for the Plans page."""
    def go(c):
        out = []
        for p in c.execute("SELECT id, key, name, price_minor, currency, interval FROM plans WHERE active ORDER BY sort").fetchall():
            ents = c.execute("SELECT feature, enabled, limit_int FROM plan_entitlements WHERE plan_id = ? ORDER BY feature", (p["id"],)).fetchall()
            out.append({"key": p["key"], "name": p["name"], "price_minor": p["price_minor"], "currency": p["currency"], "interval": p["interval"],
                        "buyable": False, "entitlements": [{"feature": e["feature"], "enabled": e["enabled"], "limit": e["limit_int"]} for e in ents]})   # no payment provider yet (FR-021)
        return out
    return _tx(go)


def set_entitlement(plan_key, feature, enabled=True, limit=None):
    """Change what a plan includes (the owner's data change, SC-008). Returns False when there is no such plan."""
    if limit is not None and int(limit) < 0: raise ValueError("a limit is zero or more")
    return _tx(lambda c: c.execute("INSERT INTO plan_entitlements (plan_id, feature, enabled, limit_int) SELECT id, ?, ?, ? FROM plans WHERE key = ? "
                                   "ON CONFLICT (plan_id, feature) DO UPDATE SET enabled = excluded.enabled, limit_int = excluded.limit_int RETURNING feature",
                                   (feature, bool(enabled), None if limit is None else int(limit), plan_key)).fetchone()) is not None


def override(user_id, feature, reason, enabled=None, limit=None, expires_at=None):
    """An exception for one person and one feature, with the reason."""
    if not reason or not str(reason).strip(): raise ValueError("say why")
    _tx(lambda c: c.execute("INSERT INTO entitlement_overrides (user_id, feature, enabled, limit_int, reason, expires_at) VALUES (?::uuid, ?, ?, ?, ?, ?) "
                            "ON CONFLICT (user_id, feature) DO UPDATE SET enabled = excluded.enabled, limit_int = excluded.limit_int, reason = excluded.reason, expires_at = excluded.expires_at, created_at = now()",
                            (user_id, feature, enabled, limit, str(reason).strip()[:300], expires_at)))


def switch_plan(user_id, plan_key, status="active"):
    """Put a person on a plan (what a checkout will call once a provider exists). Ends the live subscription, starts the new one."""
    def go(c):
        p = c.execute("SELECT id FROM plans WHERE key = ? AND active", (plan_key,)).fetchone()
        if not p: raise LookupError("no such plan")
        c.execute("UPDATE subscriptions SET status = 'canceled', updated_at = now() WHERE user_id = ?::uuid AND status = ANY(?)", (user_id, list(LIVE)))
        c.execute("INSERT INTO subscriptions (user_id, plan_id, status, period_start) VALUES (?::uuid, ?, ?, now())", (user_id, p["id"], status))
    _tx(go)


def erase(user_id):
    """Remove everything billing holds about a person (account deletion)."""
    def go(c):
        for t in ("subscriptions", "entitlement_overrides"): c.execute(f"DELETE FROM {t} WHERE user_id = ?::uuid", (user_id,))
    _tx(go)


def export(user_id):
    def go(c):
        return {"subscriptions": [{**r, "created_at": r["created_at"].isoformat()} for r in c.execute("SELECT p.key AS plan, s.status, s.created_at FROM subscriptions s JOIN plans p ON p.id = s.plan_id WHERE s.user_id = ?::uuid ORDER BY s.created_at", (user_id,)).fetchall()],
                "overrides": [{"feature": r["feature"], "enabled": r["enabled"], "limit": r["limit_int"], "reason": r["reason"]} for r in c.execute("SELECT feature, enabled, limit_int, reason FROM entitlement_overrides WHERE user_id = ?::uuid", (user_id,)).fetchall()]}
    return _tx(go)
