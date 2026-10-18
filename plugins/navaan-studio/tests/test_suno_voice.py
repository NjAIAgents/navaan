"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: the Suno song's own sound as an inspiration's narration: the page's video link, the checks on the download, and what attaching it writes.
"""
import os, sys, shutil, subprocess, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import suno_import as S
import narration

HAVE = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
URL = "https://cdn1.suno.ai/1f8a68df-a2bc-4d29-8a6a-f3ebbfa0509e.mp4"
PAGE = 'x,\\"video_url\\":\\"' + URL + '\\",\\"y\\"'   # the page's data escapes its quotes


def make_mp4(path, seconds=5, tone=True):
    src = "sine=frequency=330:duration=%d" % seconds if tone else "anullsrc=r=48000:cl=stereo"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=%d" % seconds, "-f", "lavfi", "-i", src, "-t", str(seconds), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", path]
    subprocess.run(cmd, check=True)


class Resp:
    def __init__(self, data, ctype="video/mp4", length=None):
        self.data, self._p = data, 0; self.headers = {"Content-Type": ctype, "Content-Length": str(len(data) if length is None else length)}
    def read(self, n=-1):
        c = self.data[self._p:] if n < 0 else self.data[self._p:self._p + n]; self._p += len(c); return c
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Link(unittest.TestCase):
    def test_the_video_link_comes_from_the_page_and_only_from_suno_servers(self):
        self.assertEqual(S.parse_video_url(PAGE), URL)
        self.assertEqual(S.parse_video_url(PAGE.replace("cdn1.suno.ai", "evil.example")), "")   # any other host is ignored
        self.assertEqual(S.parse_video_url("<html>no video here</html>"), "")
        self.assertEqual(S.parse_video_url(PAGE.replace("https://", "http://")), "")


@unittest.skipUnless(HAVE, "ffmpeg is needed")
class Download(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.t, True)
        self.good = os.path.join(self.t, "good.mp4"); make_mp4(self.good)
        self.work = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.work, True)

    def fetch(self, data, **kw):
        with mock.patch("urllib.request.urlopen", lambda req, timeout=0: Resp(data, **kw)): return S.fetch_voice(URL, self.work)

    def test_a_whole_playable_video_gives_its_sound_without_re_encoding(self):
        out = self.fetch(open(self.good, "rb").read())
        self.assertTrue(out.endswith("voice.m4a")); pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,codec_type", "-of", "csv=p=0", out], capture_output=True, text=True).stdout
        self.assertIn("aac,audio", pr); self.assertNotIn("video", pr)   # the sound only, the same aac stream

    def test_every_bad_download_is_refused_with_a_sentence(self):
        data = open(self.good, "rb").read()
        with self.assertRaises(ValueError) as c: S.fetch_voice("https://evil.example/a.mp4", self.work)
        self.assertIn("not on Suno's own servers", str(c.exception))
        with self.assertRaises(ValueError) as c: self.fetch(data, ctype="text/html")
        self.assertIn("instead of a video", str(c.exception))
        with self.assertRaises(ValueError) as c: self.fetch(data, length=S.MAX_VOICE_BYTES + 1)
        self.assertIn("over 40 MB", str(c.exception))
        with self.assertRaises(ValueError) as c: self.fetch(data[: len(data) // 2])   # cut off half way
        self.assertTrue(any(w in str(c.exception) for w in ("damaged", "no sound track")))
        with self.assertRaises(ValueError): self.fetch(b"<html>login</html>")   # not a media file at all
        silent = os.path.join(self.t, "silent.mp4"); make_mp4(silent, tone=False)
        with self.assertRaises(ValueError) as c: self.fetch(open(silent, "rb").read())
        self.assertIn("silent", str(c.exception))
        short = os.path.join(self.t, "short.mp4"); make_mp4(short, seconds=1)
        with self.assertRaises(ValueError) as c: self.fetch(open(short, "rb").read())
        self.assertIn("does not look like the song", str(c.exception))


@unittest.skipUnless(HAVE, "ffmpeg is needed")
class WholeSong(unittest.TestCase):
    def test_a_song_may_be_longer_than_a_voice_and_the_page_audio_is_ready_to_save(self):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d, True); big = os.path.join(d, "long.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=32x32:d=200:r=1", "-f", "lavfi", "-i", "sine=frequency=330:duration=200", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", big], check=True)
        data = open(big, "rb").read(); work = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, work, True)
        with mock.patch("urllib.request.urlopen", lambda req, timeout=0: Resp(data)):
            with self.assertRaises(ValueError) as c: S.fetch_voice(URL, work)   # a voice is at most 180 seconds
            self.assertIn("does not look like the song", str(c.exception))
            out = S.fetch_voice(URL, work, max_seconds=S.SONG_SECONDS, max_bytes=S.SONG_BYTES); self.assertTrue(os.path.getsize(out) > 50000)   # a song may be ten minutes
            info = {"title": "The Streets We Carry", "video_url": URL}
            name, b64 = S.page_audio(info)
        self.assertEqual(name, "The Streets We Carry.m4a"); raw, ext = S.check_upload(name, b64); self.assertEqual(ext, ".m4a")   # exactly what save_upload takes
        with self.assertRaises(ValueError) as c: S.page_audio({"title": "x", "video_url": ""})
        self.assertIn("Add the song's audio file instead", str(c.exception))


@unittest.skipUnless(HAVE, "ffmpeg is needed")
class Attach(unittest.TestCase):
    def test_the_lyrics_become_the_quote_the_sound_the_voice_and_the_title_is_suno_s(self):
        D = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, D, True)
        open(os.path.join(D, "brief.md"), "w").write("# Inspiration short\n\n## Idea\n\n(write the quote or the idea here)\n\n## Options\n\n")
        mp4 = os.path.join(D, "src.mp4"); make_mp4(mp4); m4a = os.path.join(D, "v.m4a")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-vn", "-c:a", "copy", m4a], check=True)
        S.attach_voice(D, {"title": "You Are Allowed to Change", "lyrics": "[Verse]\nYou are allowed to change,\n\nand grow\n[Outro]"}, m4a)
        self.assertTrue(os.path.isfile(os.path.join(D, "voiceover.m4a")))
        import json
        q = json.load(open(os.path.join(D, "quote.json"))); self.assertEqual(q["lines"], ["You are allowed to change,", "and grow"])   # labels and blanks dropped
        self.assertEqual(open(os.path.join(D, "title.txt")).read().strip(), "You Are Allowed to Change")
        self.assertEqual(narration.get_option(D, "voice_from"), "suno"); self.assertEqual(narration.get_option(D, "voiceover"), "file")

    def test_a_song_with_no_lyrics_or_too_many_is_refused_before_anything_is_made(self):
        with self.assertRaises(ValueError): S.voice_lines({"lyrics": "[Instrumental]"})
        with self.assertRaises(ValueError) as c: S.voice_lines({"lyrics": "\n".join("line %d" % i for i in range(41))})
        self.assertIn("more than 40", str(c.exception))


if __name__ == "__main__":
    unittest.main()
