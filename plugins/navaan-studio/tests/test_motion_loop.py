import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import motion_loop as M
import motion_clips as MC

try:
    import numpy as np, cv2
    HAVE = True
except ImportError:
    HAVE = False

BOX = [[0.4, 0.7], [0.5, 0.7], [0.5, 0.4], [0.4, 0.4]]


class Clean(unittest.TestCase):
    def test_clean_regions_keeps_good_and_drops_bad(self):
        r = M.clean_regions({"steam": [BOX, [[0, 0], [1, 1]]], "bogus": [BOX], "sway": [[[-1, 2], [2, 2], [0.5, -3]]], "flicker": "nope", "water": [[["a", 1], [0, 0], [1, 1]]]})
        self.assertEqual(sorted(r), ["steam", "sway"])
        self.assertEqual(len(r["steam"]), 1)
        self.assertTrue(all(0 <= v <= 1 for p in r["sway"][0] for v in p))
        self.assertEqual(M.clean_regions(None), {})

    def test_kinds_include_the_new_effects(self):
        for k in ("steam", "sway", "flicker", "foliage", "water", "sky"): self.assertIn(k, M.KINDS)


@unittest.skipUnless(HAVE, "numpy and opencv are not installed")
class Engine(unittest.TestCase):
    def img(self):
        rng = np.random.RandomState(1)
        return cv2.GaussianBlur((rng.rand(180, 320, 3) * 255).astype(np.uint8), (0, 0), 3)

    def frames(self, reg, strength="subtle", seconds=2, fps=12):
        return [f.astype(int) for f in M.iter_frames(self.img(), M.clean_regions(reg), size=(320, 180), seconds=seconds, fps=fps, strength=strength)]

    def test_only_marked_area_moves(self):
        fr = self.frames({"flicker": [BOX]})
        d = np.abs(fr[0] - fr[len(fr) // 2]).sum(axis=2)
        inside = d[int(0.4 * 180):int(0.7 * 180), int(0.4 * 320):int(0.5 * 320)].mean()
        outside = np.concatenate([d[:60].ravel(), d[:, :80].ravel()]).mean()
        self.assertGreater(inside, 0.5); self.assertLess(outside, 0.01)

    def test_loop_is_seamless(self):
        for reg in ({"steam": [BOX]}, {"sway": [BOX]}, {"flicker": [BOX]}):
            fr = self.frames(reg)
            step = np.abs(fr[1] - fr[0]).mean()
            wrap = np.abs(fr[0] - fr[-1]).mean()  # the jump from the last frame back to the first is no bigger than a normal step
            self.assertLessEqual(wrap, step * 1.5 + 0.05, reg)

    def test_strength_off_is_still(self):
        fr = self.frames({"steam": [BOX], "sway": [BOX], "flicker": [BOX]}, strength="off")
        self.assertEqual(np.abs(fr[0] - fr[-1]).sum(), 0)

    def test_gentle_moves_more_than_subtle(self):
        a = self.frames({"sway": [BOX]}, "subtle"); b = self.frames({"sway": [BOX]}, "gentle")
        self.assertGreater(np.abs(b[0] - b[len(b) // 2]).mean(), np.abs(a[0] - a[len(a) // 2]).mean())


class Clips(unittest.TestCase):
    def song(self, motion=True, shots=True):
        D = tempfile.mkdtemp(); os.makedirs(os.path.join(D, "images"))
        open(os.path.join(D, "images", "pic_01.png"), "wb").write(b"x"); open(os.path.join(D, "images", "pic_02.png"), "wb").write(b"x")
        if shots: json.dump({"shots": [{"start": 10, "end": 20, "image": "images/pic_02.png"}, {"start": 0, "end": 10, "image": "images/pic_01.png"}, {"start": 20, "end": 30, "image": "images/pic_01.png"}]}, open(os.path.join(D, "shots.json"), "w"))
        if motion: json.dump({"pictures": {"images/pic_01.png": {"regions": {"steam": [BOX]}}, "images/pic_02.png": {"regions": {}}}}, open(os.path.join(D, "motion.json"), "w"))
        return D

    def test_wanted_lists_each_picture_once_in_shot_order(self):
        self.assertEqual(MC.wanted(self.song()), ["images/pic_01.png", "images/pic_02.png"])

    def test_pending_only_pictures_with_regions(self):
        D = self.song()
        self.assertEqual(MC.pending(D), ["images/pic_01.png"])
        os.makedirs(os.path.dirname(MC.loop_path(D, "images/pic_01.png")))
        open(MC.loop_path(D, "images/pic_01.png"), "wb").write(b"mp4")
        os.utime(os.path.join(D, "images", "pic_01.png"), (1, 1)); os.utime(os.path.join(D, "motion.json"), (1, 1))
        self.assertEqual(MC.pending(D), [])

    def test_no_motion_file_means_nothing_pending(self):
        self.assertEqual(MC.pending(self.song(motion=False)), [])

    def test_loop_path_is_under_cache(self):
        self.assertTrue(MC.loop_path("/s", "images/pic_01.png").endswith(os.path.join(".cache", "motion", "pic_01.mp4")))


if __name__ == "__main__":
    unittest.main()
