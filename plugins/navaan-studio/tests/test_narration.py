import os, sys, json, base64, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import narration as N

SRT = "1\n00:00:01,000 --> 00:00:03,500\nSome people leave…\n\n2\n00:00:03,500 --> 00:00:07,000\nbut the life you imagined stays.\n"
BRIEF = "# Inspiration short\n\n## Idea\n\nx\n\n## Options\n\n- tone: relatable\n- music: auto\n- voiceover: none\n- camera: auto\n"


def folder():
    D = tempfile.mkdtemp(); open(os.path.join(D, "brief.md"), "w").write(BRIEF); return D


class T(unittest.TestCase):
    def test_save_writes_files_and_sets_the_brief(self):
        D = folder()
        r = N.save(D, "My Voice.MP3", "data:audio/mpeg;base64," + base64.b64encode(b"ID3fake").decode(), SRT)
        self.assertEqual(r, {"audio": "voiceover.mp3", "cues": 2, "seconds": 7.0})
        self.assertEqual(open(os.path.join(D, "voiceover.mp3"), "rb").read(), b"ID3fake")
        b = open(os.path.join(D, "brief.md")).read()
        self.assertIn("- voiceover: file", b); self.assertIn("- music: none", b); self.assertIn("- tone: relatable", b)

    def test_new_audio_replaces_the_old_one(self):
        D = folder(); N.save(D, "a.wav", b"RIFF1", SRT); N.save(D, "b.m4a", b"M4A22", SRT)
        self.assertEqual(sorted(f for f in os.listdir(D) if f.startswith("voiceover")), ["voiceover.m4a", "voiceover.srt"])

    def test_rejects_bad_input(self):
        D = folder()
        with self.assertRaises(ValueError): N.save(D, "x.ogg", b"1", SRT)
        with self.assertRaises(ValueError): N.save(D, "x.mp3", b"", SRT)
        with self.assertRaises(ValueError): N.save(D, "x.mp3", b"1", "just some words")
        with self.assertRaises(ValueError): N.save(D, "x.mp3", b"1" * (N.MAX_AUDIO + 1), SRT)
        self.assertFalse(any(f.startswith("voiceover") for f in os.listdir(D)))

    def test_remove_restores_defaults(self):
        D = folder(); N.save(D, "a.mp3", b"1", SRT); N.remove(D)
        self.assertEqual([f for f in os.listdir(D) if f.startswith("voiceover")], [])
        b = open(os.path.join(D, "brief.md")).read(); self.assertIn("- voiceover: none", b); self.assertIn("- music: auto", b)

    def test_option_added_when_missing(self):
        D = tempfile.mkdtemp(); open(os.path.join(D, "brief.md"), "w").write("# t\n\n## Options\n\n- tone: x\n")
        N.set_options(D, {"voiceover": "file"}); self.assertIn("- voiceover: file", open(os.path.join(D, "brief.md")).read())


if __name__ == "__main__":
    unittest.main()
