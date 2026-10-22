"""Author: Navjyot Nishant
Created: 2026-10-21
Last updated: 2026-10-21
Description: an inspiration short with "a picture per beat" (NAV-145): the plan's rules, the steps it adds (and that the default is untouched), the paid picture step, the cuts that follow the voice, and the render props.
"""
import io, json, os, shutil, subprocess, sys, tempfile, unittest
from unittest import mock
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import _pgenv  # noqa: F401  (a throwaway database schema per path, for the items made below)
import beat_plan as B

LINES = ["You were never meant to carry everything.", "Not their expectations.", "Not their guilt.", "Let it go.", "Your peace matters too."]
LOOK = "Quiet dusk photographs, cold teal and amber, soft grain, long shadows, empty streets."


def plan(*groups, look=LOOK):
    return {"look": look, "beats": [{"lines": g, "prompt": "A figure seen from behind on an empty street at dusk, wet pavement."} for g in groups]}


class Rules(unittest.TestCase):
    def test_lines_are_grouped_in_order_into_fewer_pictures_than_lines(self):
        self.assertEqual(B.problems(plan([0], [1, 2], [3, 4]), LINES), [])
        self.assertEqual(B.problems(plan([0, 1], [2, 3, 4]), LINES), [])
        one_to_one = B.problems(plan([0], [1], [2], [3], [4]), LINES)
        self.assertTrue(any("takes 2 to 4 pictures" in p for p in one_to_one), one_to_one)   # a picture carries a thought, not a sentence

    def test_every_line_is_in_exactly_one_beat_and_in_order(self):
        self.assertTrue(any("cover 4 of the 5 lines" in p for p in B.problems(plan([0], [1, 2], [3]), LINES)))
        self.assertTrue(any("next lines in order" in p for p in B.problems(plan([0], [2, 3, 4], [1]), LINES)))
        self.assertTrue(any("next lines in order" in p for p in B.problems(plan([0, 1], [1, 2, 3, 4]), LINES)))
        self.assertTrue(any("has no lines" in p for p in B.problems({"look": LOOK, "beats": [{"lines": [], "prompt": "x" * 30}, {"lines": [0, 1, 2, 3, 4], "prompt": "x" * 30}]}, LINES)))

    def test_a_beat_must_be_long_enough_to_be_seen_and_have_a_scene_and_the_short_a_look(self):
        short = B.problems(plan([0, 1, 2], [3], [4]), LINES)   # "Let it go." is 3 words
        self.assertTrue(any("beat 2 has 3 words" in p for p in short), short)
        bad = plan([0, 1], [2, 3, 4]); bad["beats"][0]["prompt"] = "too short"
        self.assertTrue(any("beat 1's prompt" in p for p in B.problems(bad, LINES)))
        self.assertTrue(any("no look" in p for p in B.problems(plan([0, 1], [2, 3, 4], look=""), LINES)))
        self.assertTrue(any("at least 2" in p for p in B.problems(plan([0]), ["One line only that is long enough."])))
        self.assertEqual(B.problems(None, LINES), ["there is no picture plan"])


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import new_song
        self.slug = new_song.create(None, "inspiration", ""); self.D = os.path.join(self.tmp.name, "songs", self.slug)
        json.dump({"text": " ".join(LINES), "lines": LINES, "author": "", "kind": "original", "language": "en"}, open(os.path.join(self.D, "quote.json"), "w"))

    def write_plan(self, p): json.dump(p, open(os.path.join(self.D, B.PLAN), "w"))
    def beats_on(self):
        import narration; narration.set_options(self.D, {"pictures": "beats"})
    def pictures(self, n):
        from PIL import Image
        os.makedirs(os.path.join(self.D, "scenes"), exist_ok=True)
        for k in range(n): Image.new("RGB", (8, 8)).save(B.beat_file(self.D, k))


class Steps(Env):
    def ids(self):
        import navaan
        return [s["id"] for s in navaan.inspiration_steps(self.slug, self.D)]

    def test_without_the_option_the_steps_are_exactly_what_they_were(self):
        ids = self.ids(); self.assertIn("background", ids); self.assertNotIn("beat_plan", ids); self.assertNotIn("beat_pictures", ids)

    def test_the_option_swaps_the_one_background_for_a_plan_and_the_paid_pictures_behind_the_credits(self):
        import navaan
        self.beats_on(); ids = self.ids()
        self.assertEqual(ids[:4], ["quote", "originality", "beat_plan", "beat_pictures"]); self.assertNotIn("background", ids)
        st = {s["id"]: s for s in navaan.inspiration_steps(self.slug, self.D)}
        self.assertEqual((st["beat_plan"]["kind"], st["beat_plan"]["skill"]), ("claude", "inspiration-beats")); self.assertIsNone(st["beat_plan"].get("before"))   # planning spends nothing
        self.assertEqual((st["beat_pictures"]["kind"], st["beat_pictures"]["before"]), ("script", "credits"))
        self.assertIn("picture_plan.json", st["quote"]["outputs"], "a new quote makes the old plan stale")
        self.assertTrue(os.path.isfile(os.path.join(HERE, "..", "skills", "inspiration-beats", "SKILL.md")))

    def test_an_owners_scene_video_or_an_aha_short_never_gets_the_beat_steps(self):
        import navaan
        self.beats_on(); open(os.path.join(self.D, "scene_src.mp4"), "w").write("x")
        ids = self.ids(); self.assertIn("scene", ids); self.assertNotIn("beat_plan", ids)
        self.assertNotIn("beat_plan", [s["id"] for s in navaan.aha_steps(self.slug, self.D)])

    def test_the_approval_line_says_how_many_pictures_and_what_they_cost_and_counts_only_what_is_left(self):
        import navaan
        self.beats_on(); label = lambda: {s["id"]: s for s in navaan.inspiration_steps(self.slug, self.D)}["beat_pictures"]
        self.assertIn("not planned yet", label()["label"])
        self.write_plan(plan([0], [1, 2], [3, 4])); l = label()["label"]
        self.assertIn("Make 3 pictures with OpenAI, one per beat", l); self.assertIn("$", l); self.assertEqual(navaan.spend_what(label()), l)
        self.pictures(1); self.assertIn("Make 2 pictures", label()["label"])
        self.assertFalse(label()["done"]({})); self.pictures(3); self.assertTrue(label()["done"]({}))


class Paid(Env):
    def run_main(self, *extra, have_key=True):
        import beat_pictures as P, image_openai as I, media_cfg
        from PIL import Image
        png = io.BytesIO(); Image.new("RGB", (64, 114), (30, 40, 60)).save(png, "PNG")
        calls, spent = [], []
        with mock.patch.object(I, "request_image", side_effect=lambda prompt, *a, **k: calls.append(prompt) or png.getvalue()), \
             mock.patch.object(media_cfg, "get_key", return_value="k" if have_key else ""), mock.patch.object(media_cfg, "add_usage", side_effect=lambda **k: spent.append(k)), \
             mock.patch("builtins.print"):
            try: rc = P.main([self.slug, *extra])
            except SystemExit as e: rc = str(e)
        return rc, calls, spent

    def test_one_picture_per_beat_each_with_the_short_look_and_the_limits_and_the_first_is_the_thumbnail(self):
        self.write_plan(plan([0], [1, 2], [3, 4])); rc, calls, spent = self.run_main()
        self.assertEqual((rc, len(calls), len(spent)), (0, 3, 3))
        self.assertTrue(all(LOOK in c and "No words, letters" in c for c in calls))
        self.assertTrue(all(os.path.exists(B.beat_file(self.D, k)) for k in range(3))); self.assertTrue(os.path.exists(os.path.join(self.D, "background.png")))

    def test_a_second_run_pays_for_nothing_and_force_makes_them_all_again(self):
        self.write_plan(plan([0, 1], [2, 3, 4])); self.run_main()
        rc, calls, spent = self.run_main(); self.assertEqual((rc, calls, spent), (0, [], []))
        rc, calls, spent = self.run_main("--force"); self.assertEqual((len(calls), len(spent)), (2, 2))

    def test_no_usable_plan_or_no_key_means_nothing_is_spent(self):
        rc, calls, spent = self.run_main(); self.assertIn("picture plan", str(rc)); self.assertEqual((calls, spent), ([], []))
        self.write_plan(plan([0], [1], [2], [3], [4])); rc, calls, spent = self.run_main(); self.assertIn("not usable", str(rc)); self.assertEqual(spent, [])
        self.write_plan(plan([0, 1], [2, 3, 4])); rc, calls, spent = self.run_main(have_key=False); self.assertIn("no OpenAI key", str(rc)); self.assertEqual(spent, [])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class Timing(Env):
    """The real prep over a narrated inspiration: a picture changes where a beat's first line starts in the voice."""
    SRT = "1\n00:00:00,500 --> 00:00:02,400\nMaybe you are not behind\n\n2\n00:00:02,700 --> 00:00:05,000\nMaybe you are just becoming\n\n3\n00:00:05,300 --> 00:00:07,000\nSlow is still moving\n"
    L3 = ["Maybe you are not behind", "Maybe you are just becoming", "Slow is still moving"]

    def setUp(self):
        super().setUp()
        import narration
        json.dump({"text": " ".join(self.L3), "lines": self.L3, "author": "", "kind": "original", "language": "en"}, open(os.path.join(self.D, "quote.json"), "w"))
        narration.set_options(self.D, {"music": "none", "narrate": "none", "pictures": "beats"})
        from PIL import Image
        Image.new("RGB", (8, 8)).save(os.path.join(self.D, "background.png"))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=7.5", os.path.join(self.D, "voiceover.mp3")], check=True)
        open(os.path.join(self.D, "voiceover.srt"), "w").write(self.SRT)

    def timing(self):
        import inspire_prep
        with mock.patch("builtins.print"): inspire_prep.main(self.slug)
        return json.load(open(os.path.join(self.D, "timing.json")))

    def test_pictures_change_where_the_voice_starts_a_beat_and_the_last_one_holds_to_the_end(self):
        self.write_plan(plan([0], [1, 2])); self.pictures(2); T = self.timing(); s = T["scenes"]
        self.assertEqual([x["bg"] for x in s], ["scenes/beat_01.png", "scenes/beat_02.png"])
        self.assertEqual(s[0]["start"], 0.0); self.assertAlmostEqual(s[0]["end"], T["lines"][1]["start"], places=2); self.assertAlmostEqual(s[1]["start"], T["lines"][1]["start"], places=2)
        self.assertAlmostEqual(s[1]["end"], T["duration"], places=2)
        self.assertGreater(T["lines"][1]["start"], 2.0, "the cut is where the second line starts in the voice, not on a timer")

    def test_without_the_pictures_or_a_fitting_plan_the_short_keeps_its_one_background(self):
        self.write_plan(plan([0], [1, 2])); self.assertNotIn("scenes", self.timing())            # the pictures are not made yet
        self.pictures(2); os.remove(os.path.join(self.D, B.PLAN)); self.assertNotIn("scenes", self.timing())   # no plan
        self.write_plan(plan([0, 1], [2])); self.assertNotIn("scenes", self.timing())            # the last beat has 4 words: not a usable plan for this script

    def test_the_default_output_carries_no_scenes(self):
        import narration
        narration.set_options(self.D, {"pictures": "single"}); self.write_plan(plan([0], [1, 2])); self.pictures(2); self.assertNotIn("scenes", self.timing())

    def test_the_renderer_is_given_the_pictures(self):
        import inspire_render as R
        self.write_plan(plan([0], [1, 2])); self.pictures(2); T = self.timing()
        with mock.patch.object(R, "remotion_dir", return_value=self.tmp.name), mock.patch.object(R.subprocess, "run") as run:
            R.render_remotion(self.D, T, os.path.join(self.D, "out.mp4"))
        props = json.load(open(os.path.join(self.D, "visual_props.json"))) if "VisualShort" in run.call_args[0][0] else json.load(open(os.path.join(self.D, "narration_props.json")))
        self.assertEqual([b["bg"] for b in props["bgs"]], ["scenes/beat_01.png", "scenes/beat_02.png"])


class Segments(Env):
    def test_a_cut_that_would_flash_a_picture_for_under_a_second_is_refused(self):
        self.write_plan(plan([0], [1, 2], [3, 4]))
        ok = B.segments(self.D, [0.4, 4.0, 6.0, 9.0, 11.0], 15.0)
        self.assertEqual([(x["start"], x["end"]) for x in ok], [(0.0, 4.0), (4.0, 9.0), (9.0, 15.0)])
        self.assertIsNone(B.segments(self.D, [0.4, 4.0, 6.0, 4.5, 11.0], 15.0))
        self.assertIsNone(B.segments(self.D, [0.4, 4.0], 15.0), "one start per line")


if __name__ == "__main__":
    unittest.main()
