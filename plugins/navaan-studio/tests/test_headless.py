"""NAVAAN_HEADLESS=1: a Chrome-driven step does not launch anything; it leaves a MAC: note. Run: python3 -W ignore -m unittest test_headless"""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))


class Headless(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan as N, navaan_common as C
        self.N, self.C = N, C
        self.D = os.path.join(C.songs_root(), "s1"); os.makedirs(self.D)
        json.dump({"slug": "s1", "type": "music", "state": "draft"}, open(os.path.join(self.D, "meta.json"), "w"))
        self.real = N.steps; self.real_run_cmd = N.run_cmd
        N.steps = lambda slug, D: [dict(id="visuals", outputs=["clips/a.mp4"], label="Cover art and Flow clips", kind="claude", skill="flow-visuals", chrome=True, state="draft", done=lambda m: False)]

    def tearDown(self):
        self.N.steps = self.real; self.N.run_cmd = self.real_run_cmd; os.environ.pop("NAVAAN_HEADLESS", None); self.tmp.cleanup()

    def test_headless_leaves_mac_note_and_runs_nothing(self):
        os.environ["NAVAAN_HEADLESS"] = "1"
        self.N.run_cmd = lambda *a, **k: self.fail("a command was started")
        self.assertEqual(self.N.run("s1", step="visuals", retries=0), 5)
        self.assertTrue(open(os.path.join(self.D, "needs_you.txt")).read().startswith("MAC: step visuals"))

    def test_not_headless_does_not_leave_note(self):
        os.environ["NAVAAN_HEADLESS"] = "0"
        self.assertEqual(self.N.run("s1", step="visuals", dry=True), 0)
        self.assertFalse(os.path.exists(os.path.join(self.D, "needs_you.txt")))


if __name__ == "__main__":
    unittest.main()
