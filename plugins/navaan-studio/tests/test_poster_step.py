"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: the poster is not a step of a song's pipeline (NAV-144: the cover is the picture of a shared link), and a poster made on request still paints from the prompt saved on its card, else from the song.
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

    def test_a_song_has_no_poster_step_so_the_credits_approval_never_lists_one(self):
        D = tempfile.mkdtemp(); st = self.steps(D)
        self.assertEqual(list(st), ["prompts", "pictures", "cover"])
        self.assertFalse(any("poster" in k or "poster" in v["label"].lower() or "poster" in N.spend_what(v).lower() for k, v in st.items() if v.get("before") == "credits"))
        self.assertEqual({k for k, v in st.items() if v.get("before") == "credits"}, {"pictures", "cover"})

    def test_a_song_that_already_has_a_poster_is_not_touched_by_the_pipeline_and_the_poster_files_are_not_step_outputs(self):
        D = tempfile.mkdtemp(); open(os.path.join(D, "poster_2x3.png"), "wb").write(b"x")
        st = self.steps(D); outs = [o for v in st.values() for o in v.get("outputs", [])]
        self.assertNotIn("poster_2x3.png", outs); self.assertNotIn("poster_art.png", outs)   # a redo of a step never moves an existing poster away

    def test_a_poster_made_on_request_paints_from_the_prompt_saved_on_the_poster_card_else_from_the_song(self):
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
