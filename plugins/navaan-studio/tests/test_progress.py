"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: how far a running step has got: the PROGRESS line a step prints, the sign of life, the ffmpeg helper, and the picture plan's editable words.
"""
import io, json, os, shutil, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan as N
import navaan_common as C
import prompt_pack as P

HAVE = bool(shutil.which("ffmpeg"))


class Lines(unittest.TestCase):
    def test_a_progress_line_is_read_and_anything_else_is_not(self):
        self.assertEqual(N.parse_progress("PROGRESS 3/16 pictures saved"), {"done": 3, "total": 16, "pct": 19, "label": "pictures saved"})
        self.assertEqual(N.parse_progress("PROGRESS 5/5")["pct"], 100); self.assertEqual(N.parse_progress("PROGRESS 9/4")["done"], 4)   # never past the end
        for bad in ("", "picture 3 of 16 saved", "PROGRESS soon", "PROGRESS 1/0", "progress 1/2"): self.assertIsNone(N.parse_progress(bad), bad)

    def test_a_step_s_output_moves_its_bar_and_is_a_sign_of_life(self):
        N.RUN["s"] = {"step": "pictures", "attempt": 1, "attempts": 3, "started": 1.0, "activity_at": 1.0, "failed": None}; self.addCleanup(N.RUN.pop, "s", None)
        N.note_output("s", "some chatter"); self.assertGreater(N.RUN["s"]["activity_at"], 1.0); self.assertNotIn("pct", N.RUN["s"])
        N.note_output("s", "PROGRESS 8/16 pictures saved"); self.assertEqual((N.RUN["s"]["pct"], N.RUN["s"]["label"]), (50, "pictures saved"))
        N.note_output("other", "PROGRESS 1/2"); N.note_output(None, "PROGRESS 1/2")   # nobody is running there: nothing to update, nothing raised
        N.RUN["s"] = {"step": None, "failed": "pictures"}; N.note_output("s", "PROGRESS 1/2"); self.assertNotIn("pct", N.RUN["s"])   # a failed run is not updated by late output

    def test_the_output_pump_feeds_the_bar_and_keeps_the_raw_text_in_the_step_file(self):
        N.RUN["p"] = {"step": "video", "attempt": 1, "attempts": 3, "started": 1.0, "activity_at": 1.0, "failed": None}; self.addCleanup(N.RUN.pop, "p", None)
        r, w = os.pipe(); os.write(w, b"hello\rPROGRESS 2/4 joining\nbye\n"); os.close(w)
        class S:   # the pump only needs a file number
            def fileno(self): return r
        log = io.StringIO(); N._pump(S(), log, "p"); os.close(r)
        self.assertEqual(N.RUN["p"]["pct"], 50); self.assertIn("PROGRESS 2/4 joining", log.getvalue())   # the file keeps everything


@unittest.skipUnless(HAVE, "ffmpeg is needed")
class Ffmpeg(unittest.TestCase):
    def test_run_ffmpeg_reports_the_share_done_inside_its_part_of_the_bar_and_still_raises(self):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d, True); out = os.path.join(d, "o.mp4"); said = io.StringIO()
        cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=64x64:d=4:r=10", "-c:v", "libx264", "-pix_fmt", "yuv420p", out]
        with mock.patch("sys.stdout", said): C.run_ffmpeg(cmd, 4, "joining", base=70, span=30)
        pcts = [int(l.split()[1].split("/")[0]) for l in said.getvalue().splitlines() if l.startswith("PROGRESS ")]
        self.assertTrue(pcts and all(70 <= p <= 99 for p in pcts) and pcts == sorted(pcts), pcts)   # inside its 70 to 99 part, never going back
        self.assertTrue(os.path.getsize(out) > 0)
        import subprocess
        with self.assertRaises(subprocess.CalledProcessError): C.run_ffmpeg(["ffmpeg", "-y", "-v", "error", "-i", os.path.join(d, "missing.mp4"), out], 4)


PACK = {"director": "openai", "concept": "A quiet ache.", "character": "A woman.", "style_line": "Rain-slick city.", "look": {"style_line": "Rain-slick city.", "palette": "teal"}, "aspect": "16:9",
        "prompts": [{"n": 1, "section": "Verse", "lyric": "a", "prompt": "First picture.", "camera": "push_in", "focus": [0.5, 0.5], "motion": ""}, {"n": 2, "section": "Chorus", "lyric": "b", "prompt": "Second picture.", "camera": "pan", "focus": None, "motion": ""}]}


class Plan(unittest.TestCase):
    def setUp(self):
        self.D = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, self.D, True)
        json.dump(PACK, open(P.pack_path(self.D), "w", encoding="utf-8"))

    def test_only_the_words_change_and_the_rest_of_the_plan_is_kept(self):
        P.apply_edits(self.D, {"character": "A lone man seen from behind.", "style_line": "Soft dusk.", "prompts": [{"n": 2, "prompt": "  The same street, empty.  "}]})
        got = json.load(open(P.pack_path(self.D), encoding="utf-8"))
        self.assertEqual((got["character"], got["style_line"], got["look"]["style_line"]), ("A lone man seen from behind.", "Soft dusk.", "Soft dusk."))   # the look follows the one-line style
        self.assertEqual((got["prompts"][1]["prompt"], got["prompts"][0]["prompt"]), ("The same street, empty.", "First picture."))
        self.assertEqual((got["prompts"][1]["camera"], got["look"]["palette"], got["concept"], got["aspect"]), ("pan", "teal", "A quiet ache.", "16:9"))   # camera, palette, idea untouched

    def test_every_bad_edit_is_refused_with_a_sentence_and_changes_nothing(self):
        before = open(P.pack_path(self.D), encoding="utf-8").read()
        for edits, word in (({"concept": "  "}, "cannot be empty"), ({"character": "x" * 3001}, "over 3000"), ({"prompts": [{"n": 9, "prompt": "x"}]}, "no picture 9"),
                            ({"prompts": [{"n": 1, "prompt": ""}]}, "cannot be empty"), ({"prompts": [{"prompt": "x"}]}, "picture number"), ("text", "object")):
            with self.assertRaises(ValueError, msg=str(edits)) as c: P.apply_edits(self.D, edits)
            self.assertIn(word, str(c.exception))
        self.assertEqual(open(P.pack_path(self.D), encoding="utf-8").read(), before)
        os.remove(P.pack_path(self.D))
        with self.assertRaises(ValueError) as c: P.apply_edits(self.D, {"concept": "x"})
        self.assertIn("no picture plan", str(c.exception))


if __name__ == "__main__":
    unittest.main()
