import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import shots_render as R
import short_meta as M


class T(unittest.TestCase):
    def test_reel_plan_window(self):
        shots = [{"start": 0, "end": 40, "image": "a", "camera": "push_in"}, {"start": 40, "end": 100, "image": "b", "camera": "pan_left", "focus": [0.2, 0.4]},
                 {"start": 100, "end": 200, "image": "c", "camera": "drift"}]
        ps = R.reel_plan(shots, 50, 58, "a")
        self.assertEqual([p["image"] for p in ps], ["b", "c"])
        self.assertEqual(ps[0]["start"], 0.0); self.assertEqual(ps[-1]["end"], 58)
        self.assertEqual(ps[0]["end"], ps[1]["start"])
        self.assertEqual(ps[0]["focus"], [0.2, 0.4])

    def test_reel_plan_falls_back_to_one_shot(self):
        ps = R.reel_plan([], 10, 30, "cover.jpg")
        self.assertEqual(len(ps), 1); self.assertEqual((ps[0]["start"], ps[0]["end"], ps[0]["image"]), (0.0, 30, "cover.jpg"))

    def test_window_from_reel_start_json(self):
        D = tempfile.mkdtemp(); json.dump({"start": 100, "dur": 70}, open(os.path.join(D, "reel_start.json"), "w"))
        R.C.duration = lambda p: 300.0
        s, d = R.pick_window(D, "x.mp3")
        self.assertEqual(s, 100.0); self.assertEqual(d, R.REEL_MAX)

    def test_window_never_runs_past_the_song(self):
        D = tempfile.mkdtemp(); json.dump({"start": 290, "dur": 45}, open(os.path.join(D, "reel_start.json"), "w"))
        R.C.duration = lambda p: 300.0
        s, d = R.pick_window(D, "x.mp3")
        self.assertLessEqual(s + d, 300.0)

    def test_short_meta(self):
        out = M.build({"title": "Tere Hone Se #shorts", "description": "First para.\n\nSecond.", "tags": ["a", "b"], "language": "hi"}, "https://youtu.be/abc")
        self.assertEqual(out["title"], "Tere Hone Se #Shorts")
        self.assertTrue(out["description"].startswith("Full song: https://youtu.be/abc"))
        self.assertIn("First para.", out["description"]); self.assertNotIn("Second.", out["description"])
        self.assertIn("Shorts", out["tags"]); self.assertEqual(out["language"], "hi")
        self.assertLessEqual(len(M.build({"title": "x" * 200}, "")["title"]), 100)


if __name__ == "__main__":
    unittest.main()
