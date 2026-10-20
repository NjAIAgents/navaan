"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: the visual treatment library (NAV-130) and its planners: what a plan may say per channel, that no figure is shown without a source, that Python and Remotion agree, that a plan reaches the render; the Aha-lorithm plan, its picture savings and its approval (NAV-129); the automatic calm caption of an inspiration (NAV-131); word starts and the loudness curve from the voice (NAV-132).
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile, unittest
from unittest import mock
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import _pgenv  # noqa: F401  (a throwaway database schema per path, for the items made below)
import visuals_plan as V
REMOTION = os.path.join(HERE, "..", "remotion")


def beat(line, treatment, **data): return {"line": line, "treatment": treatment, **({"data": data} if data else {})}


class Rules(unittest.TestCase):
    def test_an_aha_short_may_use_every_scene_and_each_beat_names_its_line_once(self):
        plan = {"beats": [beat(0, "hook"), beat(1, "compare", left={"title": "A", "text": "b"}, right={"title": "C", "text": "d"}), beat(2, "strike", wrong="Sure", right="Proof")]}
        self.assertEqual(V.validate(plan, "aha", 3), [])
        self.assertTrue(any("two treatments" in e for e in V.validate({"beats": [beat(0, "hook"), beat(0, "hook")]}, "aha", 3)))
        self.assertTrue(any("not one of the 2 lines" in e for e in V.validate({"beats": [beat(2, "hook")]}, "aha", 2)))

    def test_inspiration_stays_simple_one_calm_caption_and_never_a_scene(self):
        self.assertEqual(V.validate({"caption": {"treatment": "hero", "emph": ["behind"], "closing": True}}, "inspiration", 0), [])
        self.assertTrue(any("does not use the chat" in e for e in V.validate({"beats": [beat(0, "chat", question="q", answer="a")]}, "inspiration", 3)))
        self.assertTrue(any("does not use the karaoke" in e for e in V.validate({"caption": {"treatment": "karaoke"}}, "aha", 3)))
        self.assertTrue(any("unknown caption" in e for e in V.validate({"caption": {"treatment": "confetti"}}, "inspiration", 0)))

    def test_a_figure_is_never_shown_without_a_source_or_the_sample_label(self):
        for t, d in (("stat", {"value": 87, "label": "x"}), ("ring", {"value": 87, "label": "x"}), ("chart", {"series": [{"label": "a", "points": [0.1, 0.2, 0.3]}]})):
            self.assertTrue(any("a number is never shown" in e for e in V.validate({"beats": [beat(0, t, **d)]}, "aha", 1)), t)
            self.assertEqual(V.validate({"beats": [beat(0, t, **d, sample=True)]}, "aha", 1), [], t)
            self.assertEqual(V.validate({"beats": [beat(0, t, **d, source="WHO 2024, table 3")]}, "aha", 1), [], t)
        self.assertTrue(V.validate({"beats": [beat(0, "stat", value=5, label="x", sample=False)]}, "aha", 1), "sample must be true, not just present")

    def test_bars_are_an_illustration_so_a_number_in_a_label_needs_a_source(self):
        rows = [{"label": "Feels certain", "fill": 0.9}, {"label": "Checked 35%", "fill": 0.35}]
        self.assertTrue(any("has a number" in e for e in V.validate({"beats": [beat(0, "bars", rows=rows)]}, "aha", 1)))
        self.assertEqual(V.validate({"beats": [beat(0, "bars", rows=rows, source="Survey 2024")]}, "aha", 1), [])

    def test_text_that_would_not_fit_the_frame_is_refused(self):
        self.assertTrue(any("frame fits" in e for e in V.validate({"beats": [beat(0, "strike", wrong="Confidencexx", right="Evidence")]}, "aha", 1)))
        self.assertTrue(V.validate({"beats": [beat(0, "flow", nodes=["only one"])]}, "aha", 1))
        self.assertTrue(V.validate({"beats": [beat(0, "ring", value=140, label="x", sample=True)]}, "aha", 1))

    def test_an_empty_unknown_or_unrelated_plan_is_refused(self):
        self.assertTrue(V.validate({}, "aha", 3)); self.assertTrue(V.validate("x", "aha", 3)); self.assertTrue(V.validate({"beats": [beat(0, "hook")]}, "music", 3))
        self.assertTrue(any("unknown scene" in e for e in V.validate({"beats": [beat(0, "spin")]}, "aha", 3)))


class Library(unittest.TestCase):
    def names(self, file, pattern): return set(re.findall(pattern, open(os.path.join(REMOTION, "src", "treatments", file), encoding="utf-8").read(), re.M))

    def test_the_python_and_remotion_lists_are_the_same_lists(self):
        self.assertEqual(set(V.SCENES), self.names("scenes.tsx", r"^  (\w+): \{C: "), "scene treatments: scripts/visuals_plan.py and remotion/src/treatments/scenes.tsx")
        reg = re.search(r"export const CAPTIONS[^=]*= \{(.*)\};", open(os.path.join(REMOTION, "src", "treatments", "captions.tsx"), encoding="utf-8").read()).group(1)
        self.assertEqual(set(V.CAPTIONS), set(re.findall(r"(\w+): \w+", reg)), "caption treatments: scripts/visuals_plan.py and remotion/src/treatments/captions.tsx")

    def test_every_treatment_has_a_valid_sample_to_preview(self):
        files = {os.path.basename(p)[:-5]: json.load(open(p, encoding="utf-8")) for p in glob.glob(os.path.join(REMOTION, "samples", "*.json"))}
        self.assertEqual(set(files), set(V.SCENES) | set(V.CAPTIONS), "one samples/<treatment>.json each")
        for name, props in files.items():
            channel = "inspiration" if name in V.CAPTIONS else "aha"
            self.assertEqual(V.validate(props["visuals"], channel, len(props.get("lines") or [])), [], name)
            self.assertEqual(props["base"], "none")

    def test_the_composition_is_registered(self):
        self.assertIn('id="VisualShort"', open(os.path.join(REMOTION, "src", "Root.tsx"), encoding="utf-8").read())


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name
        self.D = os.path.join(self.tmp.name, "songs", "aha-001"); os.makedirs(self.D)


class Files(Env):
    def test_a_valid_plan_loads_and_a_broken_one_is_ignored_with_a_reason(self):
        self.assertIsNone(V.load(self.D, "aha", 2), "no visual_plan.json is the normal case")
        plan = {"beats": [beat(0, "hook")]}; json.dump(plan, open(os.path.join(self.D, "visual_plan.json"), "w")); self.assertEqual(V.load(self.D, "aha", 2), plan)
        json.dump({"beats": [beat(0, "stat", value=1, label="x")]}, open(os.path.join(self.D, "visual_plan.json"), "w"))
        with mock.patch("builtins.print") as said: self.assertIsNone(V.load(self.D, "aha", 2))
        self.assertIn("not usable", said.call_args[0][0])
        open(os.path.join(self.D, "visual_plan.json"), "w").write("{nope"); self.assertIsNone(V.load(self.D, "aha", 2))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class Short(unittest.TestCase):
    """The real prep over an Aha-lorithm short: a valid plan lands in timing.json, none leaves it as it was."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import new_song, narration
        slug = new_song.create(None, "aha", ""); self.slug = slug; self.D = os.path.join(self.tmp.name, "songs", slug)
        json.dump({"text": "One. Two. Three.", "lines": ["One thing.", "Two things.", "Three things."], "author": "", "kind": "original", "language": "en", "aha": 2}, open(os.path.join(self.D, "quote.json"), "w"))
        narration.set_options(self.D, {"duration": "12", "music": "none", "narrate": "none"})
        from PIL import Image
        Image.new("RGB", (8, 8)).save(os.path.join(self.D, "background.png"))

    def test_the_plan_is_merged_into_the_timing_and_an_absent_one_changes_nothing(self):
        import inspire_prep
        inspire_prep.main(self.slug); self.assertNotIn("visuals", json.load(open(os.path.join(self.D, "timing.json"))))
        plan = {"beats": [beat(1, "checklist", items=["a", "b"])]}; json.dump(plan, open(os.path.join(self.D, "visual_plan.json"), "w"))
        inspire_prep.main(self.slug); self.assertEqual(json.load(open(os.path.join(self.D, "timing.json")))["visuals"], plan)
        json.dump({"beats": [beat(9, "hook")]}, open(os.path.join(self.D, "visual_plan.json"), "w"))   # a line the short does not have
        inspire_prep.main(self.slug); self.assertNotIn("visuals", json.load(open(os.path.join(self.D, "timing.json"))))


class Render(Env):
    T = {"narration": False, "duration": 20, "background": "background.png", "voiceover": None, "music": None, "slug": "aha-001",
         "lines": [{"text": "A", "start": 0, "end": 3}, {"text": "B", "start": 3, "end": 6}], "style": {"color": "#fff", "accent": "#E2B75A"}, "hold_until": 6.5}

    def run_render(self, T, side_effect=None):
        import inspire_render as R
        json.dump(T, open(os.path.join(self.D, "timing.json"), "w"))
        with mock.patch.object(R, "remotion_dir", return_value=self.tmp.name), mock.patch.object(R.subprocess, "run", side_effect=side_effect) as run:
            R.render_remotion(self.D, T, os.path.join(self.D, "out.mp4"))
        return [c[0][0] for c in run.call_args_list]

    def test_a_planned_aha_short_renders_through_visualshort_over_the_quote_base(self):
        cmds = self.run_render({**self.T, "visuals": {"beats": [beat(0, "hook")]}})
        self.assertEqual(len(cmds), 1); self.assertIn("VisualShort", cmds[0]); self.assertNotIn("Quote", cmds[0])
        props = json.load(open(os.path.join(self.D, "visual_props.json")))
        self.assertEqual((props["base"], props["visuals"], props["lines"][1]["text"]), ("quote", {"beats": [beat(0, "hook")]}, "B"))
        self.assertIn("--props=" + os.path.join(self.D, "visual_props.json"), cmds[0])

    def test_a_scene_only_aha_short_with_a_voice_is_not_taken_for_the_lyrics_template(self):
        cmds = self.run_render({**self.T, "narration": True, "voiceover": "narration.mp3", "visuals": {"beats": [beat(0, "hook")]}})
        self.assertEqual(json.load(open(os.path.join(self.D, "visual_props.json")))["base"], "quote"); self.assertIn("VisualShort", cmds[0])

    def test_a_narrated_inspiration_with_a_caption_plan_uses_the_lyrics_base(self):
        T = {**self.T, "narration": True, "voiceover": "narration.mp3", "brand": None, "visuals": {"caption": {"treatment": "rise"}}}
        self.run_render(T); props = json.load(open(os.path.join(self.D, "visual_props.json")))
        self.assertEqual((props["base"], props["visuals"]["caption"]["treatment"]), ("lyrics", "rise")); self.assertEqual([c["text"] for c in props["cues"]], ["A", "B"])

    def test_if_the_plan_does_not_render_the_plain_short_is_made_instead(self):
        boom = subprocess.CalledProcessError(1, "npx")
        cmds = self.run_render({**self.T, "visuals": {"beats": [beat(0, "hook")]}}, side_effect=[boom, None])
        self.assertEqual(len(cmds), 2); self.assertIn("VisualShort", cmds[0]); self.assertIn("Quote", cmds[1]); self.assertIn("--props=" + os.path.join(self.D, "timing.json"), cmds[1])

    def test_a_short_without_a_plan_renders_exactly_as_before(self):
        cmds = self.run_render(self.T); self.assertEqual(len(cmds), 1); self.assertIn("Quote", cmds[0]); self.assertFalse(os.path.exists(os.path.join(self.D, "visual_props.json")))


class Aha(unittest.TestCase):
    """NAV-129: the Aha-lorithm's plan is approved with the script, saves the pictures it replaces, and never carries sample data into a real short."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import new_song
        self.slug = new_song.create(None, "aha", ""); self.D = os.path.join(self.tmp.name, "songs", self.slug)
        json.dump({"text": "a b c d", "lines": ["Hook line.", "Compare them.", "A figure.", "The aha."], "captions": ["Hook", "Compare", "Figure", "Aha"], "aha": 3,
                   "pictures": ["a long enough picture prompt for beat one", "", "", "a long enough picture prompt for the aha beat"]}, open(os.path.join(self.D, "quote.json"), "w"))

    def plan(self, beats):
        json.dump({"beats": beats}, open(os.path.join(self.D, "visual_plan.json"), "w"))

    def test_a_beat_shown_by_a_scene_needs_no_picture_and_none_is_paid_for(self):
        import aha_pictures as A, navaan as N
        from PIL import Image
        import io
        self.plan([beat(1, "compare", left={"title": "A", "text": "b"}, right={"title": "C", "text": "d"}), beat(2, "checklist", items=["x"])])
        self.assertEqual(V.picture_beats(V.load(self.D, "aha", 4), 4), [0, 3]); self.assertEqual(len(A.prompts(self.D)), 4)
        buf = io.BytesIO(); Image.new("RGB", (1152, 2048), "teal").save(buf, "PNG"); calls = []
        import media_cfg; old = (A.I.request_image, media_cfg.get_key, media_cfg.add_usage)
        A.I.request_image = lambda p, *a, **k: calls.append(p) or buf.getvalue(); media_cfg.get_key = lambda n: "k"; media_cfg.add_usage = lambda **k: None
        try: self.assertEqual(A.main([self.slug]), 0)
        finally: A.I.request_image, media_cfg.get_key, media_cfg.add_usage = old
        self.assertEqual(len(calls), 2, "beats 1 and 4 only"); self.assertFalse(os.path.exists(A.beat_file(self.D, 1))); self.assertTrue(N.aha_beats_done(self.D))

    def test_without_a_plan_every_beat_needs_its_picture_as_before(self):
        import aha_pictures as A
        with self.assertRaises(ValueError): A.prompts(self.D)   # beats 2 and 3 have empty prompts and nothing shows them instead

    def test_the_plan_is_approved_with_the_script_so_changing_either_needs_a_new_approval(self):
        import navaan as N
        before = N.gate_sha(self.D, "quote"); self.plan([beat(0, "hook")]); with_plan = N.gate_sha(self.D, "quote"); self.assertNotEqual(before, with_plan)
        self.plan([beat(0, "hook"), beat(2, "checklist", items=["x"])]); self.assertNotEqual(N.gate_sha(self.D, "quote"), with_plan)

    def test_approving_the_script_is_refused_while_its_plan_cannot_be_drawn(self):
        import navaan as N
        self.plan([beat(2, "stat", value=87, label="x", sample=True)])   # sample data is for previews: a real short needs a source
        with self.assertRaises(SystemExit) as cm: N.set_gate(self.slug, "quote", True, "test")
        self.assertIn("a number is never shown", str(cm.exception)); self.assertNotIn("quote", (json.load(open(os.path.join(self.D, "meta.json"))).get("approvals") or {}))
        self.plan([beat(2, "stat", value=87, label="x", source="https://example.org/report")]); N.set_gate(self.slug, "quote", True, "test")
        self.assertIn("quote", json.load(open(os.path.join(self.D, "meta.json")))["approvals"])

    def test_a_sample_figure_is_a_preview_only_a_real_short_ignores_the_plan_with_one(self):
        self.plan([beat(2, "ring", value=50, label="x", sample=True)])
        with mock.patch("builtins.print"): self.assertIsNone(V.load(self.D, "aha", 4))
        self.assertEqual(V.validate({"beats": [beat(2, "ring", value=50, label="x", sample=True)]}, "aha", 4), [], "previews may still say SAMPLE DATA")


class Look(unittest.TestCase):
    """NAV-131: an inspiration gets one calm caption treatment chosen from its words, `- look:` overrides it."""
    LINES = ["Maybe you are not behind", "Maybe you are just becoming", "Slow is still moving"]

    def test_few_lines_with_strong_words_get_the_hero_and_it_grows_those_words(self):
        c = V.auto_caption(self.LINES)["caption"]
        self.assertEqual((c["treatment"], c["closing"]), ("hero", True)); self.assertEqual(c["emph"], ["behind", "becoming", "moving"])

    def test_many_lines_are_read_one_at_a_time_and_the_rest_rise(self):
        self.assertEqual(V.auto_caption(["one two"] * 7)["caption"]["treatment"], "karaoke")
        self.assertEqual(V.auto_caption(["to be or not", "so it is", "we go on", "yes", "no way"])["caption"]["treatment"], "rise")

    def test_the_brief_can_name_the_look_or_turn_it_off(self):
        self.assertEqual(V.auto_caption(self.LINES, "karaoke")["caption"]["treatment"], "karaoke")
        self.assertIsNone(V.auto_caption(self.LINES, "plain")); self.assertEqual(V.auto_caption(self.LINES, "sparkly")["caption"]["treatment"], "hero", "an unknown look is auto")
        self.assertEqual(V.validate(V.auto_caption(self.LINES), "inspiration", 0, strict=True), [])
        self.assertIsNone(V.auto_caption([" "]))

    def test_devanagari_words_survive_the_emphasis_pick(self):
        c = V.auto_caption(["मैं अकेलापन महसूस करता हूँ", "फिर भी चलता रहूँगा हमेशा"])["caption"]; self.assertEqual(c["treatment"], "hero")
        self.assertTrue(all(w == w.strip() and "।" not in w for w in c["emph"])); self.assertIn("अकेलापन", c["emph"])


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class Voice(unittest.TestCase):
    """NAV-132: word starts and the loudness curve come from the voice."""
    def wav(self, path, bursts, total):
        import wave, struct, math
        sr = 16000; x = [0.0] * int(sr * total)
        for a, b in bursts:
            for i in range(int(a * sr), int(b * sr)): x[i] = 0.5 * math.sin(2 * math.pi * 220 * i / sr)
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(b"".join(struct.pack("<h", int(v * 32000)) for v in x))

    def test_each_word_starts_where_the_voice_picks_up_not_where_its_length_says(self):
        import voice_timing as VT
        try: import numpy  # noqa: F401
        except ImportError: self.skipTest("numpy not installed")
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); p = os.path.join(tmp.name, "v.wav")
        self.wav(p, [(0.5, 1.0), (1.6, 2.7), (3.1, 3.5)], 4.0)   # three words, the middle one long
        r = VT.analyse(p, 30, [{"text": "aaa bbbbbbb ccc", "start": 0.4, "end": 3.6}])
        at = r["at"][0]; self.assertEqual(len(at), 3); self.assertAlmostEqual(at[0], 0.4, places=2)
        self.assertAlmostEqual(at[1], 1.6, delta=0.15, msg="the long word starts after its pause (length alone says about 1.5)"); self.assertAlmostEqual(at[2], 3.1, delta=0.15)
        amp = r["amp"]; self.assertEqual(len(amp), int(4.0 * 30) + 1); self.assertTrue(all(0 <= a <= 1 for a in amp))
        self.assertGreater(amp[int(0.7 * 30)], 0.7); self.assertLess(amp[int(1.3 * 30)], 0.2, "quiet between the words"); self.assertGreater(amp[int(2.0 * 30)], 0.7)

    def test_a_silent_or_unreadable_voice_gives_nothing_so_the_words_are_timed_by_length(self):
        import voice_timing as VT
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); p = os.path.join(tmp.name, "s.wav"); self.wav(p, [], 2.0)
        self.assertIsNone(VT.analyse(p, 30, [{"text": "a b", "start": 0, "end": 1}])); open(os.path.join(tmp.name, "bad.wav"), "w").write("not audio")
        self.assertIsNone(VT.analyse(os.path.join(tmp.name, "bad.wav"), 30, [{"text": "a b", "start": 0, "end": 1}]))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
class Narrated(unittest.TestCase):
    """The real prep over a narrated inspiration: the caption chosen, timed by the voice, and passed to the renderer."""
    SRT = "1\n00:00:00,500 --> 00:00:02,400\nMaybe you are not behind\n\n2\n00:00:02,700 --> 00:00:05,000\nMaybe you are just becoming\n\n3\n00:00:05,300 --> 00:00:07,000\nSlow is still moving\n"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import new_song, narration
        self.slug = new_song.create(None, "inspiration", ""); self.D = os.path.join(self.tmp.name, "songs", self.slug)
        json.dump({"text": "x", "lines": ["Maybe you are not behind", "Maybe you are just becoming", "Slow is still moving"], "author": "", "kind": "original", "language": "en"}, open(os.path.join(self.D, "quote.json"), "w"))
        narration.set_options(self.D, {"music": "none", "narrate": "none"})
        from PIL import Image
        Image.new("RGB", (8, 8)).save(os.path.join(self.D, "background.png"))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=7.5", os.path.join(self.D, "voiceover.mp3")], check=True)
        open(os.path.join(self.D, "voiceover.srt"), "w").write(self.SRT)

    def timing(self):
        import inspire_prep
        with mock.patch("builtins.print"): inspire_prep.main(self.slug)
        return json.load(open(os.path.join(self.D, "timing.json")))

    def test_a_narrated_inspiration_gets_a_calm_caption_timed_by_its_voice(self):
        T = self.timing(); cap = T["visuals"]["caption"]
        self.assertEqual(cap["treatment"], "hero"); self.assertEqual(V.validate(T["visuals"], "inspiration", 0, strict=True), [])
        try: import numpy  # noqa: F401
        except ImportError: return
        self.assertTrue(cap["amp"] and all(0 <= a <= 1 for a in cap["amp"])); self.assertEqual([len(l["at"]) for l in T["lines"]], [5, 5, 4])

    def test_the_brief_look_overrides_and_plain_leaves_the_captions_as_before(self):
        import narration
        narration.set_options(self.D, {"music": "none", "narrate": "none", "look": "karaoke"}); self.assertEqual(self.timing()["visuals"]["caption"]["treatment"], "karaoke")
        narration.set_options(self.D, {"music": "none", "narrate": "none", "look": "plain"}); self.assertNotIn("visuals", self.timing())

    def test_a_plan_somebody_wrote_wins_over_the_automatic_one(self):
        json.dump({"caption": {"treatment": "rise"}}, open(os.path.join(self.D, "visual_plan.json"), "w")); self.assertEqual(self.timing()["visuals"]["caption"]["treatment"], "rise")

    def test_the_renderer_is_given_each_words_start(self):
        import inspire_render as R
        T = {"width": 1080, "height": 1920, "fps": 30, "duration": 9, "background": "background.png", "background_video": False, "voiceover": "narration.mp3", "narration": True, "brand": None,
             "lines": [{"text": "a b", "start": 1, "end": 3, "at": [1.0, 1.6]}, {"text": "c", "start": 3, "end": 4}], "style": {"color": "#fff", "accent": "#E2B75A", "dim": 0.4}, "visuals": {"caption": {"treatment": "rise"}}}
        with mock.patch.object(R, "remotion_dir", return_value=self.tmp.name), mock.patch.object(R.subprocess, "run"):
            R.render_remotion(self.D, T, os.path.join(self.D, "o.mp4"))
        cues = json.load(open(os.path.join(self.D, "visual_props.json")))["cues"]; self.assertEqual(cues[0]["at"], [1.0, 1.6]); self.assertNotIn("at", cues[1])


if __name__ == "__main__":
    unittest.main()
