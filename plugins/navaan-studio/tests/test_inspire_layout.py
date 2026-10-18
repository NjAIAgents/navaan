import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import inspire_prep as P


def lines(): return [{"text": "a", "start": 1.0, "end": 9.0}, {"text": "b", "start": 4.0, "end": 9.0}, {"text": "c", "start": 7.0, "end": 9.0}]


class Layout(unittest.TestCase):
    def test_single_shows_one_line_at_a_time_each_ending_where_the_next_starts_and_the_last_holds(self):
        out = P.apply_layout(lines(), "single")
        self.assertEqual([l["end"] for l in out], [4.0, 7.0, 9.0])

    def test_stack_keeps_every_line_until_the_end_as_before(self):
        out = P.apply_layout(lines(), "stack")
        self.assertEqual([l["end"] for l in out], [9.0, 9.0, 9.0])

    def test_one_line_and_no_lines_are_fine(self):
        self.assertEqual(P.apply_layout([{"text": "a", "start": 1, "end": 5}], "single")[0]["end"], 5); self.assertEqual(P.apply_layout([], "single"), [])

    def test_the_brief_chooses_the_layout_and_single_is_the_default(self):
        import tempfile
        d = tempfile.mkdtemp(); self.assertEqual(P.opt(d, "layout", "single"), "single")
        open(os.path.join(d, "brief.md"), "w").write("## Options\n\n- layout: stack\n"); self.assertEqual(P.opt(d, "layout", "single"), "stack")


class Hook(unittest.TestCase):
    def test_a_quote_with_no_voice_starts_at_once_and_runs_seven_to_fifteen_seconds(self):
        i, d = P.plain_timing(8.0, 5.6); self.assertEqual(i, 0.2); self.assertAlmostEqual(d, 13.8)   # as long as the words need
        self.assertEqual(P.plain_timing(20.0, 5.6)[1], 15.0)   # a long quote is held to fifteen seconds
        self.assertEqual(P.plain_timing(0.5, 2.2)[1], 7.0)   # and a tiny one is not shorter than seven
        self.assertEqual(P.plain_timing(8.0, 5.6)[0], P.HOOK_INTRO); self.assertLess(P.HOOK_INTRO, 2.0)   # the first line is on screen within the first two seconds
        self.assertEqual(P.plain_timing(8.0, 5.6, "25"), (0.2, 25.0)); self.assertEqual(P.plain_timing(8.0, 5.6, "99")[1], 30.0); self.assertEqual(P.plain_timing(8.0, 5.6, "3")[1], 7.0)   # a duration in the brief wins, within 7 to 30

if __name__ == "__main__":
    unittest.main()
