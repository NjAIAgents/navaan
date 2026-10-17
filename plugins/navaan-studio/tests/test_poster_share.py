"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: the poster as the picture a shared link previews: publishing it to the bucket, its own cached size, and the share pages that point at it.
"""
import io, os, sys, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
from PIL import Image
from test_media import Base, png
import share_page


class Publish(Base):
    def poster(self, slug="song-001", colour=(30, 60, 150)):
        D = os.path.join(self.C.songs_root(), slug)
        with open(os.path.join(D, "poster_2x3.png"), "wb") as f: f.write(png(400, 600, colour))
        return D

    def test_the_poster_goes_to_the_bucket_is_registered_and_is_served_in_its_own_size(self):
        import poster as P
        self.song(); self.poster()
        self.assertEqual(P.published("song-001"), {"published": False, "stale": False, "can_publish": True})
        r = P.publish("song-001"); self.assertEqual(r["key"], "navaan/songs/song-001/poster_2x3.png"); self.assertIn(r["key"], self.bucket)
        self.assertEqual(P.published("song-001"), {"published": True, "stale": False, "can_publish": True})
        data, etag, mime = self.M.variant("song-001", 320, "jpg", "poster"); self.assertEqual(mime, "image/jpeg")
        im = Image.open(io.BytesIO(data)); self.assertEqual(max(im.size), 320); self.assertLess(im.width, im.height)   # still portrait
        self.assertNotEqual(etag, self.M.variant("song-001", 320, "jpg")[1])   # not the cover's cache entry
        self.assertIsNone(self.M.variant("ghost", 320, "jpg", "poster")); self.assertRaises(ValueError, self.M.variant, "song-001", 320, "jpg", "banner")
        self.assertIsNone(self.K.poster_asset("song-001").get("dominant_colour"))   # the cover's colour and size facts are not recorded for a poster

    def test_a_poster_made_after_publishing_is_marked_stale_and_publishing_again_replaces_it(self):
        import poster as P
        self.song(); D = self.poster(); P.publish("song-001")
        with open(os.path.join(D, "poster_2x3.png"), "wb") as f: f.write(png(400, 600, (200, 10, 10)) + b"\0" * 50)   # a new poster, a different size
        self.assertTrue(P.published("song-001")["stale"])
        old = self.M.variant("song-001", 320, "jpg", "poster")[1]
        P.publish("song-001"); self.assertFalse(P.published("song-001")["stale"])
        self.assertNotEqual(self.M.variant("song-001", 320, "jpg", "poster")[1], old)   # a new size gives a new cache entry

    def test_it_says_why_it_cannot_publish(self):
        import poster as P
        self.song()
        with self.assertRaises(ValueError) as c: P.publish("song-001")
        self.assertIn("Make the poster first", str(c.exception))
        D = self.poster(); import json
        m = json.load(open(os.path.join(D, "meta.json"))); m["cloud"]["verified"] = False; json.dump(m, open(os.path.join(D, "meta.json"), "w")); self.K.sync_item("song-001")
        with self.assertRaises(ValueError) as c: P.publish("song-001")
        self.assertIn("not in the bucket yet", str(c.exception)); self.assertFalse(P.published("song-001")["can_publish"])
        with self.assertRaises(ValueError) as c: P.publish("ghost")
        self.assertIn("no such song", str(c.exception))


class Pages(unittest.TestCase):
    def test_the_share_page_and_the_clip_page_preview_the_poster_when_there_is_one_and_the_cover_when_not(self):
        t = {"slug": "song-001", "title": "Tere Hone Se", "start_ms": 0}
        self.assertIn("/img/song-001/1280.jpg", share_page.render(t, "tok12345", "https://navaan.online"))
        page = share_page.render(t, "tok12345", "https://navaan.online", has_cover=False, has_poster=True)
        self.assertIn('property="og:image" content="https://navaan.online/img/song-001/poster-1280.jpg"', page); self.assertNotIn("/img/song-001/1280.jpg", page)
        self.assertIn("/img/song-001/1280.jpg", share_page.render_clip("song-001", "Tere Hone Se", "tok12345", "https://navaan.online"))
        self.assertIn("/img/song-001/poster-1280.jpg", share_page.render_clip("song-001", "Tere Hone Se", "tok12345", "https://navaan.online", has_poster=True))


if __name__ == "__main__":
    unittest.main()
