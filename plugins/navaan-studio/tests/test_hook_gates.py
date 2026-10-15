import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

CHORUS = ["एक ख़त था, जो लिखा ही नहीं,", "एक दर्द था, जो कहा ही नहीं।", "तुम मेरी कभी बनी ही नहीं,", "दिल को तुम्हारे बिना सुकूँ मिला ही नहीं।"]


def cues():
    out, t = [], 15.0
    for tx in ["तुम सामने थीं, मैं चुप रहा,", "दिल का हर हाल, मैंने न कहा।", "आँखों में ख़्वाब थे, होंठों पे बात,", "इतनी क़रीब, फिर भी तन्हा थी रात।", "तुम आईं तो कमरा गुलज़ार हुआ,", "सूना-सा ये दिल भी तैयार हुआ।"] + CHORUS + ["तुम भूल गईं वो मुलाक़ात की घड़ी,", "मैं रात भर उसकी याद में जगता रहा।"] + CHORUS:
        out.append([t, t + 5.5, tx]); t += 6.5
    return out


class Hook(unittest.TestCase):
    def test_claude_pick_sets_the_window_on_the_hook_lines(self):
        import reel_hook as H
        c = cues(); r = H.pick(c, "", ask=lambda cu, st: (6, 9))
        self.assertEqual(r["source"], "claude")
        self.assertAlmostEqual(r["start"], round(c[6][0] - 0.5, 1))
        self.assertGreaterEqual(r["dur"], H.MIN_DUR); self.assertLessEqual(r["dur"], H.MAX_DUR)
        self.assertGreaterEqual(r["start"] + r["dur"], c[9][1])   # the four hook lines are all inside

    def test_without_claude_the_first_repeated_run_is_used(self):
        import reel_hook as H
        c = cues()
        def boom(cu, st): raise RuntimeError("no claude")
        r = H.pick(c, "", ask=boom)
        self.assertEqual(r["source"], "chorus"); self.assertEqual(r["first"], 6); self.assertEqual(r["last"], 9)

    def test_nothing_repeated_falls_back_to_the_busiest_stretch(self):
        import reel_hook as H
        words = "चाँद सूरज बारिश आसमान दरिया रेत हवा शहर रास्ता खिड़की किताब चिराग".split()
        c = [[i * 6.0, i * 6.0 + 5.0, f"{w} {w[::-1]} मेरा {w}ही"] for i, w in enumerate(words)]
        def boom(cu, st): raise RuntimeError("no claude")
        self.assertEqual(H.pick(c, "", ask=boom)["source"], "busiest")

    def test_bad_answer_from_claude_is_not_trusted(self):
        import reel_hook as H
        c = cues()
        r = H.pick(c, "", ask=lambda cu, st: (3, 99))
        self.assertNotEqual(r["source"], "claude")

    def test_short_hook_runs_on_to_the_minimum_length(self):
        import reel_hook as H
        c = cues(); start, dur = H.window(c, 6, 7)
        self.assertGreaterEqual(dur, H.MIN_DUR)


class Watermark(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup()

    def test_default_is_the_handle_or_navaan(self):
        import watermark as W, navaan_common as C
        D = os.path.join(C.songs_root(), "s1"); os.makedirs(D)
        json.dump({"slug": "s1", "type": "music"}, open(os.path.join(D, "meta.json"), "w"))
        old = C.cfg
        try:
            C.cfg = lambda k, d=None: {"publish.instagram_handle": "@navaan.music"}.get(k, d)
            self.assertEqual(W.text(D), "@navaan.music")
            C.cfg = lambda k, d=None: d
            self.assertEqual(W.text(D), "NAVAAN")
            C.cfg = lambda k, d=None: {"video.watermark": "off"}.get(k, d)
            self.assertIsNone(W.text(D))
            C.cfg = lambda k, d=None: {"video.watermark": "© The Unsaid Within"}.get(k, d)
            self.assertEqual(W.text(D), "© The Unsaid Within")
        finally:
            C.cfg = old


class Gates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name; os.environ["NAVAAN_CONF_DIR"] = os.path.join(self.tmp.name, "conf")
    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); os.environ.pop("NAVAAN_CONF_DIR", None); self.tmp.cleanup()

    def test_every_gate_is_on_by_default_and_a_switch_sticks(self):
        import gate_cfg as G, navaan_common as C
        st = G.status()["gates"]
        self.assertEqual([x["id"] for x in st], list(C.GATES)); self.assertTrue(all(x["on"] for x in st))
        G.save({"media": False, "go_public": False})
        self.assertEqual(G.load(), {"media", "go_public"})
        G.save({"media": True})
        self.assertEqual(G.load(), {"go_public"})
        with self.assertRaises(ValueError): G.save({"nope": False})

    def test_a_gate_switched_off_approves_itself_once_and_leaves_the_others(self):
        import gate_cfg as G, navaan as N, navaan_common as C
        D = os.path.join(C.songs_root(), "s1"); os.makedirs(D)
        json.dump({"slug": "s1", "type": "music", "state": "approved", "approvals": {}}, open(os.path.join(D, "meta.json"), "w"))
        self.assertEqual(N.auto_gates("s1"), [])   # nothing off, nothing approved
        G.save({"listen": False, "credits": False})
        self.assertEqual(sorted(N.auto_gates("s1")), ["credits", "listen"])
        ap = json.load(open(os.path.join(D, "meta.json")))["approvals"]
        self.assertEqual(sorted(ap), ["credits", "listen"]); self.assertIn("auto", ap["listen"]["via"])
        self.assertEqual(N.auto_gates("s1"), [])   # already approved


if __name__ == "__main__":
    unittest.main()
