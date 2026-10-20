"""Author: Navjyot Nishant
Created: 2026-10-20
Last updated: 2026-10-20
Description: changing an Aha-lorithm script at its approval (NAV-133): edit the beats' words, replace the script with the owner's own, and send a note back; the modern song and album covers (NAV-135), and the Aha-lorithm pictures that follow their topic (NAV-136).
"""
import json, os, sys, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import script_edit as S


class Edit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name
        self.D = os.path.join(self.tmp.name, "songs", "aha-001"); os.makedirs(self.D)
        json.dump({"type": "aha", "state": "draft", "approvals": {}}, open(os.path.join(self.D, "meta.json"), "w"))
        json.dump({"text": "One. Two.", "lines": ["One.", "Two."], "captions": ["One", "*Two*"], "pictures": ["p" * 30, "q" * 30], "aha": 1, "sources": ["https://example.org"]}, open(os.path.join(self.D, "quote.json"), "w"))

    def q(self): return json.load(open(os.path.join(self.D, "quote.json")))

    def test_editing_rewrites_the_words_and_keeps_everything_else(self):
        S.edit(self.D, ["Uno *now*.", "Dos."], ["Uno", "*Dos*"]); q = self.q()
        self.assertEqual((q["lines"], q["captions"], q["text"]), (["Uno now.", "Dos."], ["Uno", "*Dos*"], "Uno now. Dos."), "marks stay out of the spoken lines and in the captions")
        self.assertEqual((q["pictures"], q["aha"], q["sources"]), (["p" * 30, "q" * 30], 1, ["https://example.org"]))

    def test_the_number_of_beats_cannot_change_here_and_nothing_may_be_empty_or_too_long(self):
        for lines, caps, why in ((["a"], ["a"], "has 2 beats"), (["a", "b", "c"], ["a", "b", "c"], "has 2 beats"), (["a", " "], ["a", "b"], "Beat 2 has no spoken"), (["a", "b"], ["a", ""], "Beat 2 has no caption"),
                                 (["a" * 201, "b"], ["a", "b"], "200 characters"), (["a", "b"], ["x" * 81, "b"], "80 characters")):
            with self.assertRaises(ValueError) as cm: S.edit(self.D, lines, caps)
            self.assertIn(why, str(cm.exception))
        self.assertEqual(self.q()["lines"], ["One.", "Two."], "a refused edit changes nothing")
        with self.assertRaises(ValueError): S.edit(self.D, "x", "y")

    def test_own_words_are_written_for_the_script_step_and_a_note_too(self):
        S.replace(self.D, "  First sentence here.\n\n  Second one follows.  ")
        t = open(os.path.join(self.D, S.FEEDBACK)).read(); self.assertTrue(t.startswith("REPLACE:")); self.assertIn("Keep every word exactly", t); self.assertTrue(t.rstrip().endswith("First sentence here.\nSecond one follows."))
        S.feedback(self.D, "make   the hook\nsharper"); self.assertEqual(open(os.path.join(self.D, S.FEEDBACK)).read(), "make the hook sharper\n")
        for bad in ("", "short", "x" * 2501):
            with self.assertRaises(ValueError): S.replace(self.D, bad)
        with self.assertRaises(ValueError): S.feedback(self.D, "  ")

    def test_the_script_step_clears_the_old_plan_when_it_is_redone_and_knows_replace(self):
        import navaan as N
        st = next(s for s in N.steps("aha-001", self.D) if s["id"] == "quote"); self.assertIn("visual_plan.json", st["outputs"]); self.assertIn("quote.json", st["outputs"])
        self.assertIn("REPLACE:", open(os.path.join(HERE, "..", "skills", "aha-script", "SKILL.md"), encoding="utf-8").read())


class Covers(unittest.TestCase):
    """NAV-135: the art direction is modern and the lettering is a clean sans; a cover still renders for Latin and Devanagari titles."""
    def test_the_direction_is_modern_not_painterly_and_the_songs_skill_says_the_same(self):
        import make_cover as M
        for w in ("Modern", "negative space", "limited palette", "Not painterly"): self.assertIn(w, M.MODERN_LOOK)
        sk = open(os.path.join(HERE, "..", "skills", "flow-visuals", "SKILL.md"), encoding="utf-8").read()
        self.assertIn("Make it modern", sk); self.assertNotIn("painterly, grainy, editorial", sk)

    def test_latin_lettering_prefers_a_modern_sans_and_always_finds_a_font(self):
        import make_cover as M
        names = [os.path.basename(p) for p, _ in M.LATIN]; self.assertTrue(names[0].startswith("Inter")); self.assertLess(names.index("NotoSans-Bold.ttf"), names.index("DejaVuSans-Bold.ttf"))
        self.assertLess(names.index("Avenir Next.ttc"), names.index("Arial Bold.ttf")); self.assertGreater(M.latin(40).size, 0)

    def test_a_song_cover_renders_for_a_latin_and_a_native_title(self):
        import make_cover as M
        from PIL import Image
        os.environ["NAVAAN_ROOT"] = tempfile.mkdtemp(); self.addCleanup(lambda: os.environ.pop("NAVAAN_ROOT", None))
        D = os.path.join(os.environ["NAVAAN_ROOT"], "songs", "song-001"); os.makedirs(D); Image.new("RGB", (900, 900), (40, 60, 120)).save(os.path.join(D, "art.png"))
        for title in ("Tere Hone Se", "पता ही ना चला (Pata Hi Na Chala)"):
            M.make("song-001", os.path.join(D, "art.png"), D, title)
            self.assertEqual(Image.open(os.path.join(D, "cover_1x1.png")).size, (1080, 1080)); self.assertEqual(Image.open(os.path.join(D, "cover_16x9.png")).size, (1920, 1080))


class Pictures(unittest.TestCase):
    """NAV-136: a beat's picture is its own scene in the short's own look, with only the technical limits fixed."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.D = self.tmp.name

    def quote(self, **kw): json.dump({"lines": ["a", "b"], **kw}, open(os.path.join(self.D, "quote.json"), "w"))

    def test_what_is_sent_is_the_scene_the_shorts_look_and_the_limits_not_a_house_style(self):
        import aha_pictures as A
        self.quote(look="Paper-cut collage with soft shadows, warm terracotta and teal, quiet morning light")
        p = A.prompt_for("A tangled phone charger on a desk", A.look(self.D))
        self.assertTrue(p.startswith("A tangled phone charger on a desk")); self.assertIn("Paper-cut collage", p); self.assertIn("No words, letters, numbers", p); self.assertIn("calm enough for a caption", p)
        for old in ("near-black", "luminous gold", "shallow depth of field", "Cinematic still"): self.assertNotIn(old, p, "the fixed gold and dark wording is gone")

    def test_two_shorts_with_different_looks_send_different_directions_and_an_older_one_still_works(self):
        import aha_pictures as A
        self.quote(look="Risograph print with grain and two spot colours, red and blue"); a = A.look(self.D)
        self.quote(look="Blueprint line art on deep blue, technical and precise"); b = A.look(self.D); self.assertNotEqual(a, b)
        self.quote(); self.assertEqual(A.look(self.D), A.DEFAULT_LOOK); self.quote(look="x"); self.assertEqual(A.look(self.D), A.DEFAULT_LOOK, "a look too short to mean anything is the neutral one")
        self.quote(look="y" * 900); self.assertEqual(len(A.look(self.D)), 400)
        self.assertNotIn("gold", A.DEFAULT_LOOK.lower())

    def test_the_script_skill_asks_for_a_look_per_topic_and_a_scene_per_beat(self):
        t = open(os.path.join(HERE, "..", "skills", "aha-script", "SKILL.md"), encoding="utf-8").read()
        for w in ("`look`", "concrete scene", "no two beats share a subject", "Do not default to glowing brains"): self.assertIn(w, t)
        self.assertNotIn("One look across the beats", t); self.assertNotIn("near-black backgrounds, luminous gold", t); self.assertIn('"look": "the short\'s art direction"'.replace("\\'", "'"), t)


if __name__ == "__main__":
    unittest.main()
