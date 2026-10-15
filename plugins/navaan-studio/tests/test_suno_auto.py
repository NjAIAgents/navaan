import os, sys, json, base64, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import suno_import as S


class T(unittest.TestCase):
    def test_pick_audio(self):
        c = {"audio_url": "https://studio-api.prod.suno.com/api/forbidden",
             "media_urls": [{"url": "https://d2lwuy8qc234o3.cloudfront.net/1/clip/x.m4a", "content_type": "m4a-opus"}]}
        self.assertEqual(S.pick_audio_url(c), "https://d2lwuy8qc234o3.cloudfront.net/1/clip/x.m4a")
        self.assertIsNone(S.pick_audio_url({"audio_url": "https://studio-api.prod.suno.com/api/forbidden", "media_urls": []}))
        self.assertEqual(S.pick_audio_url({"audio_url": "https://cdn1.suno.ai/x.mp3"}), "https://cdn1.suno.ai/x.mp3")
        self.assertIsNone(S.pick_audio_url({"media_urls": [{"url": "http://insecure/x.m4a", "content_type": "m4a-opus"}]}))

    def test_auto_marks_failure_and_keeps_going(self):
        D = tempfile.mkdtemp()
        json.dump({"source": "suno_import", "suno": {"id": "a5d98935-ef34-4c38-abdd-5e68c5487892"}}, open(os.path.join(D, "meta.json"), "w"))
        S.song_dir = lambda slug: D
        S.fetch = lambda slug, dest=None: False
        self.assertEqual(S.auto("x"), 1)
        self.assertEqual(json.load(open(os.path.join(D, "meta.json")))["suno"]["auto_failed"], "no public text")

    def test_save_upload_checks_and_clears_failure(self):
        D = tempfile.mkdtemp()
        json.dump({"source": "suno_import", "suno": {"auto_failed": "no public audio"}}, open(os.path.join(D, "meta.json"), "w"))
        S.song_dir = lambda slug: D
        big = "data:audio/mpeg;base64," + base64.b64encode(b"x" * 60000).decode()
        with self.assertRaises(ValueError): S.save_upload("x", "notes.txt", big)
        with self.assertRaises(ValueError): S.save_upload("x", "a.mp3", "data:;base64," + base64.b64encode(b"x" * 10).decode())
        self.assertEqual(S.save_upload("x", "My_Song.mp3", big), "takes/upload.mp3")
        m = json.load(open(os.path.join(D, "meta.json")))
        self.assertNotIn("auto_failed", m["suno"]); self.assertEqual(m["suno"]["upload_title"], "My Song")
        self.assertEqual(os.path.getsize(os.path.join(D, "takes", "upload.mp3")), 60000)

    def test_auto_uses_upload_without_suno_text(self):
        D = tempfile.mkdtemp(); os.makedirs(os.path.join(D, "takes"))
        open(os.path.join(D, "takes", "upload.mp3"), "wb").write(b"x")
        json.dump({"source": "suno_import", "suno": {"upload": "takes/upload.mp3", "upload_title": "My Song"}}, open(os.path.join(D, "meta.json"), "w"))
        S.song_dir = lambda slug: D
        S.fetch = lambda slug, dest=None: False
        def no_fetch(slug, dest=None): raise AssertionError("must not fetch Suno audio when an upload exists")
        S.fetch_audio = no_fetch
        seen = {}
        S.ingest = lambda slug, a: seen.update(audio=a.audio, title=a.title)
        self.assertEqual(S.auto("x"), 0)
        self.assertTrue(seen["audio"].endswith("upload.mp3")); self.assertEqual(seen["title"], "My Song")


if __name__ == "__main__":
    unittest.main()
