import os, sys, json, tempfile, subprocess, shutil, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import caption_clips as K
import navaan as N


def steps_for(flag):
    D = tempfile.mkdtemp()
    json.dump({"mode": "own", "layout": "motion"}, open(os.path.join(D, "visuals.json"), "w"))
    json.dump({"source": "suno_import"}, open(os.path.join(D, "meta.json"), "w"))
    old = N.cfg
    N.cfg = lambda k, d=None: flag if k == "captions.reel" else d
    try: return N.steps("x", D)
    finally: N.cfg = old


class T(unittest.TestCase):
    def test_plan_shifts_cues_into_the_reel(self):
        cues = [[10.0, 12.0, "before"], [50.0, 53.0, "inside one"], [54.0, 57.0, "inside two"], [200.0, 203.0, "after"]]
        items = K.plan(cues, 48.0, 45.0)
        self.assertEqual([t for _, _, t in items], ["inside one", "inside two"])
        self.assertAlmostEqual(items[0][0], 1.9, places=1)
        for a, b, _ in items: self.assertLess(a, b); self.assertLessEqual(b, 44.7)

    def test_plan_keeps_a_caption_that_started_just_before_the_reel(self):
        items = K.plan([[47.0, 51.0, "carry"]], 48.0, 45.0)
        self.assertEqual(len(items), 1); self.assertEqual(items[0][0], 0.3)

    def test_reel_captions_are_a_step_when_on(self):
        ids = [s["id"] for s in steps_for(True)]
        self.assertLess(ids.index("captions"), ids.index("video"))
        v = next(s for s in steps_for(True) if s["id"] == "video")
        self.assertTrue(any(c[-1] == "own" and c[-2].endswith("x") for c in v["cmds"]))
        self.assertIn("final_reel_9x16_cap.mp4", v["outputs"])

    def test_no_caption_step_when_off(self):
        ss = steps_for(False)
        self.assertNotIn("captions", [s["id"] for s in ss])
        v = next(s for s in ss if s["id"] == "video")
        self.assertFalse(any(c[-1] == "own" for c in v["cmds"]))

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_burns_captions_onto_the_reel(self):
        D = tempfile.mkdtemp()
        subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x203040:s=1080x1920:r=24:d=6", "-f", "lavfi", "-i", "sine=f=220:d=6",
                               "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", os.path.join(D, "final_reel_9x16.mp4")])
        json.dump({"start": 100.0, "dur": 6}, open(os.path.join(D, "reel_report.json"), "w"))
        json.dump([[101.0, 103.0, "first line"], [103.5, 105.5, "second line"]], open(os.path.join(D, "caption_cues.json"), "w"))
        K.song_dir = lambda slug: D
        try: K.main("x", "own")
        except SystemExit as e: self.skipTest(f"no usable font here: {e}")
        out = os.path.join(D, "final_reel_9x16_cap.mp4")
        self.assertTrue(os.path.exists(out))
        self.assertAlmostEqual(K.duration(out), 6.0, delta=0.3)
        self.assertGreater(os.path.getsize(out), 2000)


if __name__ == "__main__":
    unittest.main()
