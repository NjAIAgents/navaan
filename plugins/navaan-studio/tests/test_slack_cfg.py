"""NAV-151: connecting Slack with OAuth v2. Every call to Slack goes through a fake HTTP, so nothing here reaches Slack."""
import os, sys, tempfile, time, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import slack_cfg as S

APP = dict(client_id="1234567.7654321", client_secret="a" * 32, signing_secret="b" * 32, app_token="xapp-1-A0-123-" + "c" * 30)
GRANT = {"ok": True, "token_type": "bot", "access_token": "xoxb-1-2-secret", "scope": S.SCOPES, "bot_user_id": "UBOT123", "app_id": "A0APP1",
         "team": {"id": "T0TEAM1", "name": "Navaan"}, "authed_user": {"id": "U0OWNER1"}}


class Fake:
    def __init__(self, answers): self.answers, self.calls = answers, []
    def __call__(self, method, url, headers=None, data=None, timeout=20):
        name = url.rsplit("/", 1)[1]; self.calls.append((name, dict(data or {}), dict(headers or {})))
        return 200, self.answers.get(name, {"ok": False, "error": "unknown_method"})


class Slack(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        p = mock.patch.dict(os.environ, {"NAVAAN_CONF_DIR": self.tmp.name, "NAVAAN_STUDIO_HOST": "studio.navaan.online", "NAVAAN_SLACK_REDIRECT": ""}); p.start(); self.addCleanup(p.stop)
        S.STATES.clear(); S._CHECK.update(at=0.0, problem="")

    def connect(self, fake):
        S.app_save(**APP)
        url = S.start(); state = url.split("state=")[1]
        with mock.patch.object(S, "HTTP", fake): return S.finish({"state": [state], "code": ["c0de"]}), state

    def test_the_app_keys_are_checked_and_never_shown(self):
        with self.assertRaises(ValueError): S.app_save(**{**APP, "client_secret": "nope"})
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, S.ENV)))   # nothing written on a refusal
        with self.assertRaisesRegex(ValueError, "Still needed"): S.app_save(APP["client_id"], "", "", "")
        st = S.app_save(**APP); self.assertTrue(st["app_saved"]); self.assertTrue(st["app_token"]); self.assertNotIn("a" * 32, repr(st))
        self.assertEqual(oct(os.stat(os.path.join(self.tmp.name, S.ENV)).st_mode & 0o777), "0o600")
        S.app_save("", "", "", ""); self.assertTrue(S.status()["app_saved"])   # empty boxes keep what is saved

    def test_connect_sends_the_browser_to_slack_with_a_single_use_state(self):
        with self.assertRaisesRegex(ValueError, "Client ID"): S.start()
        S.app_save(**APP); url = S.start()
        self.assertTrue(url.startswith(S.AUTHORIZE)); self.assertIn("redirect_uri=https%3A%2F%2Fstudio.navaan.online%2Fapi%2Fslack%2Fcallback", url); self.assertIn("client_id=1234567.7654321", url)
        with mock.patch.dict(os.environ, {"NAVAAN_STUDIO_HOST": ""}), self.assertRaisesRegex(ValueError, "https"): S.start()

    def test_the_callback_saves_the_bot_token_and_who_connected(self):
        fake = Fake({"oauth.v2.access": GRANT}); st, state = self.connect(fake)
        self.assertTrue(st["connected"]); self.assertEqual((st["team"], st["owner_user_id"]), ("Navaan", "U0OWNER1")); self.assertNotIn("xoxb", repr(st))
        sent = fake.calls[0][1]; self.assertEqual((sent["code"], sent["client_id"], sent["redirect_uri"]), ("c0de", APP["client_id"], "https://studio.navaan.online/api/slack/callback"))
        with mock.patch.object(S, "HTTP", fake), self.assertRaisesRegex(ValueError, "already used"): S.finish({"state": state, "code": "c0de"})   # the same state twice: refused

    def test_a_bad_callback_saves_nothing(self):
        S.app_save(**APP)
        with self.assertRaisesRegex(ValueError, "did not start here"): S.finish({"state": "forged", "code": "x"})
        with self.assertRaisesRegex(ValueError, "not approved"): S.finish({"error": "access_denied"})
        state = S.start().split("state=")[1]; S.STATES[state] = time.time() - 1
        with self.assertRaisesRegex(ValueError, "too long"): S.finish({"state": state, "code": "x"})
        state = S.start().split("state=")[1]
        with mock.patch.object(S, "HTTP", Fake({"oauth.v2.access": {"ok": False, "error": "invalid_code"}})), self.assertRaisesRegex(ValueError, "invalid_code"): S.finish({"state": state, "code": "x"})
        state = S.start().split("state=")[1]
        with mock.patch.object(S, "HTTP", Fake({"oauth.v2.access": {**GRANT, "token_type": "user", "access_token": "xoxp-1"}})), self.assertRaisesRegex(ValueError, "bot token"): S.finish({"state": state, "code": "x"})
        self.assertFalse(S.status()["connected"])

    def test_the_channel_must_have_the_bot_and_gets_a_hello(self):
        self.connect(Fake({"oauth.v2.access": GRANT}))
        out = Fake({"conversations.info": {"ok": True, "channel": {"name": "navaan", "is_member": False}}})
        with mock.patch.object(S, "HTTP", out), self.assertRaisesRegex(ValueError, "/invite"): S.set_channel("C0CHAN1")
        self.assertEqual([c[0] for c in out.calls], ["conversations.info"])   # no hello where the bot is not
        ok = Fake({"conversations.info": {"ok": True, "channel": {"name": "navaan", "is_member": True}}, "chat.postMessage": {"ok": True}})
        with mock.patch.object(S, "HTTP", ok): st = S.set_channel("C0CHAN1")
        self.assertEqual(st["channel"], "navaan"); self.assertEqual(ok.calls[1][2]["Authorization"], "Bearer xoxb-1-2-secret")
        with self.assertRaises(ValueError): S.set_channel("not a channel")
        _, state = self.connect(Fake({"oauth.v2.access": GRANT})); self.assertEqual(S.status()["channel"], "navaan")   # a Reconnect keeps the channel

    def test_owner_fallback_revoked_token_and_disconnect(self):
        self.connect(Fake({"oauth.v2.access": {**GRANT, "authed_user": {}}})); self.assertEqual(S.status()["owner_user_id"], "")
        with self.assertRaises(ValueError): S.set_owner("me")
        self.assertEqual(S.set_owner("U0OWNER9")["owner_user_id"], "U0OWNER9")
        with mock.patch.object(S, "HTTP", Fake({"auth.test": {"ok": False, "error": "token_revoked"}})): self.assertIn("Reconnect", S.status(check=True)["problem"])
        bye = Fake({"auth.revoke": {"ok": True}})
        with mock.patch.object(S, "HTTP", bye): st = S.disconnect()
        self.assertEqual(bye.calls[0][0], "auth.revoke"); self.assertFalse(st["connected"]); self.assertTrue(st["app_saved"]); self.assertEqual(st["team"], "")


if __name__ == "__main__": unittest.main()
