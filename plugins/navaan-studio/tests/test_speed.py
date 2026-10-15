import os, shutil, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))


class Backdrop(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg not installed")
    def test_blurred_backdrop_is_made_once_at_the_reel_size(self):
        tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = tmp.name
        try:
            import shots_render as S
            D = tmp.name; os.makedirs(os.path.join(D, ".cache", "shots"))
            src = os.path.join(D, ".cache", "shots", "pic_01.jpg")
            subprocess.check_call(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360", "-frames:v", "1", src])
            rel = S.blur_backdrop(D, os.path.join(".cache", "shots", "pic_01.jpg"))
            out = os.path.join(D, rel); self.assertTrue(os.path.exists(out))
            wh = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", out], text=True).strip()
            self.assertEqual(wh, "1080,1920")
            m = os.path.getmtime(out); S.blur_backdrop(D, os.path.join(".cache", "shots", "pic_01.jpg")); self.assertEqual(os.path.getmtime(out), m)   # not made again
        finally:
            os.environ.pop("NAVAAN_ROOT", None); tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
