import os, re, shutil, subprocess, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
HAVE_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def _import():
    tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = tmp.name
    import ffrender as F
    return F, tmp


class Moves(unittest.TestCase):
    def test_camera_moves_mirror_shots_tsx(self):
        F, tmp = _import()
        try:
            src = open(os.path.join(HERE, "..", "remotion", "src", "Shots.tsx"), encoding="utf-8").read()
            self.assertIn("const BASE = 1.16", src.replace("export ", ""))
            self.assertEqual(F.BASE, 1.16)
            # push in: scale grows 0.1 over the shot, shift aims at the focus
            s, x, y = F.move("push_in", 1.0, (0.25, 0.5))
            self.assertAlmostEqual(s, 1.26); self.assertAlmostEqual(x, 2.0); self.assertAlmostEqual(y, 0)
            s, x, y = F.move("pull_out", 1.0, (0.5, 0.5)); self.assertAlmostEqual(s, 1.16)
            travel = (1.16 - 1) * 50
            self.assertAlmostEqual(F.move("pan_left", 0, (0.5, 0.5))[1], travel)
            self.assertAlmostEqual(F.move("pan_left", 1, (0.5, 0.5))[1], -travel)
            self.assertAlmostEqual(F.move("pan_right", 0, (0.5, 0.5))[1], -travel)
            self.assertAlmostEqual(F.move("tilt_up", 0, (0.5, 0.5))[2], travel)
            self.assertAlmostEqual(F.move("drift", 0.5, (0.5, 0.5))[0], 1.19)
            self.assertEqual(F.move("hold", 0.7, (0.5, 0.5)), (1.16, 0, 0))
            self.assertEqual(F.fit_scale("hold", 1), 1.0); self.assertAlmostEqual(F.fit_scale("push_in", 1), 1.06)
        finally:
            tmp.cleanup()

    def test_zoompan_filter_text(self):
        F, tmp = _import()
        try:
            f = F.zoompan({"camera": "pan_left", "focus": [0.5, 0.5]}, 1920, 1080, 24, 1.2, 8)
            self.assertTrue(f.startswith("zoompan=z='")); self.assertIn("s=1920x1080:fps=24", f)
            self.assertNotIn("nan", f.lower())
            self.assertIn("1+0.06*", F.zoompan({"camera": "push_in"}, 1080, 1920, 24, 0, 8, fit=True))
        finally:
            tmp.cleanup()


class Timeline(unittest.TestCase):
    def test_first_shot_has_no_lead_and_later_ones_cross_fade(self):
        F, tmp = _import()
        try:
            shots = [{"start": 0, "end": 8}, {"start": 8, "end": 16}, {"start": 16, "end": 24}]
            tl = F.timeline(shots, 1.2, 24)
            self.assertEqual(tl[0][0], 0); self.assertEqual(tl[0][1], 0)
            self.assertAlmostEqual(tl[1][0], 6.8); self.assertAlmostEqual(tl[1][1], 1.2)
            self.assertAlmostEqual(tl[2][0], 14.8)
        finally:
            tmp.cleanup()


class Overlay(unittest.TestCase):
    def test_vignette_is_clear_in_the_middle_and_dark_in_the_corners(self):
        F, tmp = _import()
        try:
            im = F.vignette_layer(192, 108, 0.35)
            self.assertEqual(im.size, (192, 108))
            self.assertEqual(im.getpixel((96, 54))[3], 0)
            self.assertAlmostEqual(im.getpixel((0, 0))[3], round(0.35 * 255), delta=12)
        finally:
            tmp.cleanup()

    def test_mark_goes_bottom_right_wide_and_top_left_vertical(self):
        F, tmp = _import()
        try:
            try: F.C.font(12)
            except SystemExit: self.skipTest("no font on this machine")
            for W, H in ((960, 540), (540, 960)):
                p = os.path.join(tmp.name, f"m{W}.png"); F.watermark_png("@navaan.music", W, H, p, 0.0)
                from PIL import Image
                bb = Image.open(p).getchannel("A").getbbox()
                self.assertIsNotNone(bb)
                if W > H: self.assertTrue(bb[0] > W / 2 and bb[1] > H / 2)
                else: self.assertTrue(bb[2] < W / 2 and bb[3] < H / 2)
        finally:
            tmp.cleanup()


class Renderer(unittest.TestCase):
    @unittest.skipUnless(HAVE_FF, "ffmpeg not installed")
    def test_small_render_has_size_length_and_audio(self):
        F, tmp = _import()
        try:
            D = tmp.name; os.makedirs(os.path.join(D, "images"))
            for i, c in enumerate(("red", "blue")):
                subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"color=c={c}:s=640x360", "-frames:v", "1", os.path.join(D, "images", f"p{i}.jpg")])
            subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=5", os.path.join(D, "a.mp3")])
            props = {"width": 320, "height": 180, "fps": 12, "duration": 4.0, "audio": "a.mp3", "fade": 0.5, "grade": {"dim": 0.08, "vignette": 0.35}, "fadeOut": 1,
                     "watermark": "@test", "loopSeconds": 6,
                     "shots": [{"start": 0, "end": 2, "image": "images/p0.jpg", "camera": "push_in", "focus": [0.5, 0.5], "loop": None},
                               {"start": 2, "end": 4, "image": "images/p1.jpg", "camera": "pan_left", "focus": [0.5, 0.5], "loop": None}]}
            out = os.path.join(D, "o.mp4"); F.render(D, props, out)
            j = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", out], text=True)
            import json
            j = json.loads(j); kinds = {s["codec_type"] for s in j["streams"]}
            self.assertEqual(kinds, {"video", "audio"})
            v = [s for s in j["streams"] if s["codec_type"] == "video"][0]
            self.assertEqual((v["width"], v["height"]), (320, 180))
            self.assertAlmostEqual(float(j["format"]["duration"]), 4.0, delta=0.3)
            self.assertFalse(os.path.exists(os.path.join(D, ".cache", "ffseg")))   # scratch clips are cleaned up
        finally:
            tmp.cleanup()


class Fallback(unittest.TestCase):
    def test_remotion_is_used_when_the_fast_renderer_fails(self):
        tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = tmp.name
        try:
            import shots_render as S, ffrender
            calls = []
            old_r, old_run, old_ready = ffrender.render, S.subprocess.run, S.R.remotion_ready
            def boom(*a, **k): raise SystemExit("no font")   # navaan_common.font() exits, which must not stop the render
            ffrender.render = boom
            S.subprocess.run = lambda cmd, **k: calls.append(cmd)
            S.R.remotion_ready = lambda: True
            try:
                S.render_any(tmp.name, {}, os.path.join(tmp.name, "p.json"), os.path.join(tmp.name, "o.mp4"), "test")
            finally:
                ffrender.render, S.subprocess.run, S.R.remotion_ready = old_r, old_run, old_ready
            self.assertEqual(len(calls), 1); self.assertIn("remotion", calls[0])
        finally:
            os.environ.pop("NAVAAN_ROOT", None); tmp.cleanup()

    def test_fast_renderer_is_the_default_and_remotion_can_be_forced(self):
        tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = tmp.name
        try:
            import shots_render as S, ffrender
            seen = []
            old_r, old_run, old_ready, old_cfg = ffrender.render, S.subprocess.run, S.R.remotion_ready, S.C.cfg
            ffrender.render = lambda *a, **k: seen.append("ff")
            S.subprocess.run = lambda cmd, **k: seen.append("rm")
            S.R.remotion_ready = lambda: True
            try:
                S.render_any(tmp.name, {}, "p", "o", "t")
                S.C.cfg = lambda k, d=None: "remotion" if k == "video.renderer" else d
                S.render_any(tmp.name, {}, "p", "o", "t")
            finally:
                ffrender.render, S.subprocess.run, S.R.remotion_ready, S.C.cfg = old_r, old_run, old_ready, old_cfg
            self.assertEqual(seen, ["ff", "rm"])
        finally:
            os.environ.pop("NAVAAN_ROOT", None); tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
