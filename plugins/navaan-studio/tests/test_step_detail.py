import os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan_ui as U


class Made(unittest.TestCase):
    def setUp(self):
        self.D = tempfile.mkdtemp()
        for rel, data in {"background.png": b"x" * 10, "images/a.png": b"y", "images/b.png": b"z", "clips/c1.mp4": b"v", ".cache/motion/m.mp4": b"h", "scenes/background.txt": b"A quiet harbour at dusk, warm light.", "quote.json": b'{"text":"Stay soft."}', "big.txt": b"q" * 300_000, "voiceover.mp3": b"a"}.items():
            p = os.path.join(self.D, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(data)

    def test_the_files_a_step_made_are_named_the_way_media_serves_them_and_hidden_or_deep_ones_are_left_out(self):
        got = U.made_files(self.D, ["background.*", "images/*", "clips/*.mp4", ".cache/motion/*.mp4", "scenes/*.txt", "voiceover.mp3"])
        self.assertEqual([g["name"] for g in got], ["background.png", "images~a.png", "images~b.png", "clips~c1.mp4", "voiceover.mp3"])   # scenes/ is text (shown as text); .cache is hidden
        self.assertEqual(got[0]["size"], 10); self.assertEqual(U.made_files(self.D, ["images/*"], cap=1), [{"name": "images~a.png", "size": 1}])

    def test_the_text_a_step_wrote_is_shown_so_a_prompt_can_be_read_after_it_ran(self):
        t = U.made_texts(self.D, ["scenes/background.txt", "quote.json", "big.txt", "background.*"])
        self.assertEqual([x["name"] for x in t], ["scenes/background.txt", "quote.json"])   # too big and not text are skipped
        self.assertEqual(t[0]["text"], "A quiet harbour at dusk, warm light.")
        self.assertTrue(U.made_texts(self.D, ["quote.json"], limit=5)[0]["text"].endswith("…"))   # long text is cut, and says so
        self.assertEqual(U.made_texts(self.D, ["nothing.txt"]), [])


if __name__ == "__main__":
    unittest.main()
