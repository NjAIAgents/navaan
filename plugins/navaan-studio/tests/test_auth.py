"""Tests for the portal login (auth.py): setup code, password plus TOTP, replay, recovery code, per-IP throttle, cookie flags, expiry.
Run: python3 -W ignore -m unittest test_auth   (from this folder)"""
import os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import auth, core_store as CS

PW = "correct horse battery"
H = "localhost:8765"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        auth.DIR = self.tmp.name
        auth.FILE = os.path.join(self.tmp.name, "auth.json")
        auth.CODE_FILE = os.path.join(self.tmp.name, "auth_setup_code")
        os.environ["NAVAAN_SESSIONS_DIR"] = self.tmp.name; auth._LEGACY_DONE = False
        CS._LOCAL.conn = None   # sessions, attempts and the audit trail are in Postgres: this folder is under the temp directory, so it gets its own throwaway schema
        for m in (auth.TICKETS, auth.PENDING): m.clear()
        os.environ.pop("NAVAAN_AUTH", None)

    def tearDown(self):
        os.environ.pop("NAVAAN_SESSIONS_DIR", None)
        if getattr(CS._LOCAL, "conn", None): CS._LOCAL.conn.close(); CS._LOCAL.conn = None
        self.tmp.cleanup()

    def restart(self):
        """What a portal restart does to memory: tickets and a setup in progress are gone; sessions and sign-in attempts are in Postgres and stay."""
        for m in (auth.TICKETS, auth.PENDING): m.clear()
        auth._LEGACY_DONE = False

    def sql(self, q, params=()):
        return CS._run(lambda c: c.execute(q, params).fetchall() if q.lstrip().upper().startswith("SELECT") else c.execute(q, params).rowcount)

    def post(self, path, body, ck=None, ip="1.1.1.1", https=False):
        return auth.handle_post(path, body, ck, H, ip=ip, https=https)

    def setup_login(self, ip="1.1.1.1", https=False):
        """Run first-time setup. Returns (cookie header, totp secret, recovery codes)."""
        auth.ensure_setup_code()
        c, j, _ = self.post("/auth/setup/start", {"code": auth.setup_code(), "user": "nj", "password": PW}, ip=ip, https=https)
        self.assertEqual(c, 200, j)
        sec = j["secret"]
        c, j, ck = self.post("/auth/setup/finish", {"code": auth.totp(sec, int(auth.now() // 30))}, ip=ip, https=https)
        self.assertEqual(c, 200, j)
        return ck[0].split(";")[0], sec, j["recovery"]

    def login(self, code, ip="1.1.1.1", https=False):
        c, j, _ = self.post("/auth/login", {"user": "nj", "password": PW}, ip=ip, https=https)
        self.assertEqual(c, 200, j)
        return self.post("/auth/mfa", {"ticket": j["ticket"], "code": code}, ip=ip, https=https)


class Setup(Base):
    def test_wrong_setup_code(self):
        auth.ensure_setup_code()
        c, _, _ = self.post("/auth/setup/start", {"code": "0000-0000-0000", "user": "nj", "password": PW})
        self.assertEqual(c, 403)

    def test_weak_password(self):
        auth.ensure_setup_code()
        c, _, _ = self.post("/auth/setup/start", {"code": auth.setup_code(), "user": "nj", "password": "short"})
        self.assertEqual(c, 400)

    def test_setup_signs_in_and_removes_code(self):
        ck, _, rec = self.setup_login()
        self.assertTrue(auth.configured())
        self.assertFalse(os.path.exists(auth.CODE_FILE))
        self.assertEqual(len(rec), 10)
        self.assertEqual(auth.state(ck, H)["state"], "authed")

    def test_no_second_setup(self):
        self.setup_login()
        c, _, _ = self.post("/auth/setup/start", {"code": "x", "user": "nj", "password": PW})
        self.assertEqual(c, 403)

    def test_login_file_mode(self):
        self.setup_login()
        self.assertEqual(os.stat(auth.FILE).st_mode & 0o777, 0o600)


class SignIn(Base):
    def test_password_then_totp(self):
        _, sec, _ = self.setup_login()
        step = int(auth.now() // 30) + 1  # next window: setup already used the current one
        c, j, ck = self.login(auth.totp(sec, step))
        self.assertEqual(c, 200, j)
        self.assertEqual(auth.state(ck[0].split(";")[0], H)["state"], "authed")

    def test_totp_replay_refused(self):
        _, sec, _ = self.setup_login()
        code = auth.totp(sec, int(auth.now() // 30) + 1)
        self.assertEqual(self.login(code)[0], 200)
        self.assertEqual(self.login(code)[0], 401)

    def test_wrong_password(self):
        self.setup_login()
        c, _, _ = self.post("/auth/login", {"user": "nj", "password": "wrong wrong wrong"})
        self.assertEqual(c, 401)

    def test_recovery_code_once(self):
        _, _, rec = self.setup_login()
        self.assertEqual(self.login(rec[0])[0], 200)
        self.assertEqual(self.login(rec[0])[0], 401)

    def test_not_signed_in(self):
        self.setup_login()
        self.assertEqual(auth.state(None, H)["state"], "login")
        self.assertIsNone(auth.session(None))

    def test_logout(self):
        ck, _, _ = self.setup_login()
        c, _, _ = self.post("/auth/logout", {}, ck=ck)
        self.assertEqual(c, 200)
        self.assertIsNone(auth.session(ck))


class Throttle(Base):
    def test_lockout_is_per_ip(self):
        self.setup_login()
        for _ in range(5): self.post("/auth/login", {"user": "nj", "password": "wrong wrong wrong"}, ip="9.9.9.9")
        c, j, _ = self.post("/auth/login", {"user": "nj", "password": PW}, ip="9.9.9.9")
        self.assertEqual(c, 429, j)
        c, _, _ = self.post("/auth/login", {"user": "nj", "password": PW}, ip="2.2.2.2")  # a stranger cannot lock out the owner
        self.assertEqual(c, 200)

    def test_state_reports_lock(self):
        self.setup_login()
        for _ in range(5): self.post("/auth/login", {"user": "nj", "password": "wrong wrong wrong"}, ip="9.9.9.9")
        self.assertGreater(auth.state(None, H, ip="9.9.9.9")["locked"], 0)
        self.assertEqual(auth.state(None, H, ip="2.2.2.2")["locked"], 0)


class Cookies(Base):
    def test_flags_plain_http(self):
        h = auth.cookie_header("tok")
        self.assertIn("HttpOnly", h); self.assertIn("SameSite=Strict", h); self.assertNotIn("Secure", h)

    def test_secure_under_https(self):
        auth.state(None, H, https=True)
        self.assertIn("; Secure", auth.cookie_header("tok"))
        self.assertIn("; Secure", auth.cookie_header("", clear=True))

    def test_setup_cookie_secure_under_https(self):
        auth.ensure_setup_code()
        c, j, _ = self.post("/auth/setup/start", {"code": auth.setup_code(), "user": "nj", "password": PW}, https=True)
        _, _, ck = self.post("/auth/setup/finish", {"code": auth.totp(j["secret"], int(auth.now() // 30))}, https=True)
        self.assertIn("; Secure", ck[0])

    def test_passkey_origin_follows_scheme(self):
        auth.CTX.https = True
        self.assertEqual(auth.rp_of("navaan.njlabs.dev"), ("navaan.njlabs.dev", "https://navaan.njlabs.dev"))
        auth.CTX.https = False
        self.assertEqual(auth.rp_of("localhost:8765"), ("localhost", "http://localhost:8765"))


class Expiry(Base):
    def test_seven_day_limit(self):
        ck, _, _ = self.setup_login()
        self.sql("UPDATE sessions SET expires_at = now() - interval '1 second' WHERE token_hash = ?", (auth.skey(auth.token_from(ck)),))
        self.assertIsNone(auth.session(ck))

    def test_idle_limit(self):
        ck, _, _ = self.setup_login()
        self.sql("UPDATE sessions SET last_seen_at = now() - (? * interval '1 second') WHERE token_hash = ?", (auth.SESSION_IDLE + 1, auth.skey(auth.token_from(ck))))
        self.assertIsNone(auth.session(ck))

    def test_activity_keeps_session(self):
        ck, _, _ = self.setup_login()
        self.sql("UPDATE sessions SET last_seen_at = now() - (? * interval '1 second') WHERE token_hash = ?", (auth.SESSION_IDLE - 60, auth.skey(auth.token_from(ck))))
        self.assertIsNotNone(auth.session(ck))
        self.assertEqual(self.sql("SELECT last_seen_at > now() - interval '1 minute' AS fresh FROM sessions")[0]["fresh"], True)   # and the idle clock restarted


class Remembered(Base):
    def test_session_survives_restart(self):
        ck, _, _ = self.setup_login()
        self.restart()
        self.assertEqual(auth.state(ck, H)["state"], "authed")

    def test_database_holds_hashes_not_tokens(self):
        ck, _, _ = self.setup_login()
        rows = self.sql("SELECT * FROM sessions")
        self.assertEqual(len(rows), 1)
        self.assertNotIn(auth.token_from(ck), " ".join(str(v) for v in rows[0].values()))
        self.assertEqual(rows[0]["token_hash"], auth.skey(auth.token_from(ck)))

    def test_logout_is_forgotten_after_restart(self):
        ck, _, _ = self.setup_login()
        self.post("/auth/logout", {}, ck=ck); self.restart()
        self.assertIsNone(auth.session(ck))

    def test_expired_session_not_restored(self):
        ck, _, _ = self.setup_login()
        self.sql("UPDATE sessions SET expires_at = now() - interval '1 second'")
        self.restart()
        self.assertIsNone(auth.session(ck))

    def test_password_change_signs_out_other_sessions_even_after_restart(self):
        ck, sec, _ = self.setup_login()
        c, j, ck2 = self.login(auth.totp(sec, int(auth.now() // 30) + 1))
        ck2 = ck2[0].split(";")[0]
        self.post("/auth/password", {"password": PW, "new": "another long password 1"}, ck=ck2)
        self.restart()
        self.assertIsNone(auth.session(ck)); self.assertIsNotNone(auth.session(ck2))

    def test_cookie_lasts_a_week(self):
        self.assertIn("Max-Age=604800", auth.cookie_header("tok"))

    def test_the_older_sessions_json_is_taken_in_once_and_moved_aside(self):
        import json, time
        tok = "legacy-token-123"; now = time.time()
        with open(auth.sess_file(), "w") as f: json.dump({auth.skey(tok): {"created": now - 100, "last": now - 50, "user": "nj"}, "deadbeef": {"created": now - 99999999, "last": now - 99999999, "user": "nj"}}, f)
        ck = f"{auth.COOKIE}={tok}"
        s = auth.session(ck)
        self.assertEqual((s["user"], s["roles"]), ("nj", ["owner"])); self.assertTrue(s["csrf"])
        self.assertFalse(os.path.exists(auth.sess_file())); self.assertTrue(os.path.exists(auth.sess_file() + ".imported"))
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM sessions")[0]["n"], 1)   # the expired one was not imported


class Core(Base):
    """Roles, permissions, a CSRF token per session, the audit trail, attempts in the database (NAV-5 stage 1)."""
    def test_a_signed_in_owner_has_the_owner_role_and_the_studio_permissions(self):
        ck, _, _ = self.setup_login()
        s = auth.session(ck)
        self.assertEqual(s["roles"], ["owner"]); self.assertTrue(auth.can(s, "studio.access")); self.assertTrue(auth.can(s, "studio.approve"))
        self.assertFalse(auth.can(None, "studio.access")); self.assertFalse(auth.can(s, "nonsense"))

    def test_every_session_has_its_own_csrf_token(self):
        ck, sec, _ = self.setup_login()
        c, j, ck2 = self.login(auth.totp(sec, int(auth.now() // 30) + 1)); ck2 = ck2[0].split(";")[0]
        a, b = auth.session(ck)["csrf"], auth.session(ck2)["csrf"]
        self.assertTrue(a and b and a != b)

    def test_a_listener_has_no_studio_permission(self):
        u = CS.ensure_user("listener1", role="listener")
        tok = "listener-token"; CS.create_session(auth.skey(tok), u["id"], "csrf-l", "9.9.9.9", None, 3600)
        s = auth.session(f"{auth.COOKIE}={tok}")
        self.assertEqual(s["roles"], ["listener"]); self.assertFalse(auth.can(s, "studio.access")); self.assertTrue(auth.can(s, "library.view"))

    def test_a_disabled_person_cannot_use_a_session(self):
        u = CS.ensure_user("gone", role="listener"); tok = "gone-token"; CS.create_session(auth.skey(tok), u["id"], "c", None, None, 3600)
        self.assertIsNotNone(auth.session(f"{auth.COOKIE}={tok}"))
        self.sql("UPDATE users SET status = 'disabled' WHERE username = 'gone'")
        self.assertIsNone(auth.session(f"{auth.COOKIE}={tok}"))

    def test_sign_ins_and_failures_reach_the_audit_trail_without_secrets(self):
        ck, sec, _ = self.setup_login()
        self.login("000000"); self.post("/auth/logout", {}, ck=ck)
        actions = [r["action"] for r in self.sql("SELECT action FROM audit_log ORDER BY id")]
        for a in ("user_created", "owner_setup", "login", "login_failed", "logout"): self.assertIn(a, actions)
        blob = " ".join(str(r["detail"]) + str(r["subject"]) for r in self.sql("SELECT subject, detail FROM audit_log"))
        for secret in (PW, sec): self.assertNotIn(secret, blob)

    def test_a_lockout_survives_a_restart(self):
        self.setup_login()
        for _ in range(5): self.post("/auth/login", {"user": "nj", "password": "wrong"}, ip="7.7.7.7")
        self.restart()
        c, j, _ = self.post("/auth/login", {"user": "nj", "password": PW}, ip="7.7.7.7")
        self.assertEqual(c, 429); self.assertGreater(j["locked"], 0)
        self.assertEqual(self.post("/auth/login", {"user": "nj", "password": PW}, ip="8.8.8.8")[0], 200)   # another address is not locked out

    def test_the_health_check_state_survives_a_database_outage(self):
        self.setup_login()
        with mock.patch.object(CS, "failures", side_effect=RuntimeError("database down")):
            self.assertEqual(auth.state(None, H)["state"], "login")
        with mock.patch.object(CS, "get_session", side_effect=RuntimeError("database down")):
            self.assertIsNone(auth.session(f"{auth.COOKIE}=whatever"))   # closed, not open


class UserName(Base):
    def test_email_is_stored_as_typed_and_works_at_sign_in(self):
        auth.ensure_setup_code()
        c, j, _ = self.post("/auth/setup/start", {"code": auth.setup_code(), "user": "me.name@gmail.com", "password": PW})
        self.assertEqual(c, 200, j)
        self.post("/auth/setup/finish", {"code": auth.totp(j["secret"], int(auth.now() // 30))})
        self.assertEqual(auth.load()["user"], "me.name@gmail.com")
        for typed in ("me.name@gmail.com", "ME.name@gmail.com", "me.namegmail.com", "  me.name@gmail.com "):
            self.assertEqual(self.post("/auth/login", {"user": typed, "password": PW})[0], 200, typed)
        self.assertEqual(self.post("/auth/login", {"user": "someone.else@gmail.com", "password": PW})[0], 401)

    def test_older_login_stored_without_the_at_sign_still_accepts_the_email(self):
        self.setup_login()
        d = auth.load(); d["user"] = "me.namegmail.com"; auth.save(d)
        self.assertEqual(self.post("/auth/login", {"user": "me.name@gmail.com", "password": PW})[0], 200)


class PasskeyOnly(Base):
    def setUp(self):
        super().setUp()
        if not auth.passkeys_available(): self.skipTest("cryptography is not installed")
        import hashlib
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        self.ec, self.hashlib = ec, hashlib
        self.priv = ec.generate_private_key(ec.SECP256R1())
        self.der = self.priv.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)

    def add_key(self):
        self.setup_login()
        d = auth.load(); d["passkeys"] = [{"id": auth.b64u(b"cred-1"), "pub": auth.b64u(self.der), "count": 0, "name": "t", "added": 1}]; auth.save(d)

    def assertion(self, o, count=1, flags=0x05, origin="http://localhost:8765"):
        import json
        cd = json.dumps({"type": "webauthn.get", "challenge": o["challenge"], "origin": origin}).encode()
        ad = self.hashlib.sha256(b"localhost").digest() + bytes([flags]) + count.to_bytes(4, "big")
        sig = self.priv.sign(ad + self.hashlib.sha256(cd).digest(), self.ec.ECDSA(__import__("cryptography.hazmat.primitives.hashes", fromlist=["SHA256"]).SHA256()))
        return {"ticket": o["ticket"], "id": auth.b64u(b"cred-1"), "clientDataJSON": auth.b64u(cd), "authenticatorData": auth.b64u(ad), "signature": auth.b64u(sig)}

    def test_no_passkey_no_begin(self):
        self.setup_login()
        self.assertEqual(self.post("/auth/passkey/begin", {})[0], 400)

    def test_passkey_alone_signs_in(self):
        self.add_key()
        c, o, _ = self.post("/auth/passkey/begin", {}); self.assertEqual(c, 200, o)
        c, j, ck = self.post("/auth/passkey/login", self.assertion(o))
        self.assertEqual(c, 200, j)
        self.assertEqual(auth.state(ck[0].split(";")[0], H)["state"], "authed")

    def test_passkey_without_user_verification_is_refused(self):
        self.add_key()
        c, o, _ = self.post("/auth/passkey/begin", {})
        c, j, _ = self.post("/auth/passkey/login", self.assertion(o, flags=0x01))
        self.assertEqual(c, 401)

    def test_wrong_signature_refused_and_ticket_not_reusable(self):
        self.add_key()
        c, o, _ = self.post("/auth/passkey/begin", {})
        good = self.assertion(o); bad = dict(good, signature=auth.b64u(b"x" * 70))
        self.assertEqual(self.post("/auth/passkey/login", bad)[0], 401)
        self.assertEqual(self.post("/auth/passkey/login", good)[0], 401)  # the challenge was consumed

    def test_state_offers_passkey_when_one_exists(self):
        self.add_key()
        self.assertTrue(auth.state(None, H)["passkey_ready"])


class Disabled(Base):
    def test_auth_off(self):
        os.environ["NAVAAN_AUTH"] = "off"
        try: self.assertEqual(auth.state(None, H)["state"], "authed")
        finally: os.environ.pop("NAVAAN_AUTH", None)


class Edge(unittest.TestCase):
    """navaan_ui env switches: public host, trusted proxy headers. Defaults keep localhost behaviour."""
    def handler(self, **hdr):
        import navaan_ui
        h = object.__new__(navaan_ui.H)
        h.headers = hdr; h.client_address = ("172.18.0.5", 1234)
        return h

    def setUp(self):
        for k in ("NAVAAN_PUBLIC_HOST", "NAVAAN_TRUST_PROXY"): os.environ.pop(k, None)

    tearDown = setUp

    def test_defaults_localhost_only(self):
        self.assertTrue(self.handler(Host="localhost:8765")._host_ok())
        self.assertFalse(self.handler(Host="navaan.njlabs.dev")._host_ok())

    def test_public_host_allowed_when_set(self):
        os.environ["NAVAAN_PUBLIC_HOST"] = "navaan.njlabs.dev"
        self.assertTrue(self.handler(Host="navaan.njlabs.dev")._host_ok())
        self.assertFalse(self.handler(Host="evil.example")._host_ok())

    def test_proxy_headers_ignored_by_default(self):
        h = self.handler(Host="localhost", **{"X-Real-IP": "8.8.8.8", "X-Forwarded-Proto": "https"})
        self.assertEqual(h._ip(), "172.18.0.5"); self.assertFalse(h._https())

    def test_proxy_headers_trusted_when_set(self):
        os.environ["NAVAAN_TRUST_PROXY"] = "1"
        h = self.handler(Host="localhost", **{"X-Real-IP": "8.8.8.8", "X-Forwarded-Proto": "https"})
        self.assertEqual(h._ip(), "8.8.8.8"); self.assertTrue(h._https())
        self.assertEqual(self.handler(Host="localhost")._ip(), "172.18.0.5")  # no header: fall back to the socket


class SecretsStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.f = os.path.join(self.tmp.name, "secrets.status")
        os.environ["NAVAAN_SECRETS_STATUS"] = self.f; os.environ.pop("NAVAAN_VAULT_ADDR", None)

    def tearDown(self):
        os.environ.pop("NAVAAN_SECRETS_STATUS", None); os.environ.pop("NAVAAN_VAULT_ADDR", None); self.tmp.cleanup()

    def test_no_vault_no_file_is_none(self):
        import navaan_ui
        self.assertIsNone(navaan_ui.secrets_status())

    def test_vault_configured_but_no_file_is_waiting(self):
        import navaan_ui
        os.environ["NAVAAN_VAULT_ADDR"] = "http://vault:8200"
        self.assertEqual(navaan_ui.secrets_status()["status"], "waiting")

    def test_ok_and_stale(self):
        import navaan_ui, json, time
        json.dump({"status": "ok", "detail": "", "at": int(time.time())}, open(self.f, "w"))
        self.assertEqual(navaan_ui.secrets_status()["status"], "ok")
        json.dump({"status": "ok", "detail": "", "at": int(time.time()) - 600}, open(self.f, "w"))
        self.assertEqual(navaan_ui.secrets_status()["status"], "waiting")  # watcher died: do not trust an old ok


    def test_scheduler_states(self):
        import navaan_ui, json, time
        os.environ.pop("NAVAAN_SCHEDULER", None)
        self.assertEqual(navaan_ui.scheduler_state(), "on")
        os.environ["NAVAAN_SCHEDULER"] = "off"
        try: self.assertEqual(navaan_ui.scheduler_state(), "off")
        finally: os.environ.pop("NAVAAN_SCHEDULER", None)
        json.dump({"status": "sealed", "detail": "", "at": int(time.time())}, open(self.f, "w"))
        self.assertEqual(navaan_ui.scheduler_state(), "paused")


if __name__ == "__main__":
    unittest.main()
