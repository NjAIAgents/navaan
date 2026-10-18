"""NAV-67: The Aha-lorithm, a YouTube-Shorts-only channel built on the inspiration pipeline: no Instagram, its own account, its own look."""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401


class Aha(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
        tok = os.path.join(self.tmp.name, "yt_aha.json"); open(tok, "w").write("{}")
        json.dump({"accounts": {"aha": {"instagram_handle": "", "youtube_channel": "@TheAhalorithm", "youtube_token": tok}}}, open(os.path.join(self.tmp.name, "navaan.config.json"), "w"))
        import navaan_common as C, navaan as N, inspire_prep as P
        self.C, self.N, self.P = C, N, P
        if hasattr(C, "_CFG"): C._CFG = None
        self.D = os.path.join(C.songs_root(), "aha-001"); os.makedirs(self.D)
        json.dump({"slug": "aha-001", "type": "aha", "state": "draft", "approvals": {}}, open(os.path.join(self.D, "meta.json"), "w"))

    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup()

    def test_its_gates_and_steps_have_no_instagram_and_the_writers_know_the_channel(self):
        self.assertNotIn("instagram_caption", self.C.type_gates("aha")); self.assertNotIn("publish_instagram", self.C.type_gates("aha"))
        ids = [s["id"] for s in self.N.steps("aha-001", self.D)]
        self.assertIn("publish_youtube", ids); self.assertIn("go_public", ids)
        self.assertNotIn("instagram_caption", ids); self.assertNotIn("publish_instagram", ids)
        meta_step = next(s for s in self.N.steps("aha-001", self.D) if s["id"] == "youtube_meta"); self.assertIn("The Aha-lorithm", meta_step["hint"]); self.assertIn("AI awareness", meta_step["hint"])
        self.assertFalse(self.N.ig_enabled({"type": "aha"})); self.assertTrue(self.C.is_short("aha")); self.assertEqual(self.C.TYPE_PREFIX["aha"], "aha")

    def test_a_youtube_login_alone_makes_its_account_ready(self):
        a = self.C.account("aha"); self.assertTrue(a["configured"]); self.assertEqual(a["youtube_channel"], "@TheAhalorithm")

    def test_its_look_and_mark_are_its_own(self):
        self.assertEqual(self.P.handle("aha"), "TheAhalorithm"); self.assertEqual(self.P.watermark("aha-001"), "@TheAhalorithm")
        self.assertEqual(self.P.LOOKS["aha"]["font"], "sans"); self.assertNotEqual(self.P.LOOKS["aha"]["accent"], self.P.LOOKS["inspiration"]["accent"])


if __name__ == "__main__":
    unittest.main()
