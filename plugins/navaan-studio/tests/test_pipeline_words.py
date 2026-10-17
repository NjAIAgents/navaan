import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan as N, navaan_ui as U

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


if __name__ == "__main__":
    unittest.main()
