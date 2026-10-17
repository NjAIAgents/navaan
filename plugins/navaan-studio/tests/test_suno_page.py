import os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import suno_import as S

PAGE = '''<html><head><title>The Streets We Carry by NAVAAN | Suno</title></head><body>
<a href="/style/soft-pop">soft pop</a><a href="/style/cinematic">cinematic</a><a href="/style/soft-pop">soft pop</a>
<div><textarea class="custom-textarea block w-full" disabled="" maxLength="7500">[Intro &mdash; soft piano]

[Verse 1]

There was a quiet in those little streets,
Rain on the roof &amp; the evening falling slow.

[Chorus]

We carry the streets.</textarea></div></body></html>'''


class Page(unittest.TestCase):
    def test_title_lyrics_and_style_are_read_from_the_page_text(self):
        i = S.parse_page(PAGE)
        self.assertEqual(i["title"], "The Streets We Carry"); self.assertEqual(i["style"], "soft pop, cinematic")   # once each
        self.assertTrue(i["lyrics"].startswith("[Intro — soft piano]")); self.assertIn("Rain on the roof & the evening falling slow.", i["lyrics"]); self.assertIn("[Chorus]\n\nWe carry the streets.", i["lyrics"])   # entities decoded, labels kept
        self.assertEqual(S.parse_page("<html><title>x</title></html>"), {"title": "x", "lyrics": "", "style": ""})

    def _open(self, page=None, exc=None):
        def fake(req, timeout=0):
            if exc: raise exc
            r = mock.MagicMock(); r.__enter__.return_value.read.return_value = page.encode(); return r
        return mock.patch("urllib.request.urlopen", fake)

    def test_a_link_is_read_before_anything_is_created_and_the_refusals_are_sentences(self):
        import urllib.error
        with self._open(PAGE), mock.patch.object(S, "parse_ref", lambda s: ("abc", "https://suno.com/song/abc")): self.assertEqual(S.read_page("https://suno.com/song/abc")["title"], "The Streets We Carry")
        with self._open(exc=urllib.error.URLError("timed out")), mock.patch.object(S, "parse_ref", lambda s: ("abc", "https://suno.com/song/abc")):
            with self.assertRaises(ValueError) as c: S.read_page("https://suno.com/song/abc")
        self.assertIn("could not open that Suno link", str(c.exception)); self.assertIn("public song link", str(c.exception))
        with self._open("<html><title>x by y | Suno</title><textarea class=\"custom-textarea\">[Intro]</textarea></html>"), mock.patch.object(S, "parse_ref", lambda s: ("abc", "https://suno.com/song/abc")):
            with self.assertRaises(ValueError) as c: S.read_page("https://suno.com/song/abc")
        self.assertIn("could not find lyrics", str(c.exception))   # only section labels is not lyrics
        with self.assertRaises(ValueError): S.read_page("not a link")   # parse_ref's own refusal becomes a ValueError

    def test_what_the_page_gave_is_written_but_never_over_what_the_song_already_has(self):
        D = tempfile.mkdtemp()
        with mock.patch.object(S, "song_dir", lambda slug: D), mock.patch.object(S, "_meta", lambda p, required=False: {}), mock.patch.object(S, "save", lambda p, o: None):
            open(os.path.join(D, "title.txt"), "w").write("My own title\n")
            S.apply_page("s", {"title": "From Suno", "lyrics": "[Verse]\nline", "style": "soft pop"})
        self.assertEqual(open(os.path.join(D, "title.txt")).read().strip(), "My own title")   # kept
        self.assertEqual(open(os.path.join(D, "lyrics.txt")).read().strip(), "[Verse]\nline"); self.assertEqual(open(os.path.join(D, "style.txt")).read().strip(), "soft pop")


if __name__ == "__main__":
    unittest.main()
