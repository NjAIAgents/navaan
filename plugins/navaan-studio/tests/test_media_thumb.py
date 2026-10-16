"""Covers are served as small cached JPEGs for list views. Run: python3 -W ignore -m unittest test_media_thumb"""
import os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import navaan_ui as U


@unittest.skipUnless(shutil.which("ffmpeg"), "needs ffmpeg")
class Thumb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.o = U.THUMB_DIR; U.THUMB_DIR = os.path.join(self.tmp.name, "thumbs")
        self.png = os.path.join(self.tmp.name, "cover_1x1.png")
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:size=1500x1500,noise=alls=100:allf=t", "-frames:v", "1", self.png], check=True)

    def tearDown(self): U.THUMB_DIR = self.o; self.tmp.cleanup()

    def test_small_cached_and_original_fallback(self):
        t = U.H._thumb(None, self.png, 480)
        self.assertNotEqual(t, self.png); self.assertTrue(t.endswith(".jpg")); self.assertLess(os.path.getsize(t), os.path.getsize(self.png) / 5)
        self.assertEqual(U.H._thumb(None, self.png, 480), t)  # second call hits the cache
        self.assertEqual(U.H._thumb(None, self.png, 481), self.png)  # a width outside the allowed list serves the original
        self.assertEqual(U.H._thumb(None, os.path.join(self.tmp.name, "x.mp3"), 480), os.path.join(self.tmp.name, "x.mp3"))


if __name__ == "__main__": unittest.main()
