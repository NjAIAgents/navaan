import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import narration_sync as N

LINES = ["Maybe you're not falling behind.", "Maybe you're just learning to live…", "at a pace that finally feels like yours.", "You don't have to rush your becoming.", "You don't have to have it all figured out."]


class Align(unittest.TestCase):
    def test_lines_start_where_whisper_hears_them(self):
        segs = [(0.5, 3.0, "Maybe you're not falling behind."), (3.6, 7.0, "Maybe you're just learning to live at a pace that finally feels like yours."),
                (9.0, 12.0, "You don't have to rush your becoming."), (14.0, 17.0, "You don't have to have it all figured out.")]
        cues = N.align_lines(LINES, segs)
        st = [c[0] for c in cues]
        self.assertAlmostEqual(st[0], 0.5, delta=0.3)
        self.assertAlmostEqual(st[1], 3.6, delta=0.3)
        self.assertTrue(4.5 < st[2] < 5.8)  # inside the long phrase, in proportion
        self.assertAlmostEqual(st[3], 9.0, delta=0.3)
        self.assertAlmostEqual(st[4], 14.0, delta=0.3)
        self.assertEqual(cues[0][1], cues[1][0])  # a line stays up until the next starts

    def test_spelling_differences_do_not_matter(self):
        segs = [(1.0, 4.0, "Maybe youre not falling behind"), (6.0, 9.0, "Maybe you are just learning to live")]
        cues = N.align_lines(LINES[:2], segs)
        self.assertAlmostEqual(cues[1][0], 6.0, delta=0.4)

    def test_order_and_gap_hold(self):
        cues = N.align_lines(["aaa bbb", "ccc ddd"], [(0.0, 0.2, "aaa bbb ccc ddd")])
        self.assertGreaterEqual(cues[1][0] - cues[0][0], 0.6)

    def test_nothing_heard(self):
        self.assertIsNone(N.align_lines(LINES, []))


if __name__ == "__main__":
    unittest.main()
