"""Author: Navjyot Nishant
Created: 2026-10-23
Last updated: 2026-10-23
Description: every picture step sends the key of the picture maker chosen in Settings (OpenAI or Muse), not always OpenAI's.

With Muse chosen, five steps (the picture per beat, the Aha-lorithm pictures, the poster, the song cover and the album cover) still fetched the OpenAI key and sent it to Muse, which
answered "HTTP 401 Unauthorized" on a key that works (insp-010). Each test saves two different keys, picks an engine, and checks which key reaches the image API.
"""
import json, os, sys, tempfile, unittest
from unittest import mock
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import _pgenv  # noqa: F401  (a throwaway database schema per path, for the items made below)

OPENAI_KEY, MUSE_KEY = "sk-" + "a" * 40, "LLM_" + "b" * 40


class Stop(Exception): pass


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.conf = os.path.join(self.tmp.name, "conf"); os.makedirs(self.conf)
        os.environ["NAVAAN_ROOT"] = self.tmp.name; os.environ["NAVAAN_CONF_DIR"] = self.conf
        self.addCleanup(os.environ.pop, "NAVAAN_CONF_DIR", None)
        open(os.path.join(self.conf, "openai.env"), "w").write("OPENAI_API_KEY=%s\n" % OPENAI_KEY)
        open(os.path.join(self.conf, "muse.env"), "w").write("MUSE_API_KEY=%s\n" % MUSE_KEY)
        for k in ("OPENAI_API_KEY", "MUSE_API_KEY"):
            self.enterContext(mock.patch.dict(os.environ)); os.environ.pop(k, None)
        self.songs = os.path.join(self.tmp.name, "songs"); os.makedirs(self.songs, exist_ok=True)

    def engine(self, name):
        json.dump({"image_engine": name}, open(os.path.join(self.conf, "media.json"), "w"))

    def sent_key(self, fn, *a, **k):
        """Run fn with the image API replaced by one that records the key it was given; returns that key."""
        import image_openai as I
        seen = []
        def fake(prompt, quality, key, *args, **kw): seen.append(key); raise Stop()
        with mock.patch.object(I, "request_image", side_effect=fake), mock.patch("builtins.print"):
            try: fn(*a, **k)
            except Stop: pass
        self.assertEqual(len(seen), 1, "the image API was asked once")
        return seen[0]

    def item(self, slug):
        d = os.path.join(self.songs, slug); os.makedirs(d, exist_ok=True); return d


class Steps(Env):
    PROMPT = "A lone person seen from behind on an empty pier at dusk, soft fog, photographic."

    def beat_item(self):
        import new_song, beat_plan as B
        slug = new_song.create(None, "inspiration", ""); D = os.path.join(self.songs, slug)
        L = ["You were never meant to carry everything.", "Not their expectations.", "Not their guilt.", "Let it go.", "Your peace matters too."]
        json.dump({"text": " ".join(L), "lines": L, "language": "en"}, open(os.path.join(D, "quote.json"), "w"))
        json.dump({"look": "Quiet dusk photography, cold teal and amber, soft grain.", "beats": [{"lines": [0], "prompt": self.PROMPT}, {"lines": [1, 2], "prompt": self.PROMPT}, {"lines": [3, 4], "prompt": self.PROMPT}]}, open(os.path.join(D, B.PLAN), "w"))
        return slug

    def run_beats(self):
        import beat_pictures as P
        slug = self.beat_item(); return self.sent_key(P.main, [slug])

    def run_aha(self):
        import aha_pictures as P
        D = self.item("aha-001"); L = ["Why AI sounds so sure.", "It predicts the next word.", "Sure is not true."]
        json.dump({"text": " ".join(L), "lines": L, "captions": L, "pictures": [self.PROMPT] * 3, "look": "Quiet dusk photography, cold teal and amber, soft grain."}, open(os.path.join(D, "quote.json"), "w"))
        return self.sent_key(P.main, ["aha-001"])

    def run_poster(self):
        import poster as P; self.item("song-001"); return self.sent_key(P.generate, "song-001", self.PROMPT)

    def run_cover(self):
        import song_cover as P; self.item("song-001"); return self.sent_key(P.generate, "song-001", self.PROMPT)

    def test_with_muse_chosen_every_step_sends_the_muse_key(self):
        self.engine("muse")
        for name in ("run_beats", "run_aha", "run_poster", "run_cover"):
            with self.subTest(step=name): self.assertEqual(getattr(self, name)(), MUSE_KEY)

    def test_with_openai_chosen_or_nothing_chosen_every_step_sends_the_openai_key(self):
        for engine in ("openai", None):
            if engine: self.engine(engine)
            for name in ("run_beats", "run_aha", "run_poster", "run_cover"):
                with self.subTest(engine=engine, step=name): self.assertEqual(getattr(self, name)(), OPENAI_KEY)

    def test_with_muse_chosen_but_only_an_openai_key_saved_the_step_says_muse_is_missing_and_sends_nothing(self):
        import beat_pictures as P, poster, image_openai as I
        self.engine("muse"); os.remove(os.path.join(self.conf, "muse.env")); slug = self.beat_item()
        with mock.patch.object(I, "request_image", side_effect=AssertionError("must not be called")), mock.patch("builtins.print"):
            with self.assertRaises(SystemExit) as e: P.main([slug])
            self.assertIn("no Muse key", str(e.exception))
            self.item("song-001")
            with self.assertRaises(ValueError) as e: poster.generate("song-001", self.PROMPT)
            self.assertIn("No Muse key", str(e.exception))

    def test_the_key_saved_flag_on_the_cards_follows_the_chosen_picture_maker(self):
        import poster, song_cover
        self.item("song-001"); os.remove(os.path.join(self.conf, "muse.env")); self.engine("muse")
        self.assertFalse(poster.state("song-001")["key"]); self.assertFalse(song_cover.state("song-001")["key"])   # an OpenAI key is saved, but Muse is chosen and has none
        self.engine("openai"); self.assertTrue(poster.state("song-001")["key"]); self.assertTrue(song_cover.state("song-001")["key"])


class Album(Env):
    def test_the_album_cover_sends_the_key_of_the_chosen_picture_maker_and_the_card_flag_follows_it(self):
        import album_pipeline as A
        with mock.patch.object(A, "_album", return_value={"title": "T", "slug": "alb-1", "tracks": []}), mock.patch.object(A, "album_dir", return_value=self.item("alb-1")):
            for engine, want in (("muse", MUSE_KEY), ("openai", OPENAI_KEY)):
                self.engine(engine)
                with self.subTest(engine=engine): self.assertEqual(self.sent_key(A.generate_cover, "alb-1", "A calm cover of a quiet street at dusk, soft grain."), want)
            os.remove(os.path.join(self.conf, "muse.env")); self.engine("muse")
            self.assertFalse(A.cover_state("alb-1")["key"])


if __name__ == "__main__":
    unittest.main()
