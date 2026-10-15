import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import visuals_cfg as V


class T(unittest.TestCase):
    def test_video_needs_pictures_unless_openai_will_make_them(self):
        D = tempfile.mkdtemp()
        with self.assertRaises(ValueError): V.save(D, "own", "video")
        v = V.save(D, "own", "video", pictures_later=True)
        self.assertEqual((v["mode"], v["layout"]), ("own", "video"))
        self.assertTrue(os.path.exists(V.vpath(D)))

    def test_static_still_needs_its_cover_picture(self):
        D = tempfile.mkdtemp()
        with self.assertRaises(ValueError): V.save(D, "own", "static", pictures_later=True)


if __name__ == "__main__":
    unittest.main()
