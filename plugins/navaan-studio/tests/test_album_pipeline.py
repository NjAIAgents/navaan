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
        import objstore, media
        from unittest import mock
        self.bucket = {}; self.M2 = media
        for name, fn in (("put", lambda key, data, ct="x": self.bucket.__setitem__(key, data)), ("get", lambda key: self.bucket[key])):
            pt = mock.patch.object(objstore, name, fn); pt.start(); self.addCleanup(pt.stop)
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

    def test_names_are_asked_for_as_album_titles_not_playlist_names_and_playlist_like_ones_are_dropped(self):
        seen = {}
        def runner(prompt): seen["p"] = prompt; return json.dumps({"names": [{"name": "Chill Vibes", "why": "x"}, {"name": "Late Night Mix", "why": "x"}, {"name": "Best of 2026", "why": "x"}, {"name": "Rumours of Rain", "why": "the weather the songs share"}, {"name": "Dhoop Ke Baad", "why": "light after"}, {"name": "Songs for Dusk", "why": "x"}]})
        out = self.A.suggest_names(["song-001", "song-002"], runner=runner)
        self.assertEqual([o["name"] for o in out], ["Rumours of Rain", "Dhoop Ke Baad"])   # only the record-like titles are kept
        for w in ("naming a record", "not the name of a playlist", "point of view", "Do NOT use playlist words", "Do not name the genre"): self.assertIn(w, seen["p"])
        out = self.A.suggest_names(["song-001", "song-002"], runner=lambda p: json.dumps({"names": [{"name": "Chill Mix", "why": "x"}]}))
        self.assertEqual([o["name"] for o in out], ["Chill Mix"])   # nothing else came back, so the owner still gets something to pick from or rewrite
        for bad in ("Chill Vibes", "Greatest Hits", "Best of NAVAAN", "Playlist One", "Rain Songs", "Vol. 2", "2026", "Top 10"): self.assertTrue(self.A.playlist_like(bad), bad)
        for good in ("25", "21", "1989 Skies".replace("1989 ", "Nine "), "Rumours", "Kind of Blue", "Dil Ki Baat", "Raat Ke Baad", "Mixed Feelings, Clear Skies".replace("Mixed", "Tangled"), "Hits Different".replace("Hits", "Struck")): self.assertFalse(self.A.playlist_like(good), good)

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

    def test_the_default_prompt_and_lettering_are_modern_and_an_owner_edit_is_kept(self):
        import make_cover as M
        st = self.A.cover_state(self.slug); self.assertIn(M.MODERN_LOOK, st["prompt"]); self.assertNotIn("Cinematic, painterly", st["prompt"]); self.assertIn("Not painterly", st["prompt"])
        self.assertEqual((st["style"], st["styles"][0]), ("modern", "modern")); self.assertIn("bold", st["styles"], "the display fonts stay as choices")
        self.A.generate_cover(self.slug, "My own idea for a rainy window cover art.")   # no style given: the modern one
        d = self.A.album_dir(self.slug); self.assertEqual(open(os.path.join(d, "cover_style.txt")).read().strip(), "modern"); self.assertEqual(Image.open(os.path.join(d, "cover_1x1.png")).size, (self.A.W, self.A.W))
        self.assertEqual(self.A.cover_state(self.slug)["prompt"], "My own idea for a rainy window cover art.")   # an edited prompt is never changed

    def test_a_made_cover_is_published_and_the_album_shows_it_once_it_is_published(self):
        self.assertIsNone(self.K.albums()[0]["art"]); self.assertFalse(self.A.cover_state(self.slug)["published"])
        self.A.generate_cover(self.slug, "My own idea for a rainy window cover art.", "hand")
        key = "navaan/albums/%s/cover_1x1.png" % self.slug
        self.assertEqual(self.bucket[key], open(os.path.join(self.A.album_dir(self.slug), "cover_1x1.png"), "rb").read())   # the bucket has what the studio made
        a = next(x for x in self.K.albums() if x["slug"] == self.slug)
        self.assertEqual(a["art"]["v"], len(self.bucket[key])); self.assertTrue(self.A.cover_state(self.slug)["published"])
        self.assertIsNone(self.M2.variant(self.slug, 320, "webp", "album"))   # a draft album's cover is not for listeners
        self.K.save_album(self.slug, "Raat Ke Baad", "album", "published")
        data, _, mime = self.M2.variant(self.slug, 320, "webp", "album")
        self.assertEqual(mime, "image/webp"); self.assertLessEqual(max(Image.open(io.BytesIO(data)).size), 320)
        self.assertEqual(self.K.album_cover_asset(self.slug)["dominant_colour"], next(x for x in self.K.albums() if x["slug"] == self.slug)["art"]["colour"])   # the first resize recorded the colour
        self.assertIsNone(self.M2.variant("no-such-album", 320, "webp", "album"))

    def test_a_new_picture_replaces_the_published_one_and_a_failed_publish_keeps_the_cover(self):
        self.A.use_picture(self.slug, png(800, 600)); first = self.K.album_cover_asset
        self.K.save_album(self.slug, "Raat Ke Baad", "album", "published"); old = first(self.slug)
        self.A.typeset(self.slug, style="brush"); new = first(self.slug)
        self.assertNotEqual(old["id"], new["id"])   # a new row, so the sizes cut from the old picture are not served for the new one
        def boom(key, data, ct="x"): raise RuntimeError("bucket down")
        from unittest import mock
        import objstore
        with mock.patch.object(objstore, "put", boom):
            self.A.typeset(self.slug, style="bold")   # does not raise: the cover is made
            self.assertFalse(self.A.cover_state(self.slug)["published"])   # but the studio can say it is not on the site
        self.A.publish(self.slug); self.assertTrue(self.A.cover_state(self.slug)["published"])

    def test_publishing_needs_a_made_cover_and_deleting_the_album_removes_its_asset(self):
        with self.assertRaises(ValueError): self.A.publish(self.slug)
        self.A.use_picture(self.slug, png(300, 300)); self.assertTrue(self.K.delete_album(self.slug))
        n = self.K._conn().execute("SELECT count(*) AS n FROM assets WHERE owner_kind = 'album'").fetchone()["n"]; self.assertEqual(n, 0)

    def test_an_album_is_shared_only_when_published_with_a_song_a_listener_may_hear_and_the_link_lists_only_those(self):
        K = self.K
        with self.assertRaises(LookupError): K.create_album_share(self.slug, "owner")   # a draft album has no link
        K.save_album(self.slug, "Raat Ke Baad", "album", "published")
        with self.assertRaises(ValueError): K.create_album_share(self.slug, "owner")   # published, but no song has a confirmed licence yet
        with self.assertRaises(LookupError): K.create_album_share("no-such-album", "owner")
        K.set_license("song-001", "confirmed", "owner", "paid plan")
        tok = K.create_album_share(self.slug, "owner")
        a = K.open_album_share(tok, count=True)
        self.assertEqual((a["slug"], a["artist"], [t["slug"] for t in a["tracks"]]), (self.slug, "NAVAAN", ["song-001"]))   # song-002 is not confirmed, so it is not on the page or playable
        self.assertEqual(K.open_share(tok), None)   # an album's token is not a song's
        K.set_license("song-002", "confirmed", "owner", "paid plan"); self.assertEqual([t["slug"] for t in K.open_album_share(tok)["tracks"]], ["song-001", "song-002"])
        self.assertEqual(K._conn().execute("SELECT opens FROM share_links WHERE token = ?", (tok,)).fetchone()["opens"], 1)
        self.assertTrue(K.revoke_share(tok, "owner")); self.assertIsNone(K.open_album_share(tok))
        tok = K.create_album_share(self.slug, "owner"); K.save_album(self.slug, "Raat Ke Baad", "album", "draft"); self.assertIsNone(K.open_album_share(tok))   # unpublished again: the link stops

    def test_the_album_page_names_the_artist_lists_the_songs_with_players_and_escapes_everything(self):
        import share_page
        al = {"slug": "raat", "title": "Raat <b>Ke</b> Baad", "artist": "NAVAAN", "description": "late <i>night</i>", "art": {"colour": "#445566"}, "tracks": [{"slug": "song-001", "title": "One & Two"}, {"slug": "song-002", "title": "Three"}]}
        h = share_page.render_album(al, "tok123456", "https://navaan.online", None, True)
        for want in ("Album by NAVAAN", "Raat &lt;b&gt;Ke&lt;/b&gt; Baad", "One &amp; Two", 'src="/s/tok123456/play/song-001.mp3"', 'src="/s/tok123456/play/song-002.mp3"', 'og:type" content="music.album"',
                     "an album by NAVAAN. Listen free on NAVAAN.", "https://navaan.online/img/album/raat/1280.jpg", 'href="/app/album/raat"', "late &lt;i&gt;night&lt;/i&gt;"): self.assertIn(want, h)
        self.assertNotIn("<b>Ke", h); self.assertNotIn("<script", h)
        self.assertIn("/img/song-001/1280.jpg", share_page.render_album({**al, "art": None}, "tok123456", "https://navaan.online", "song-001", False))   # no cover of its own: the first song's
        self.assertNotIn("og:image", share_page.render_album({**al, "art": None}, "tok123456", "https://navaan.online", None, False))


if __name__ == "__main__":
    unittest.main()
