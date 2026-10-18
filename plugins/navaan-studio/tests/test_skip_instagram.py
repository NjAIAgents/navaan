"""Skip Instagram for one item: its caption and post steps leave the pipeline, so it can finish on YouTube alone, and a failed post is no longer news."""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401


class SkipInstagram(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan_common as C, navaan as N
        self.C, self.N = C, N
        if hasattr(C, "_CFG"): C._CFG = None
        self.D = os.path.join(C.songs_root(), "insp-001"); os.makedirs(self.D)

    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup()

    def ids(self, m):
        json.dump({"slug": "insp-001", "type": "inspiration", "state": "draft", "approvals": {}, **m}, open(os.path.join(self.D, "meta.json"), "w"))
        return [r["id"] for r in self.N.plan_lanes("insp-001")[0]]

    def test_skipping_takes_the_instagram_steps_out_and_undoing_brings_them_back(self):
        self.assertIn("publish_instagram", self.ids({}))
        self.assertTrue(self.N.ig_enabled({"type": "inspiration"})); self.assertFalse(self.N.ig_enabled({"type": "inspiration", "skip": {"instagram": True}}))
        on = self.ids({"skip": {"instagram": True}}); self.assertNotIn("publish_instagram", on); self.assertNotIn("instagram_caption", on); self.assertIn("publish_youtube", on)
        self.assertIn("publish_instagram", self.ids({"skip": {}}))


if __name__ == "__main__":
    unittest.main()
