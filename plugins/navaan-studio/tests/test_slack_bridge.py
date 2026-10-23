"""NAV-154..158: the Slack bridge. Slack itself is never reached: posting, answering and Claude are fakes; the WebSocket client is tested over a local socket pair."""
import json, os, socket, struct, sys, tempfile, threading, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import slack_ws, slack_bridge as B, slack_cfg as S

OWNER, OTHER, CHAN = "U0OWNER1", "U0OTHER2", "C0CHAN1"


def frame(op, data, fin=True):
    n = len(data); head = bytes([(0x80 if fin else 0) | op])
    head += bytes([n]) if n < 126 else bytes([126]) + struct.pack(">H", n)
    return head + data


def unmask(raw):
    n = raw[1] & 0x7F; i = 2
    if n == 126: n = struct.unpack(">H", raw[2:4])[0]; i = 4
    mask = raw[i:i + 4]; data = raw[i + 4:i + 4 + n]
    return raw[0] & 0x0F, bytes(c ^ mask[k % 4] for k, c in enumerate(data))


class WebSocket(unittest.TestCase):
    def test_pings_are_answered_fragments_joined_and_a_close_ends_it(self):
        a, b = socket.socketpair(); ws = slack_ws.WS(a)
        b.sendall(frame(0x9, b"hi") + frame(0x1, b"hel", fin=False) + frame(0x0, b"lo") + frame(0x1, "é".encode() * 100) + frame(0x8, b""))
        self.assertEqual(ws.recv(2), "hello")
        self.assertEqual(unmask(b.recv(100)), (0xA, b"hi"))   # the pong, masked like every client frame
        self.assertEqual(ws.recv(2), "é" * 100)
        self.assertIsNone(ws.recv(2))
        ws.send('{"envelope_id": "x"}'); self.assertEqual(unmask(b.recv(100)), (0x1, b'{"envelope_id": "x"}'))
        a.close(); b.close()

    def test_nothing_in_time_is_an_empty_answer(self):
        a, b = socket.socketpair(); self.assertEqual(slack_ws.WS(a).recv(0.05), ""); a.close(); b.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        p = mock.patch.dict(os.environ, {"NAVAAN_CONF_DIR": self.tmp.name, "NAVAAN_STATE_DIR": self.tmp.name, "NAVAAN_STUDIO_HOST": "studio.navaan.online"}); p.start(); self.addCleanup(p.stop)
        S._write_meta({"team_id": "T1", "owner_user_id": OWNER, "channel_id": CHAN, "scopes": S.SCOPES}); S._write_env({"SLACK_BOT_TOKEN": "xoxb-1", "SLACK_APP_TOKEN": "xapp-1"})
        self.posted, self.said, self.whisper = [], [], []
        for t, f in ((B, "post"), (B, "respond"), (B, "ephemeral")):
            store = {"post": self.posted, "respond": self.said, "ephemeral": self.whisper}[f]
            p = mock.patch.object(t, f, lambda *a, _s=store, **k: _s.append((a, k))); p.start(); self.addCleanup(p.stop)


class Outbox(Base):
    def test_the_first_pass_marks_what_is_there_and_later_ones_post_each_new_event_once(self):
        evs = [{"key": "gate:insp-1:media::5", "kind": "gate", "slug": "insp-1", "gate": "media", "title": "Rise", "link": "", "qa": None}]
        posts = []
        with mock.patch.object(B, "events", lambda: evs):
            sent, n = B.outbox_pass(None, lambda t, b=None: posts.append(t)); self.assertEqual(n, 1); self.assertIn("1 item waiting", posts[0])
            sent, n = B.outbox_pass(sent, lambda t, b=None: posts.append(t)); self.assertEqual(n, 0)   # already seen: nothing on a restart or a retry
            evs.append({"key": "fail:42", "kind": "fail", "slug": "insp-2", "title": "Fall", "link": "", "error": "render failed: Bearer abc.def"})
            sent, n = B.outbox_pass(sent, lambda t, b=None: posts.append(t)); self.assertEqual(n, 1); self.assertIn("render failed", posts[-1]); self.assertNotIn("abc.def", posts[-1])
        B.save_sent(sent); self.assertIn("fail:42", B.load_sent())   # kept across restarts

    def test_a_refused_post_leaves_the_event_unsent(self):
        evs = [{"key": "alert:claude:x", "kind": "alert", "title": "Claude token expired", "message": "m"}]
        def boom(t, b=None): raise ValueError("Slack said no: channel_not_found.")
        with mock.patch.object(B, "events", lambda: evs), self.assertRaises(ValueError): B.outbox_pass({}, boom)
        with mock.patch.object(B, "events", lambda: evs): sent, n = B.outbox_pass({}, lambda t, b=None: None)
        self.assertEqual(n, 1); self.assertIn("alert:claude:x", sent)

    def test_only_media_quote_and_originality_carry_an_approve_button(self):
        t, b = B.message({"kind": "gate", "slug": "insp-1", "gate": "media", "title": "Rise", "link": "https://x/y", "qa": {"verdict": "fix", "summary": "Two lines overlap.", "fixes": ["lift line 2"]}})
        ids = [e.get("action_id") for e in b[1]["elements"]]; self.assertEqual(ids, ["approve", None]); self.assertIn("QA asks for fixes", t); self.assertIn("lift line 2", t)
        t, b = B.message({"kind": "gate", "slug": "insp-1", "gate": "credits", "title": "Rise", "link": "https://x/y", "qa": None})
        self.assertEqual([e.get("action_id") for e in b[1]["elements"]], [None]); self.assertIn("approved in Studio", t)


class Actions(Base):
    def press(self, user, action, value):
        B.on_action({"user": {"id": user}, "channel": {"id": CHAN}, "response_url": "https://hooks.slack.com/x", "actions": [{"action_id": action, "value": json.dumps(value)}]})

    def test_only_the_owner_approves_and_only_what_waits(self):
        import navaan as N
        with mock.patch.object(B, "items", lambda: ["insp-1"]), mock.patch.object(N, "plan", lambda s: ([], {"type": "gate", "gate": "media"})), mock.patch.object(N, "set_gate") as sg:
            self.press(OTHER, "approve", {"slug": "insp-1", "gate": "media"}); sg.assert_not_called(); self.assertIn("Only <@U0OWNER1>", self.whisper[-1][0][2])
            self.press(OWNER, "approve", {"slug": "insp-1", "gate": "credits"}); sg.assert_not_called()   # spending stays in Studio
            self.press(OWNER, "approve", {"slug": "insp-1", "gate": "media"}); sg.assert_called_once_with("insp-1", "media", True, "slack:U0OWNER1")
            self.assertIn("approved by <@U0OWNER1> via Slack", self.said[-1][0][1])
        with mock.patch.object(B, "items", lambda: ["insp-1"]), mock.patch.object(N, "plan", lambda s: ([], {"type": "step", "step": "publish"})), mock.patch.object(N, "set_gate") as sg:
            self.press(OWNER, "approve", {"slug": "insp-1", "gate": "media"}); sg.assert_not_called(); self.assertIn("no longer waiting", self.said[-1][0][1])

    def test_start_makes_the_item_like_the_studio_form_and_queues_its_run(self):
        with mock.patch.object(B, "start_new", return_value="insp-9") as sn:
            self.press(OWNER, "new_start", {"type": "inspiration", "idea": "keep going"}); sn.assert_called_once_with("inspiration", "keep going", OWNER)
        self.assertIn("Started *insp-9*", self.said[-1][0][1])


class Commands(Base):
    def cmd(self, text, user=OWNER, channel=CHAN): B.on_command({"user_id": user, "channel_id": channel, "text": text, "response_url": "https://hooks.slack.com/x"})

    def test_status_new_and_the_channel_rule(self):
        self.cmd("status", channel="C0ELSE"); self.assertIn("Use /navaan in", self.said[-1][0][1])
        with mock.patch.object(B, "status_text", lambda s="": f"STATUS[{s}]"):
            self.cmd("status"); self.assertEqual(self.said[-1][0][1], "STATUS[]")
            self.cmd("status insp-1"); self.assertEqual(self.said[-1][0][1], "STATUS[insp-1]")
        self.cmd("new aha why toast falls", user=OTHER); self.assertIn("Only", self.said[-1][0][1])
        self.cmd("new podcast x"); self.assertIn("Usage", self.said[-1][0][1])
        self.cmd("new aha why toast falls butter side down"); a, k = self.said[-1]
        self.assertIn("Start a new aha", a[1]); self.assertEqual(json.loads(k["blocks"][1]["elements"][0]["value"]), {"type": "aha", "idea": "why toast falls butter side down"})


class Words(Base):
    def say(self, text, answer, user=OWNER, **ev):
        with mock.patch.object(B, "events", lambda: []):
            B.on_message({"user": user, "channel": CHAN, "text": text, **ev}, runner=lambda p: answer)

    def test_claude_maps_words_onto_the_same_confirmed_actions(self):
        with mock.patch.object(B, "items", lambda: ["insp-1"]):
            self.say("ship the video of insp-1", '{"action": "approve", "slug": "insp-1", "gate": "media"}')
        t, b = self.posted[-1][0]; self.assertIn("Approve the video of *insp-1*?", t); self.assertEqual(b[1]["elements"][0]["action_id"], "approve")   # a button, not an approval
        self.say("start an inspiration about patience", 'Sure: {"action": "new", "type": "inspiration", "idea": "patience"}')
        self.assertIn("Start a new inspiration", self.posted[-1][0][0])
        self.say("approve everything", '{"action": "approve", "slug": "made-up", "gate": "media"}'); self.assertNotIn("Approve the video", self.posted[-1][0][0])   # no invented items
        n = len(self.posted)
        self.say("hi", '{"action": "status"}', user=OTHER); self.say("hi", '{"action": "status"}', bot_id="B1"); self.say("hi", '{"action": "status"}', subtype="channel_join")
        self.assertEqual(len(self.posted), n)   # only the owner's own messages are read


class NewItem(Base):
    def test_start_new_uses_the_studio_path(self):
        import navaan_ui, navaan
        root = os.path.join(self.tmp.name, "root"); os.makedirs(os.path.join(root, "songs"))
        with mock.patch.dict(os.environ, {"NAVAAN_ROOT": root}), mock.patch.object(navaan_ui, "start_job", return_value=True) as sj:
            sl = B.start_new("inspiration", "  keep   going ", OWNER)
            sj.assert_called_once_with(sl, True)
            self.assertIn("created from Slack via slack:U0OWNER1", json.dumps(navaan.meta(sl)))
            with self.assertRaises(ValueError): B.start_new("podcast", "x", OWNER)
            with self.assertRaises(ValueError): B.start_new("aha", "   ", OWNER)


    def test_events_read_a_real_item_its_waiting_approval_its_qa_and_status(self):
        import navaan_ui, navaan, navaan_common as C
        root = os.path.join(self.tmp.name, "root"); os.makedirs(os.path.join(root, "songs"))
        with mock.patch.dict(os.environ, {"NAVAAN_ROOT": root}), mock.patch.object(navaan_ui, "start_job", return_value=True):
            sl = B.start_new("inspiration", "keep going", OWNER)
            with open(os.path.join(C.song_dir(sl), "qa.json"), "w") as f: json.dump({"verdict": "pass", "summary": "Clean."}, f)
            with mock.patch.object(navaan, "plan", lambda s: ([{"id": "render", "label": "Render", "status": "done"}], {"type": "gate", "gate": "media"})), mock.patch("settings_api.alerts", lambda: []):
                ev = [e for e in B.events() if e.get("slug") == sl]
                self.assertEqual([e["kind"] for e in ev], ["gate"]); self.assertEqual(ev[0]["qa"]["verdict"], "pass")
                self.assertEqual(ev[0]["link"], f"https://studio.navaan.online/app/studio/inspiration/{sl}")
                self.assertIn("waiting for you: the video", B.status_text()); self.assertIn("✓ Render", B.status_text(sl))
            self.assertIn("No item called", B.status_text("nope"))

if __name__ == "__main__": unittest.main()
