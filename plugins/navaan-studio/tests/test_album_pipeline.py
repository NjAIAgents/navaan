import json, os, sys, io, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_catalog import Base   # the same throwaway project and catalog
import _pgenv  # noqa: F401
from PIL import Image


def png(w=1024, h=1024):
    b = io.BytesIO(); Image.new("RGB", (w, h), (40, 60, 120)).save(b, "PNG"); return b.getvalue()


class Albums(Base):
    def setUp(self):
        super().setUp()
        import album_pipeline as A, media_cfg
        self.A, self.M = A, media_cfg
        self.saved = (A.media_cfg.load, A.media_cfg.get_key, A.media_cfg.add_usage, A.IO.request_image)
        A.media_cfg.load = lambda: {"image_quality": "low", "max_run_usd": 5.0}; A.media_cfg.get_key = lambda p: "sk-test"
        self.spent = []; A.media_cfg.add_usage = lambda openai_usd=0.0, eleven_seconds=0.0: self.spent.append(openai_usd)
        self.sent = []; A.IO.request_image = lambda prompt, q, key, size, model=None: (self.sent.append((prompt, size)), png())[1]
        self.addCleanup(lambda: (setattr(A.media_cfg, "load", self.saved[0]), setattr(A.media_cfg, "get_key", self.saved[1]), setattr(A.media_cfg, "add_usage", self.saved[2]), setattr(A.IO, "request_image", self.saved[3])))
        self.song("song-001", "Tere Hone Se", extra={"mood": "dusk"}); self.song("song-002", "Pata Hi Na Chala", extra={"mood": "night"})
        for s in ("song-001", "song-002"): self.K.sync_item(s)
        self.slug = self.K.save_album("", "Raat Ke Baad", "album"); self.K.reorder(self.slug, ["song-001", "song-002"])

    def test_names_come_from_the_songs_and_need_two_songs(self):
        seen = {}
        def runner(prompt): seen["p"] = prompt; return json.dumps({"names": [{"name": "Raat Ke Baad", "why": "after the night"}, {"name": "Raat Ke Baad", "why": "dup"}, {"name": "Dhoop", "why": "light"}]})
        out = self.A.suggest_names(["song-001", "song-002"], runner=runner)
        self.assertEqual([o["name"] for o in out], ["Raat Ke Baad", "Dhoop"])   # a repeat is dropped
        self.assertIn("Tere Hone Se", seen["p"]); self.assertIn("dusk", seen["p"]); self.assertIn("line one", seen["p"])
        with self.assertRaises(ValueError): self.A.suggest_names(["song-001"], runner=runner)
        with self.assertRaises(RuntimeError): self.A.suggest_names(["song-001", "song-002"], runner=lambda p: "no json here")

    def test_the_cover_prompt_starts_from_the_album_and_is_what_gets_sent(self):
        st = self.A.cover_state(self.slug)
        self.assertIn("Raat Ke Baad", st["prompt"]); self.assertIn("Tere Hone Se", st["prompt"]); self.assertIn("dusk", st["prompt"]); self.assertIn("No text", st["prompt"]); self.assertFalse(st["has"])
        cost = self.A.generate_cover(self.slug, "My own idea for a rainy window cover art.", "hand")
        self.assertEqual(self.sent, [("My own idea for a rainy window cover art.", self.A.SIZE)]); self.assertEqual(self.spent, [cost])
        d = self.A.album_dir(self.slug)
        self.assertEqual(Image.open(os.path.join(d, "cover_1x1.png")).size, (self.A.W, self.A.W)); self.assertTrue(os.path.isfile(os.path.join(d, "cover_art.png")))
        st = self.A.cover_state(self.slug); self.assertTrue(st["has"]); self.assertEqual((st["prompt"], st["style"]), ("My own idea for a rainy window cover art.", "hand"))

    def test_short_prompt_missing_key_and_unknown_album_spend_nothing(self):
        with self.assertRaises(ValueError): self.A.generate_cover(self.slug, "short")
        self.A.media_cfg.get_key = lambda p: ""
        with self.assertRaises(ValueError): self.A.generate_cover(self.slug, "A long enough prompt for a cover.")
        self.A.media_cfg.get_key = lambda p: "sk-test"
        with self.assertRaises(LookupError): self.A.generate_cover("no-such-album", "A long enough prompt for a cover.")
        with self.assertRaises(ValueError): self.A.album_dir("../escape")
        self.assertEqual((self.sent, self.spent), ([], []))

    def test_your_own_picture_is_free_and_redrawing_the_title_is_free(self):
        self.A.use_picture(self.slug, png(800, 600)); self.assertEqual(Image.open(os.path.join(self.A.album_dir(self.slug), "cover_1x1.png")).size, (self.A.W, self.A.W))
        with self.assertRaises(ValueError): self.A.use_picture(self.slug, b"not a picture")
        self.A.typeset(self.slug, style="brush"); self.assertEqual((self.sent, self.spent), ([], []))


if __name__ == "__main__":
    unittest.main()
