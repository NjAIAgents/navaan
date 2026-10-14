import os, sys, json, tempfile, unittest
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


if __name__ == "__main__":
    unittest.main()
