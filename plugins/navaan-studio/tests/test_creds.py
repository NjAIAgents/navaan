"""Pasting a new Claude token or Google token file in the portal, and the alerts that ask for it. Run: python3 -W ignore -m unittest test_creds"""
import json, os, stat, sys, tempfile, textwrap, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import settings_api as S
import navaan_common as C

GOOD = "sk-ant-oat01-" + "a" * 40
APIK = "sk-ant-api03-" + "b" * 40


class Claude(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.home = S.HOME; S.HOME = self.tmp.name
        # a fake `claude -p`: answers OK only for the one token it knows
        fake = os.path.join(self.tmp.name, "fakeclaude")
        open(fake, "w").write(textwrap.dedent(f"""#!/bin/sh
            if [ "$CLAUDE_CODE_OAUTH_TOKEN" = "{GOOD}" ] || [ "$ANTHROPIC_API_KEY" = "{APIK}" ]; then echo OK; else echo "401 unauthorized: token expired" >&2; exit 1; fi
            """)); os.chmod(fake, 0o755)
        self.old = {k: os.environ.get(k) for k in ("NAVAAN_CLAUDE_CMD", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "HOME")}
        os.environ["NAVAAN_CLAUDE_CMD"] = fake; os.environ.pop("ANTHROPIC_API_KEY", None); os.environ.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        self.cf = os.path.join(self.tmp.name, "claude.env")
        self.home_env = C.os.path.expanduser; 
        C.CLAUDE_STATE.update(problem="", at=0)

    def tearDown(self):
        S.HOME = self.home
        for k, v in self.old.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        self.tmp.cleanup()

    def test_rejects_things_that_are_not_tokens(self):
        for bad in ("", "hello", "sk-ant-short", GOOD + " extra words", "Bearer abc"):
            with self.assertRaises(ValueError): S.claude_save(bad)
        self.assertFalse(os.path.exists(self.cf))

    def test_good_token_is_saved_private_and_used(self):
        r = S.claude_save(GOOD)
        self.assertTrue(r["ok"]); self.assertEqual(open(self.cf).read(), f"CLAUDE_CODE_OAUTH_TOKEN={GOOD}\n")
        self.assertEqual(stat.S_IMODE(os.stat(self.cf).st_mode), 0o600)
        self.assertEqual(r["credential"], "subscription token")
        self.assertNotIn(GOOD, json.dumps(r))

    def test_pasted_env_line_and_quotes_work(self):
        S.claude_save(f'CLAUDE_CODE_OAUTH_TOKEN="{GOOD}"')
        self.assertIn(GOOD, open(self.cf).read())

    def test_api_key_goes_to_its_own_variable_and_replaces_the_token(self):
        S.claude_save(GOOD); r = S.claude_save(APIK)
        self.assertEqual(open(self.cf).read(), f"ANTHROPIC_API_KEY={APIK}\n"); self.assertEqual(r["credential"], "API key")
        self.assertNotIn("CLAUDE_CODE_OAUTH_TOKEN", os.environ)

    def test_a_refused_token_never_replaces_a_working_one(self):
        S.claude_save(GOOD); before = open(self.cf).read()
        with self.assertRaises(ValueError) as e: S.claude_save("sk-ant-oat01-" + "z" * 40)
        self.assertIn("expired", str(e.exception)); self.assertNotIn("z" * 40, str(e.exception))
        self.assertEqual(open(self.cf).read(), before)


class Youtube(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.path = os.path.join(self.tmp.name, "youtube_token.json")
        self.o = (S._yt_path, S._yt_status); S._yt_path = lambda ctype: self.path
        self.ok = True; S._yt_status = lambda p: {"ok": True, "channel": "NAVAAN"} if self.ok else {"ok": False, "error": "sign in again (refresh token expired or revoked)"}
        open(self.path, "w").write('{"old": true}')
        self.good = json.dumps({"refresh_token": "r", "client_id": "c", "client_secret": "s", "token": "t"})

    def tearDown(self): S._yt_path, S._yt_status = self.o; self.tmp.cleanup()

    def test_garbage_and_incomplete_files_are_refused(self):
        for bad in ("", "not json", "[1,2]", '{"refresh_token": "r"}', "{" * 30000):
            with self.assertRaises(ValueError): S.yt_save("music", "publish", bad)
        self.assertEqual(open(self.path).read(), '{"old": true}')

    def test_valid_token_replaces_the_old_one(self):
        r = S.yt_save("music", "publish", self.good)
        self.assertEqual(r, {"ok": True, "channel": "NAVAAN"}); self.assertIn("refresh_token", open(self.path).read())
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600); self.assertFalse(os.path.exists(self.path + ".check"))

    def test_expired_token_is_refused_and_the_old_file_stays(self):
        self.ok = False
        with self.assertRaises(ValueError) as e: S.yt_save("music", "publish", self.good)
        self.assertIn("Sign in again", str(e.exception))
        self.assertEqual(open(self.path).read(), '{"old": true}'); self.assertFalse(os.path.exists(self.path + ".check"))

    def test_unknown_kind(self):
        with self.assertRaises(ValueError): S.yt_save("music", "other", self.good)


class YoutubeBrowserSignIn(unittest.TestCase):
    """Sign in from the person's own browser: a link out, the localhost address pasted back."""
    class FakeFlow:
        calls = []
        def __init__(self): self.credentials = type("C", (), {"to_json": lambda c: json.dumps({"refresh_token": "r", "client_id": "c", "client_secret": "s", "token": "t"})})()
        @classmethod
        def from_client_secrets_file(cls, path, scopes=None, redirect_uri=None):
            f = cls(); f.scopes, f.redirect_uri = scopes, redirect_uri; cls.calls.append((path, scopes, redirect_uri)); return f
        def authorization_url(self, **kw): self.kw = kw; return "https://accounts.google.com/o/oauth2/auth?x=1&state=ST1", "ST1"
        def fetch_token(self, code=None): self.code = code

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.home = S.HOME; S.HOME = self.tmp.name
        open(os.path.join(self.tmp.name, "youtube_client_secret.json"), "w").write("{}")
        self.o = (S._flow_cls, S.yt_save, S._yt_scopes); S._flow_cls = lambda: self.FakeFlow; self.saved = []
        S.yt_save = lambda ct, w, text: self.saved.append((ct, w, json.loads(text))) or {"ok": True, "channel": "NAVAAN"}
        S._yt_scopes = lambda w: ["scope-" + w]; S.YT_FLOWS.clear()

    def tearDown(self): S.HOME = self.home; S._flow_cls, S.yt_save, S._yt_scopes = self.o; self.tmp.cleanup()

    def test_start_returns_the_link_and_asks_for_a_long_lived_token(self):
        r = S.yt_oauth_start("music", "publish")
        self.assertTrue(r["url"].startswith("https://accounts.google.com/"))
        f = S.YT_FLOWS["ST1"]["flow"]
        self.assertEqual((f.redirect_uri, f.scopes, f.kw["access_type"], f.kw["prompt"]), (S.YT_REDIRECT, ["scope-publish"], "offline", "consent"))

    def test_finish_exchanges_the_code_and_saves(self):
        S.yt_oauth_start("music", "publish")
        r = S.yt_oauth_finish("music", "publish", "http://localhost:51234/?state=ST1&code=4%2Fabc&scope=x")
        self.assertEqual(r["channel"], "NAVAAN"); self.assertEqual(self.saved[0][:2], ("music", "publish"))
        self.assertNotIn("ST1", S.YT_FLOWS)  # single use

    def test_wrong_state_other_account_expired_and_garbage_are_refused(self):
        S.yt_oauth_start("music", "publish")
        for url in ("", "nonsense", "http://localhost:51234/?code=abc", "http://localhost:51234/?state=OTHER&code=abc", "http://localhost:51234/?error=access_denied&state=ST1"):
            with self.assertRaises(ValueError): S.yt_oauth_finish("music", "publish", url)
        with self.assertRaises(ValueError): S.yt_oauth_finish("inspiration", "publish", "http://localhost:51234/?state=ST1&code=abc")
        self.assertIn("ST1", S.YT_FLOWS)  # a wrong attempt does not use up the real one
        S.YT_FLOWS["ST1"]["exp"] = 0
        with self.assertRaises(ValueError): S.yt_oauth_finish("music", "publish", "http://localhost:51234/?state=ST1&code=abc")
        self.assertEqual(self.saved, [])

    def test_missing_client_file(self):
        os.remove(os.path.join(self.tmp.name, "youtube_client_secret.json"))
        with self.assertRaises(ValueError): S.yt_oauth_start("music", "publish")


class Alerts(unittest.TestCase):
    def setUp(self):
        self.o = (S.claude_status, S.status)
        S.claude_status = lambda: {"credential": "subscription token", "state": "ok"}
        S.status = lambda force=False: {"accounts": [{"type": "music", "yt_token": "/home/navaan/.config/navaan/youtube_token.json", "yt": {"present": True, "ok": True},
                                                      "yt_analytics": {"present": True, "ok": True}, "ig": {"present": True, "ok": True, "days_left": 40}, "market": {"present": False}}]}

    def tearDown(self): S.claude_status, S.status = self.o

    def test_nothing_to_say_when_all_is_fine(self): self.assertEqual(S.alerts(), [])

    def test_expired_claude_token(self):
        S.claude_status = lambda: {"credential": "subscription token", "state": "expired"}
        a = S.alerts(); self.assertEqual(a[0]["id"], "claude"); self.assertEqual(a[0]["command"], "claude setup-token")

    def test_rate_limited_is_not_a_credential_problem(self):
        S.claude_status = lambda: {"credential": "subscription token", "state": "rate_limited"}
        self.assertEqual(S.alerts(), [])

    def test_expired_youtube_gets_the_sign_in_command_and_the_file_to_copy(self):
        d = S.status(); d["accounts"][0]["yt"] = {"present": True, "ok": False, "error": "sign in again (refresh token expired or revoked)"}
        S.status = lambda force=False: d
        a = S.alerts()[0]
        self.assertEqual((a["id"], a["kind"], a["which"]), ("yt:music:publish", "yt", "publish"))
        self.assertIn("publish_youtube.py auth", a["command"]); self.assertIn("youtube_token.json", a["where"])

    def test_other_account_command_names_its_token_file(self):
        d = S.status(); acc = dict(d["accounts"][0], type="inspiration", yt_token="/x/youtube_token_inspiration.json", yt={"present": True, "ok": False})
        S.status = lambda force=False: {"accounts": [acc]}
        self.assertIn("NAVAAN_YT_TOKEN=~/.config/navaan/youtube_token_inspiration.json", S.alerts()[0]["command"])

    def test_instagram_token_close_to_expiry(self):
        d = S.status(); d["accounts"][0]["ig"]["days_left"] = 6
        S.status = lambda force=False: d
        a = S.alerts()[0]; self.assertEqual((a["kind"], a["id"]), ("ig", "ig:music:login")); self.assertIn("6 days", a["title"])


if __name__ == "__main__":
    unittest.main()
