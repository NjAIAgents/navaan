"""Author: Navjyot Nishant
Created: 2026-10-20
Last updated: 2026-10-20
Description: the song cover: a step of the pipeline that makes the cover in the modern look, an explicit way to make it again, and the bucket and catalog following it.
"""
import io, os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan as N
import media_cfg
import song_cover as SC
from PIL import Image


def png(w=1024, h=1024):
    b = io.BytesIO(); Image.new("RGB", (w, h), (40, 60, 120)).save(b, "PNG"); return b.getvalue()


def folder():
    D = tempfile.mkdtemp(); open(os.path.join(D, "title.txt"), "w", encoding="utf-8").write("Tere Hone Se\n"); open(os.path.join(D, "style.txt"), "w").write("soft pop, male vocals")
    open(os.path.join(D, "lyrics.txt"), "w").write("[Verse]\nline one\nline two\n"); return D


class Step(unittest.TestCase):
    def steps(self, D): return {s["id"]: s for s in N.song_picture_steps("s", D, media_cfg.load())}

    def test_the_cover_comes_after_the_pictures_before_the_poster_behind_the_credits_approval_and_says_what_it_costs(self):
        st = self.steps(tempfile.mkdtemp()); self.assertEqual(list(st), ["prompts", "pictures", "cover", "poster"])
        c = st["cover"]; self.assertEqual((c["before"], c["kind"]), ("credits", "script")); self.assertIn("cover_1x1.png", c["outputs"]); self.assertIn("thumb_16x9.jpg", c["outputs"])
        self.assertRegex(N.spend_what(c), r"^Make the cover with OpenAI \(1 picture, about \$\d+\.\d\d at \w+\)$")

    def test_it_is_done_when_a_cover_exists_or_the_videos_were_already_approved_and_not_before(self):
        D = tempfile.mkdtemp(); c = self.steps(D)["cover"]
        self.assertFalse(c["done"]({})); self.assertFalse(c["done"]({"approvals": {}}))
        self.assertTrue(c["done"]({"approvals": {"media": {"at": "x"}}}))   # a song made before this step existed is not sent back to spend
        open(os.path.join(D, "cover_1x1.png"), "wb").write(b"x"); self.assertTrue(self.steps(D)["cover"]["done"]({}))


class Make(unittest.TestCase):
    def setUp(self):
        self.D = folder(); self.sent = []; self.spent = []
        for p in (mock.patch.object(SC.C, "song_dir", lambda slug: self.D), mock.patch.object(SC.media_cfg, "load", lambda: {"image_quality": "low", "max_run_usd": 5.0}),
                  mock.patch.object(SC.media_cfg, "get_key", lambda k: "sk-test"), mock.patch.object(SC.media_cfg, "add_usage", lambda openai_usd=0.0, eleven_seconds=0.0: self.spent.append(openai_usd)),
                  mock.patch.object(SC.IO, "request_image", lambda prompt, q, key, size, model=None: (self.sent.append((prompt, size)), png())[1]),
                  mock.patch.object(SC.C, "item_load", lambda slug, default=None: {}), mock.patch.object(SC.C, "cfg", lambda k, d=None: d),
                  mock.patch.object(SC.MC, "song_dir", lambda slug: self.D), mock.patch.object(SC.MC, "cfg", lambda k, d=None: d)):   # make_cover imported these by name
            p.start(); self.addCleanup(p.stop)

    def test_the_prompt_asks_for_the_modern_look_from_the_song_and_no_lettering(self):
        p = SC.default_prompt("s")
        self.assertIn(SC.MC.MODERN_LOOK, p); self.assertIn("Tere Hone Se", p); self.assertIn("line one", p); self.assertIn("No text", p); self.assertIn("man", p)
        self.assertNotIn("painterly", p.replace(SC.MC.MODERN_LOOK, ""))   # the old direction is not in the song's part of the prompt

    def test_making_the_cover_writes_the_art_the_three_covers_and_the_prompt_and_spends_once(self):
        open(os.path.join(self.D, "cover_art.jpg"), "wb").write(b"old flow art")   # art found first would otherwise win over the new one
        cost = SC.generate("s", "My idea for a modern cover, one strong form.")
        self.assertEqual(self.sent, [("My idea for a modern cover, one strong form.", SC.SIZE)]); self.assertEqual(self.spent, [cost])
        for n in ("cover_art.png", "cover_1x1.png", "cover_16x9.png", "thumb_16x9.jpg", "cover_prompt.txt"): self.assertTrue(os.path.isfile(os.path.join(self.D, n)), n)
        self.assertFalse(os.path.exists(os.path.join(self.D, "cover_art.jpg"))); self.assertEqual(Image.open(os.path.join(self.D, "cover_1x1.png")).size, (1080, 1080))
        with self.assertRaises(ValueError): SC.generate("s", "short")
        self.assertEqual(len(self.sent), 1)   # nothing more was sent or spent

    def test_the_step_command_redraws_for_free_when_art_exists_and_paints_from_the_saved_prompt_otherwise(self):
        with mock.patch.object(SC, "generate", lambda slug, prompt: (self.sent.append(prompt), 0.04)[1]):
            self.assertEqual(SC.main(["s"]), 0); self.assertIn("Tere Hone Se", self.sent[0])   # no art yet: made from the song
            open(os.path.join(self.D, "cover_prompt.txt"), "w").write("A lantern on a quiet river, square cover, no text.\n"); self.sent.clear()
            SC.main(["s"]); self.assertEqual(self.sent, ["A lantern on a quiet river, square cover, no text."])   # the card's prompt wins
            Image.open(io.BytesIO(png())).save(os.path.join(self.D, "cover_art.png")); self.sent.clear()
            self.assertEqual(SC.main(["s"]), 0); self.assertEqual(self.sent, []); self.assertTrue(os.path.isfile(os.path.join(self.D, "cover_1x1.png")))   # art is there: only the lettering, free

    def test_your_own_picture_becomes_the_cover_for_free_and_a_bad_file_is_refused(self):
        SC.use_picture("s", png(800, 600)); self.assertEqual(Image.open(os.path.join(self.D, "cover_1x1.png")).size, (1080, 1080)); self.assertEqual((self.sent, self.spent), ([], []))
        with self.assertRaises(ValueError): SC.use_picture("s", b"not a picture")

    def test_a_song_in_the_bucket_gets_the_new_cover_there_with_its_new_size_recorded(self):
        meta = {"cloud": {"verified": True, "prefix": "navaan/songs/s/", "objects": {"cover_1x1.png": {"size": 5}}}}; saved = []; put = {}
        import objstore, catalog_store as K
        with mock.patch.object(SC.C, "item_load", lambda slug, default=None: meta), mock.patch.object(SC.C, "item_save", lambda slug, m: saved.append(m)),              mock.patch.object(objstore, "put", lambda k, d, ct="x": put.__setitem__(k, d)), mock.patch.object(K, "set_picture", lambda *a: saved.append(a) or True):
            self.assertFalse(SC.published("s")); SC.generate("s", "My idea for a modern cover, one strong form.")
            data = open(os.path.join(self.D, "cover_1x1.png"), "rb").read()
            self.assertEqual(put, {"navaan/songs/s/cover_1x1.png": data})   # in place of the earlier cover
            self.assertEqual(meta["cloud"]["objects"]["cover_1x1.png"]["size"], len(data))   # the catalog sync reads this: a stale size would bring the old picture back
            self.assertIn(("s", "cover", "navaan/songs/s/cover_1x1.png", "image/png", len(data)), saved); self.assertTrue(SC.published("s"))

    def test_a_song_not_in_the_bucket_keeps_the_cover_and_publishing_it_says_why(self):
        SC.generate("s", "My idea for a modern cover, one strong form.")   # no cloud record: nothing to replace, and no error
        self.assertTrue(os.path.isfile(os.path.join(self.D, "cover_1x1.png")))
        with self.assertRaises(ValueError): SC.publish("s")


if __name__ == "__main__":
    unittest.main()
