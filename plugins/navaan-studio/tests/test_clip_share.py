import os, sys, subprocess, tempfile, shutil, json, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import clip_share as CS

HAVE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def mp3(seconds=40):
    p = os.path.join(tempfile.mkdtemp(), "a.mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=%d" % seconds, "-c:a", "libmp3lame", p], check=True)
    return open(p, "rb").read()


class Token(unittest.TestCase):
    def test_the_clip_page_can_be_passed_on_download_always_share_where_the_browser_has_it_and_the_preview_tags_stay(self):
        import share_page
        h = share_page.render_clip("song-001", 'Tere "Hone" Se', "song-001-42-15", "https://navaan.online")
        self.assertIn('href="/c/song-001-42-15.mp4" download="song-001-clip.mp4"', h)   # a plain link: works with no script, on a computer too
        js = h.split("<script>")[1].split("</script>")[0]; self.assertLess(js.index("fetch(d.vid)"), js.index("b.onclick")); self.assertNotIn("fetch", js.split("b.onclick")[1])   # the clip is fetched on load; pressing Share awaits nothing, so an iPhone opens the sheet
        self.assertIn('id="sh"', h); self.assertIn("hidden", h.split('id="sh"')[1].split(">")[0])   # the Share button is shown only by the script, where navigator.share exists
        self.assertIn('data-page="https://navaan.online/c/song-001-42-15"', h); self.assertIn("&quot;Hone&quot;", h)   # the title is escaped into the attribute
        self.assertIn('og:video" content="https://navaan.online/c/song-001-42-15.mp4"', h); self.assertIn('property="og:image"', h)   # the link preview still works
        self.assertIn("#NAVAAN", h)   # the caption that travels carries the tag

    def test_a_token_is_the_whole_recipe_and_nothing_else_parses(self):
        self.assertEqual(CS.parse(CS.token("song-002", 45, 15)), ("song-002", 45, 15)); self.assertEqual(CS.parse("a-b-c-0-30"), ("a-b-c", 0, 30))
        for bad in ("", "song-002", "song-002-45-20", "song-002-45-15.mp4", "../x-1-15"):
            with self.assertRaises(ValueError, msg=bad): CS.parse(bad)


class Rules(unittest.TestCase):
    def test_only_15_or_30_seconds_inside_the_song_of_a_song_a_visitor_may_play(self):
        with mock.patch.object(CS.K, "play_key", lambda s, confirmed_only=False: "k" if s == "song-001" else None):
            CS.check("song-001", 0, 15); CS.check("song-001", 120, 30)
            with self.assertRaises(ValueError): CS.check("song-001", 0, 20)
            with self.assertRaises(ValueError): CS.check("song-001", -1, 15)
            with self.assertRaises(ValueError): CS.check("song-001", 99999, 15)
            with self.assertRaises(LookupError): CS.check("song-002", 0, 15)   # not published or not confirmed


@unittest.skipUnless(HAVE, "ffmpeg is not installed")
class Make(unittest.TestCase):
    def setUp(self):
        self.cache = tempfile.mkdtemp(); self.env = mock.patch.dict(os.environ, {"NAVAAN_CACHE_DIR": self.cache}); self.env.start()
        self.audio = mp3(); self.gets = []
        self.ps = [mock.patch.object(CS.K, "play_key", lambda s, confirmed_only=False: "navaan/songs/song-001/final.mp3"), mock.patch.object(CS.K, "track_view", lambda s, a=False: {"title": "Tere Hone Se"}),
                   mock.patch.object(CS.media, "variant", lambda *a: None), mock.patch.object(CS.objstore, "get", lambda k: (self.gets.append(k), self.audio)[1])]
        for p in self.ps: p.start()

    def tearDown(self):
        for p in self.ps: p.stop()
        self.env.stop()

    def probe(self, f):
        j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", f], capture_output=True, text=True).stdout)
        return j

    def test_the_clip_is_a_vertical_video_of_the_asked_length_with_the_songs_sound_and_is_made_once(self):
        out = CS.make("song-001", 5, 15); j = self.probe(out)
        v = next(s for s in j["streams"] if s["codec_type"] == "video"); a = next(s for s in j["streams"] if s["codec_type"] == "audio")
        self.assertEqual((v["width"], v["height"]), (1080, 1920)); self.assertEqual(a["codec_name"], "aac"); self.assertAlmostEqual(float(j["format"]["duration"]), 15, delta=0.5)
        self.assertLess(os.path.getsize(out), 4_000_000)
        self.assertEqual(CS.make("song-001", 5, 15), out); self.assertEqual(len(self.gets), 1)   # the second ask is the cache

    def test_a_clip_that_starts_past_the_end_is_refused_not_made_silent(self):
        with self.assertRaises(ValueError): CS.make("song-001", 3000, 15)


if __name__ == "__main__":
    unittest.main()
