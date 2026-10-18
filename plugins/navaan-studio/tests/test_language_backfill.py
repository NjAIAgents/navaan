"""Author: Navjyot Nishant
Created: 2026-10-18
Last updated: 2026-10-18
Description: the songs with no language: what the lyrics can say, what they cannot, and that applying it fills the catalog.
"""
import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_catalog import Base
import _pgenv  # noqa: F401


class Backfill(Base):
    def setUp(self):
        super().setUp()
        import language_backfill as B
        self.B = B

    def make(self, slug, title, lyrics, tags=None):
        D = self.song(slug, title); open(os.path.join(D, "lyrics.txt"), "w", encoding="utf-8").write(lyrics)
        if tags is not None: json.dump(tags, open(os.path.join(D, "tags.json"), "w"))
        self.K.sync_item(slug); return D

    def test_the_lyrics_say_english_only_for_latin_letters(self):
        g = self.B.guess
        self.assertEqual(g("[Verse]\nThere was a quiet in those little streets"), "English"); self.assertEqual(g("तेरे होने से\nसब कुछ है"), ""); self.assertEqual(g(""), ""); self.assertEqual(g("[Intro]"), "")
        self.assertEqual(g("तेरे होने से सब कुछ है तुम्हारे साथ\nrang"), "")   # mostly Devanagari: not guessed

    def test_the_plan_lists_only_tracks_with_no_language_and_says_which_it_can_set(self):
        self.make("song-001", "English One", "A quiet street at night\nWe carry it home"); self.make("song-002", "हिंदी", "तेरे होने से\nसब कुछ है"); self.make("song-003", "Has one", "x y z", tags={"language": "Hindi"})
        p = {i["slug"]: (i["language"], i["action"]) for i in self.B.plan()}
        self.assertEqual(p, {"song-001": ("English", "set"), "song-002": ("", "needs you")})   # song-003 already has a language

    def test_applying_writes_tags_and_the_catalog_and_leaves_the_rest_for_the_owner(self):
        D = self.make("song-001", "English One", "A quiet street at night\nWe carry it home"); self.make("song-002", "हिंदी", "तेरे होने से\nसब कुछ है")
        self.assertEqual(self.B.main(["--apply"]), 0)
        self.assertEqual(json.load(open(os.path.join(D, "tags.json")))["language"], "English")
        lang = lambda s: self.K._conn().execute("SELECT language FROM tracks WHERE slug = ?", (s,)).fetchone()["language"]
        self.assertEqual(lang("song-001"), "English"); self.assertIn(lang("song-002"), (None, ""))   # Devanagari is left alone
        self.assertEqual([i["slug"] for i in self.B.plan()], ["song-002"])   # only the one that needs the owner is left
        self.assertEqual(self.B.main([]), 0)   # a plain run changes nothing and lists it

    def test_a_song_whose_folder_is_gone_gets_its_language_in_the_catalog_row(self):
        import shutil
        D = self.make("song-001", "English One", "A quiet street at night\nWe carry it home"); shutil.rmtree(D)
        self.assertEqual(self.B.apply_one({"slug": "song-001", "studio_slug": "song-001", "language": "English"}), "catalog")
        self.assertEqual(self.K._conn().execute("SELECT language FROM tracks WHERE slug = 'song-001'").fetchone()["language"], "English")


if __name__ == "__main__":
    unittest.main()
