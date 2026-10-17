import os, sys, tempfile, unittest, unittest.mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import navaan_common as C, caption_clips as K, ffrender
from PIL import Image


def glyph(font, ch):
    from PIL import ImageDraw
    im = Image.new("L", (80, 80), 0); ImageDraw.Draw(im).text((10, 10), ch, font=font, fill=255); return im


def has_letters(font):
    """A font without a glyph draws the same empty box for every letter: n and v then look identical."""
    return glyph(font, "n").tobytes() != glyph(font, "v").tobytes() and glyph(font, "a").getbbox() is not None


class Fonts(unittest.TestCase):
    def test_text_with_devanagari_is_told_apart_from_latin_text(self):
        self.assertTrue(C.has_devanagari("तेरे होने से")); self.assertTrue(C.has_devanagari("Tere तेरे")); self.assertFalse(C.has_devanagari("@navaan_p5l")); self.assertFalse(C.has_devanagari(""))

    def test_english_text_gets_a_font_that_has_the_letters(self):   # the watermark "@navaan_p5l" was boxes, an underscore and a 5, because the caption font is Devanagari only
        if not any(os.path.exists(p) for p, _ in C.LATIN_FONT_CANDIDATES): self.skipTest("no Latin font on this machine")
        self.assertTrue(has_letters(C.font_for("@navaan_p5l", 40)))
        self.assertTrue(has_letters(C.font_for("There was a quiet in those little streets", 46)))

    def test_latin_text_never_goes_to_the_devanagari_font_and_devanagari_text_always_does(self):   # on prod that font is Noto Sans Devanagari, which has no a-z
        if not any(os.path.exists(p) for p, _ in C.LATIN_FONT_CANDIDATES): self.skipTest("no Latin font on this machine")
        with unittest.mock.patch.object(C, "font", lambda s: "DEVANAGARI-FONT"), unittest.mock.patch.dict(os.environ, {"NAVAAN_FONT": ""}), unittest.mock.patch.object(C, "cfg", lambda k, d=None: d):
            self.assertNotEqual(C.font_for("@navaan_p5l", 40), "DEVANAGARI-FONT"); self.assertNotEqual(C.font_for("There was a quiet", 40), "DEVANAGARI-FONT")
            self.assertEqual(C.font_for("तेरे होने से", 40), "DEVANAGARI-FONT"); self.assertEqual(C.font_for("Tere तेरे", 40), "DEVANAGARI-FONT")   # any Devanagari: that font, it also draws digits and punctuation

    def test_a_font_set_by_the_owner_still_wins_for_everything(self):
        with unittest.mock.patch.dict(os.environ, {"NAVAAN_FONT": "/nope/x.ttf"}), unittest.mock.patch.object(C, "font", lambda s: "owner-font"):
            self.assertEqual(C.font_for("English", 20), "owner-font"); self.assertEqual(C.font_for("हिंदी", 20), "owner-font")

    def test_the_watermark_of_a_wide_and_a_vertical_video_is_drawn_in_its_corner_with_real_letters(self):
        if not any(os.path.exists(p) for p, _ in C.LATIN_FONT_CANDIDATES): self.skipTest("no Latin font on this machine")
        d = tempfile.mkdtemp(); wide, tall = os.path.join(d, "w.png"), os.path.join(d, "t.png")
        ffrender.watermark_png("@navaan_p5l", 1920, 1080, wide); ffrender.watermark_png("@navaan_p5l", 1080, 1920, tall)
        w = Image.open(wide).convert("RGBA"); t = Image.open(tall).convert("RGBA")
        self.assertIsNotNone(w.crop((1100, 900, 1920, 1080)).getchannel("A").getbbox()); self.assertIsNone(w.crop((0, 0, 1000, 700)).getchannel("A").getbbox())   # bottom right only
        self.assertIsNotNone(t.crop((0, 150, 700, 450)).getchannel("A").getbbox()); self.assertIsNone(t.crop((0, 1000, 1080, 1920)).getchannel("A").getbbox())   # top left only
        # the letters are real: the same text drawn twice with different letters differs, boxes would not
        a, b = os.path.join(d, "a.png"), os.path.join(d, "b.png"); ffrender.watermark_png("nnnnnnn", 1920, 1080, a); ffrender.watermark_png("vvvvvvv", 1920, 1080, b)
        self.assertNotEqual(Image.open(a).tobytes(), Image.open(b).tobytes())


class Wrap(unittest.TestCase):
    m = staticmethod(lambda t, s: len(t) * s * 0.5)

    def test_a_short_line_stays_one_line(self):
        self.assertEqual(K.fit_lines("short line", 46, 1080, self.m), (["short line"], 46))

    def test_a_long_line_wraps_in_the_middle_and_every_line_fits(self):
        text = "There was a quiet in those little streets and the rain kept falling slow"
        lines, size = K.fit_lines(text, 46, 1080, self.m)
        self.assertEqual(len(lines), 2); self.assertEqual(" ".join(lines), text); self.assertTrue(all(self.m(l, size) <= 1080 * 0.88 for l in lines))

    def test_a_line_still_too_wide_shrinks_the_type_but_not_below_sixty_percent(self):
        lines, size = K.fit_lines("a " * 80, 46, 1080, self.m); self.assertGreaterEqual(size, 46 * 0.6 - 2); self.assertLess(size, 46)
        lines, size = K.fit_lines("unbroken" * 30, 46, 600, self.m); self.assertEqual(len(lines), 1); self.assertGreaterEqual(size, 46 * 0.6 - 2)   # one word cannot wrap


if __name__ == "__main__":
    unittest.main()
