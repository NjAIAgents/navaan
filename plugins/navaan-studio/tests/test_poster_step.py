"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: the poster as a step of a song's pipeline: where it sits, what it says it spends, when it counts as done, and which prompt it paints from.
"""
import os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan as N
import media_cfg
import poster as P


class Step(unittest.TestCase):
    def steps(self, D):
        return {s["id"]: s for s in N.song_picture_steps("s", D, media_cfg.load())}

    def test_the_poster_comes_after_the_pictures_behind_the_same_credits_approval_and_says_what_it_costs(self):
        D = tempfile.mkdtemp(); st = self.steps(D)
        self.assertEqual(list(st), ["prompts", "pictures", "cover", "poster"])
        p = st["poster"]; self.assertEqual((p["before"], p["kind"]), ("credits", "script")); self.assertEqual(p["outputs"], ["poster_2x3.png", "poster_art.png"])
        self.assertRegex(N.spend_what(p), r"^Make the poster with OpenAI \(1 picture, about \$\d+\.\d\d at \w+\)$")   # the credits approval lists it with its price

    def test_it_is_done_when_the_poster_exists_or_the_videos_were_already_approved_and_not_before(self):
        D = tempfile.mkdtemp(); p = self.steps(D)["poster"]
        self.assertFalse(p["done"]({})); self.assertFalse(p["done"]({"approvals": {}}))
        self.assertTrue(p["done"]({"approvals": {"media": {"at": "x"}}}))   # a song made before this step existed is not sent back to make a poster (and spend) on its next run
        open(os.path.join(D, "poster_2x3.png"), "wb").write(b"x"); self.assertTrue(self.steps(D)["poster"]["done"]({}))

    def test_the_step_paints_from_the_prompt_saved_on_the_poster_card_else_from_the_song(self):
        D = tempfile.mkdtemp(); open(os.path.join(D, "title.txt"), "w").write("Tere Hone Se\n"); open(os.path.join(D, "style.txt"), "w").write("soft pop, male vocals")
        open(os.path.join(D, "lyrics.txt"), "w").write("[Verse]\nline one\nline two\n")
        sent = []
        def fake(slug, prompt, style=None): sent.append(prompt); return 0.07
        with mock.patch.object(P.C, "song_dir", lambda slug: D), mock.patch.object(P, "generate", fake):
            self.assertEqual(P.main(["s"]), 0)
            self.assertIn("Tere Hone Se", sent[0])   # no saved prompt: the one made from the song
            open(os.path.join(D, "poster_prompt.txt"), "w").write("A lantern on a quiet river, portrait poster, no text.\n"); sent.clear()
            P.main(["s"]); self.assertEqual(sent[0], "A lantern on a quiet river, portrait poster, no text.")   # the card's prompt wins
            sent.clear(); P.main(["s", "--prompt", "Given on the command line, a full sentence."]); self.assertEqual(sent[0], "Given on the command line, a full sentence.")

if __name__ == "__main__":
    unittest.main()
