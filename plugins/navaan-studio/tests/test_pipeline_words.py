import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import tempfile, unittest.mock
import navaan as N, navaan_ui as U, navaan_common as C

ROWS = [{"id": "background", "label": "Create the background image (OpenAI)", "done": True}, {"id": "render", "label": "Render the video", "done": False}]


class SpendWhat(unittest.TestCase):
    def test_each_credit_step_says_what_it_spends(self):
        self.assertIn("ElevenLabs", N.spend_what({"id": "narrate", "label": "Narrate the quote (ElevenLabs)"}))
        self.assertIn("OpenAI", N.spend_what({"id": "background", "label": "Create the background image (OpenAI)"}))
        self.assertIn("Flow", N.spend_what({"id": "background", "label": "Create the background image (Flow)"}))
        self.assertIn("Suno", N.spend_what({"id": "suno", "label": "Generate the song on Suno"}))
        self.assertEqual(N.spend_what({"id": "pictures", "label": "Create the pictures with OpenAI (6 pictures, about $0.15 at high)"}), "Create the pictures with OpenAI (6 pictures, about $0.15 at high)")   # it carries its own count and price

    def test_an_inspiration_never_mentions_suno_in_what_it_spends(self):
        steps = [s for s in N.inspiration_steps("s", os.path.join(os.sep, "tmp", "none")) if s.get("before") == "credits"]
        self.assertTrue(steps); self.assertFalse(any("Suno" in N.spend_what(s) for s in steps))


class Plain(unittest.TestCase):
    def test_a_failure_is_put_in_words_and_the_raw_text_is_not_the_headline(self):
        self.assertIn("no key", U.plain_failure("narrate", "No ElevenLabs key is saved. Add it under Settings, Narration.", ROWS))
        self.assertIn("restarted", U.plain_failure("", "the worker stopped before the job finished", ROWS))
        self.assertIn("bg_9x16.png", U.plain_failure("render", "FileNotFoundError: [Errno 2] No such file or directory: 'scenes/bg_9x16.png'", ROWS))
        self.assertEqual(U.plain_failure("render", "Traceback weird", ROWS), "Render the video did not finish. The details are under this message.")
        self.assertEqual(U.plain_failure("zzz", "", ROWS), "A step did not finish. The details are under this message.")


class NoLyrics(unittest.TestCase):
    def setUp(self):
        self.D = tempfile.mkdtemp()

    def put(self, text):
        with open(os.path.join(self.D, "lyrics.txt"), "w", encoding="utf-8") as f: f.write(text)

    def test_the_sung_lines_ignore_blanks_and_section_labels_and_an_empty_file_has_none(self):
        self.assertEqual(C.lyric_lines(self.D), [])   # no file
        self.put(""); self.assertEqual(C.lyric_lines(self.D), [])   # an imported song with an empty lyrics.txt (song-007)
        self.put("[Verse 1]\n\nline one\n  line two  \n[Chorus]\n"); self.assertEqual(C.lyric_lines(self.D), ["line one", "line two"])

    def test_captions_and_the_picture_plan_stop_early_with_a_sentence_when_there_are_no_lyrics(self):
        import captions_run, prompt_pack
        self.put("")
        with unittest.mock.patch.object(captions_run, "song_dir", lambda slug: self.D):
            with self.assertRaises(SystemExit) as c: captions_run.main("s")
        self.assertIn("no lyrics saved", str(c.exception)); self.assertIn("nothing to time", str(c.exception)); self.assertIn("Content tab", str(c.exception))   # not a divide by zero inside the aligner
        with unittest.mock.patch.object(prompt_pack.C, "song_dir", lambda slug: self.D):
            with self.assertRaises(SystemExit) as c: prompt_pack.main(["s"])
        self.assertIn("would be invented", str(c.exception)); self.assertIn("male vocals", str(c.exception))

    def test_english_or_romanised_lines_get_an_english_transcript_and_devanagari_only_lyrics_do_not(self):
        import captions_run
        self.put("[Verse 1]\nThere was a quiet in those little streets,\nFamiliar faces\n"); self.assertTrue(captions_run.has_latin_lines(os.path.join(self.D, "lyrics.txt")))   # song-007: English, so the aligner needs _asren.json
        self.put("[Verse]\nतेरे होने से रंग है\nसब कुछ है\n"); self.assertFalse(captions_run.has_latin_lines(os.path.join(self.D, "lyrics.txt")))
        self.put("[Intro]\n\n[Outro]\n"); self.assertFalse(captions_run.has_latin_lines(os.path.join(self.D, "lyrics.txt")))   # labels alone are not lyrics

    def test_the_failure_says_the_lyrics_are_missing_and_our_own_messages_pass_through(self):
        rows = [{"id": "captions", "label": "Measure lyric timing", "done": False}]
        self.assertIn("no lyrics saved", U.plain_failure("captions", "navaan: no cues were produced", rows, no_lyrics=True))
        self.assertEqual(U.plain_failure("captions", "navaan: caption tools are not installed. Approve the captions_setup gate.", rows), "Caption tools are not installed. Approve the captions_setup gate.")
        self.assertIn("did not finish", U.plain_failure("captions", "Traceback ...\nValueError", rows))


if __name__ == "__main__":
    unittest.main()
