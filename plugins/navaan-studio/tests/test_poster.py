import os, sys, io, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import poster as P
from PIL import Image


def png():
    b = io.BytesIO(); Image.new("RGB", (1024, 1536), (40, 60, 120)).save(b, "PNG"); return b.getvalue()


class T(unittest.TestCase):
    def setUp(self):
        self.saved = (P.C.song_dir, P.media_cfg.load, P.media_cfg.get_key, P.media_cfg.add_usage, P.IO.request_image)
        self.D = tempfile.mkdtemp()
        open(os.path.join(self.D, "title.txt"), "w", encoding="utf-8").write("पता ही ना चला (Pata Hi Na Chala)\n")
        open(os.path.join(self.D, "style.txt"), "w").write("warm lo-fi, soft piano")
        open(os.path.join(self.D, "lyrics.txt"), "w", encoding="utf-8").write("[Verse 1]\nline one\nline two\n")
        P.C.song_dir = lambda slug: self.D
        P.media_cfg.load = lambda: {"image_quality": "low", "image_size": "1152x2048", "max_run_usd": 5.0}
        P.media_cfg.get_key = lambda p: "sk-test"
        self.spent = []; P.media_cfg.add_usage = lambda openai_usd=0.0, eleven_seconds=0.0: self.spent.append(openai_usd)
        self.sent = []; P.IO.request_image = lambda prompt, q, key, size, model=None: (self.sent.append((prompt, size)), png())[1]

    def tearDown(self):
        (P.C.song_dir, P.media_cfg.load, P.media_cfg.get_key, P.media_cfg.add_usage, P.IO.request_image) = self.saved

    def test_default_prompt_comes_from_the_song_and_forbids_lettering(self):
        p = P.default_prompt("s")
        self.assertIn("Pata Hi Na Chala", p); self.assertIn("warm lo-fi", p); self.assertIn("line one", p); self.assertNotIn("[Verse 1]", p); self.assertIn("No text", p)

    def test_generate_sends_the_edited_prompt_charges_once_and_writes_poster_and_prompt(self):
        cost = P.generate("s", "My own prompt for a rainy window poster.")
        self.assertEqual(self.sent, [("My own prompt for a rainy window poster.", P.SIZE)]); self.assertEqual(self.spent, [cost])
        self.assertEqual(Image.open(os.path.join(self.D, "poster_2x3.png")).size, (P.W, P.H))
        self.assertTrue(os.path.isfile(os.path.join(self.D, "poster_art.png")))
        self.assertEqual(P.state("s")["prompt"], "My own prompt for a rainy window poster.")   # the next run starts from it
        self.assertTrue(P.state("s")["has"])

    def test_short_prompt_and_missing_key_spend_nothing(self):
        with self.assertRaises(ValueError): P.generate("s", "short")
        P.media_cfg.get_key = lambda p: ""
        with self.assertRaises(ValueError): P.generate("s", "A long enough prompt for a poster.")
        self.assertEqual((self.sent, self.spent), ([], []))

    def test_own_picture_becomes_the_poster_for_free_and_style_is_remembered(self):
        P.use_picture("s", png()); self.assertEqual((self.sent, self.spent), ([], []))
        self.assertEqual(Image.open(os.path.join(self.D, "poster_2x3.png")).size, (P.W, P.H))
        with self.assertRaises(ValueError): P.use_picture("s", b"not a picture")
        P.generate("s", "A long enough prompt for a poster.", "hand"); self.assertEqual(P.state("s")["style"], "hand")

    def test_title_redraw_is_free(self):
        P.generate("s", "A long enough prompt for a poster."); n = len(self.sent); P.typeset("s")
        self.assertEqual((len(self.sent), len(self.spent)), (n, 1))


if __name__ == "__main__":
    unittest.main()
