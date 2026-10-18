"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: the "send this to someone who..." line at the end of a Reel: reading it, drawing it on a finished video, and doing nothing without it.
"""
import hashlib, os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import send_line as S

HAVE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


class Read(unittest.TestCase):
    def test_the_line_is_cleaned_to_one_short_line_and_missing_means_nothing(self):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d, True)
        self.assertEqual(S.read(d), "")
        w = lambda t: open(os.path.join(d, S.FILE), "w", encoding="utf-8").write(t)
        w("  “Send this to someone\n far from home.”  \n"); self.assertEqual(S.read(d), "Send this to someone far from home.")
        w("x" * 200); self.assertEqual(len(S.read(d)), S.MAX_CHARS)
        w("   \n"); self.assertEqual(S.read(d), "")


@unittest.skipUnless(HAVE, "ffmpeg is needed")
class Draw(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.d, True); self.v = os.path.join(self.d, "v.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x203040:s=360x640:d=6:r=30", "-f", "lavfi", "-i", "sine=frequency=330:duration=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", self.v], check=True)

    def frame(self, t, tag):
        from PIL import Image
        out = os.path.join(self.d, f"f{tag}{t}.png"); subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", self.v, "-frames:v", "1", out], check=True)
        return Image.open(out).convert("L")

    def change(self, a, b):
        from PIL import ImageChops, ImageStat
        return ImageStat.Stat(ImageChops.difference(a, b)).mean[0]   # how much two frames differ, 0 to 255

    def test_without_a_send_line_the_video_is_not_touched(self):
        before = hashlib.sha1(open(self.v, "rb").read()).hexdigest()
        self.assertEqual(S.apply(self.v, self.d), ""); self.assertEqual(hashlib.sha1(open(self.v, "rb").read()).hexdigest(), before)

    def test_the_line_is_drawn_on_the_last_seconds_only_and_the_sound_and_length_stay(self):
        open(os.path.join(self.d, S.FILE), "w").write("Send this to someone far from home")
        early, late = self.frame(1.0, "a"), self.frame(5.0, "a")
        self.assertEqual(S.apply(self.v, self.d, 0.78, 3.2), "Send this to someone far from home")
        self.assertLess(self.change(self.frame(1.0, "b"), early), 2.0)   # the opening is the same picture (a re-encode moves every pixel by a level at most)
        self.assertGreater(self.change(self.frame(5.0, "b"), late), 3.0)   # the end carries the line: bright text on the flat background; a bigger change than the re-encode alone
        pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "csv=p=0", self.v], capture_output=True, text=True).stdout
        self.assertIn("audio", pr); self.assertAlmostEqual(float(pr.split()[-1].split(",")[-1]), 6.0, delta=0.2)

    def test_a_failure_leaves_the_video_as_it_was(self):
        open(os.path.join(self.d, S.FILE), "w").write("Send this to someone"); before = hashlib.sha1(open(self.v, "rb").read()).hexdigest()
        open(self.v, "ab").write(b"")   # unchanged bytes
        from unittest import mock
        with mock.patch.object(S.C, "tool", lambda n: "false" if n == "ffmpeg" else shutil.which(n)):
            with self.assertRaises(RuntimeError): S.apply(self.v, self.d)
        self.assertEqual(hashlib.sha1(open(self.v, "rb").read()).hexdigest(), before)


if __name__ == "__main__":
    unittest.main()
