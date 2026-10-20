"""Author: Navjyot Nishant
Created: 2026-10-20
Last updated: 2026-10-20
Description: the images of a blog post (NAV-139): a plan that can be checked, a cover and figures drawn with Remotion (and a cover that falls back to Pillow), pictures that are the only spend, public hashed addresses, and the images put into both drafts once.
"""
import contextlib, io, json, os, re, sys, tempfile, unittest
from unittest import mock
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import _pgenv  # noqa: F401
import blog_images as B
from PIL import Image

REMOTION = os.path.join(HERE, "..", "remotion", "src")
COVER = {"title": "Why confident answers are not evidence", "kicker": "AI engineering", "chips": ["agents", "evals"], "palette": "midnight", "motif": "nodes"}
FLOW = {"id": "i1", "kind": "figure", "treatment": "flow", "data": {"nodes": ["Question", "Patterns", "Answer", "Your check"]}, "alt": "How an answer is made", "after": "Why it sounds sure"}
PIC = {"id": "i2", "kind": "picture", "prompt": "A hand-written note with one crossed-out answer on a messy desk, morning light", "alt": "A crossed-out answer on a note", "after": "What to do"}
PLAN = {"cover": COVER, "inline": [FLOW, PIC], "look": "Paper-cut collage with soft shadows, warm terracotta and teal"}
DEVTO = '---\ntitle: "Why answers sound sure"\ndescription: "Confidence is not evidence"\ntags: ai, llm\npublished: false\n---\n\nThe hook paragraph.\n\n## Why it sounds sure\n\nFirst paragraph under the heading.\nStill the same paragraph.\n\nSecond paragraph.\n\n## What to do\n\nCheck the source.\n\n```py\nprint(1)\n```\n'
LI = "The hook paragraph.\n\n## Why it sounds sure\n\nFirst paragraph under the heading.\n\n## What to do\n\nCheck the source.\n"


def png(path, size=(40, 20)): Image.new("RGB", size, (30, 40, 60)).save(path)


class Plan(unittest.TestCase):
    def test_a_good_plan_passes_and_each_mistake_is_named(self):
        self.assertEqual(B.plan_errors(PLAN), [])
        bad = lambda **c: B.plan_errors({**PLAN, "cover": {**COVER, **c}})
        self.assertTrue(any("palette" in e for e in bad(palette="neon"))); self.assertTrue(any("motif" in e for e in bad(motif="fractal"))); self.assertTrue(any("chips" in e for e in bad(chips=list("abcde"))))
        self.assertTrue(any("title" in e for e in bad(title="x" * 91))); self.assertTrue(B.plan_errors({"inline": []})); self.assertTrue(B.plan_errors("x"))
        e = B.plan_errors({**PLAN, "inline": [FLOW, {**FLOW}]}); self.assertTrue(any("unique" in x for x in e))
        self.assertTrue(any("at most 4" in x for x in B.plan_errors({**PLAN, "inline": [{**FLOW, "id": f"i{n}"} for n in range(5)]})))
        self.assertTrue(any("treatment" in x for x in B.plan_errors({**PLAN, "inline": [{**FLOW, "treatment": "hook"}]})))   # a hook is words over a picture, not a figure
        self.assertTrue(any("alt" in x for x in B.plan_errors({**PLAN, "inline": [{**FLOW, "alt": "x"}]}))); self.assertTrue(any("prompt" in x for x in B.plan_errors({**PLAN, "inline": [{**PIC, "prompt": "short"}]})))
        self.assertTrue(any("kind" in x for x in B.plan_errors({**PLAN, "inline": [{**FLOW, "kind": "video"}]})))

    def test_a_figure_with_a_number_needs_a_source_and_never_the_sample_label(self):
        stat = {"id": "i3", "kind": "figure", "treatment": "stat", "alt": "A sourced number", "after": "x", "data": {"value": 40, "unit": "%", "label": "fewer errors"}}
        self.assertTrue(any("a number is never shown" in x for x in B.plan_errors({**PLAN, "inline": [stat]})))
        self.assertTrue(any("a number is never shown" in x for x in B.plan_errors({**PLAN, "inline": [{**stat, "data": {**stat["data"], "sample": True}}]})))
        self.assertEqual(B.plan_errors({**PLAN, "inline": [{**stat, "data": {**stat["data"], "source": "https://example.org/study"}}]}), [])

    def test_the_palettes_and_motifs_are_the_ones_remotion_draws(self):
        t = open(os.path.join(REMOTION, "BlogCover.tsx"), encoding="utf-8").read()
        pal = set(re.findall(r"^  (\w+): \{a: '#", t, re.M)); motifs = set(re.findall(r"'(\w+)'", re.search(r"export const MOTIFS = \[(.*?)\];", t).group(1)))
        self.assertEqual(pal, set(B.PALETTES)); self.assertEqual(motifs, set(B.MOTIFS))
        self.assertIn('id="BlogCover"', open(os.path.join(REMOTION, "Root.tsx"), encoding="utf-8").read()); self.assertIn('id="BlogFigure"', open(os.path.join(REMOTION, "Root.tsx"), encoding="utf-8").read())

    def test_every_remotion_sample_is_a_valid_plan_part(self):
        for f in os.listdir(os.path.join(HERE, "..", "remotion", "samples", "blog")):
            d = json.load(open(os.path.join(HERE, "..", "remotion", "samples", "blog", f)))
            if f.startswith("cover_"): self.assertEqual(B.plan_errors({"cover": {k: d[k] for k in ("title", "kicker", "chips", "palette", "motif")}}), [], f)
            else: self.assertEqual(B.plan_errors({"cover": COVER, "inline": [{"id": "i1", "kind": "figure", "treatment": d["treatment"], "data": d["data"], "alt": "A figure for the test"}]}), [], f)


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name; self.addCleanup(lambda: os.environ.pop("NAVAAN_ROOT", None))
        self.bucket = os.path.join(self.tmp.name, "bucket"); os.makedirs(self.bucket)
        p = mock.patch.dict(os.environ, {"NAVAAN_OBJSTORE_DIR": self.bucket, "NAVAAN_LISTENER_HOSTS": "navaan.online"}); p.start(); self.addCleanup(p.stop)
        import navaan_common as C
        if hasattr(C, "_CFG"): C._CFG = None
        self.D = os.path.join(self.tmp.name, "songs", "blog-001"); os.makedirs(self.D)
        json.dump({"slug": "blog-001", "type": "blog", "state": "draft", "approvals": {}}, open(os.path.join(self.D, "meta.json"), "w"))
        open(os.path.join(self.D, "devto.md"), "w").write(DEVTO); open(os.path.join(self.D, "linkedin_article.md"), "w").write(LI)
        json.dump(PLAN, open(os.path.join(self.D, "images.json"), "w"))


class Draw(Env):
    def fake_still(self, fail=()):
        def still(comp, props, out):
            if comp in fail: raise RuntimeError("remotion is not installed")
            png(out, (props["width"] // 10, props["height"] // 10))
        return still

    def test_the_covers_and_figures_are_drawn_at_the_right_sizes_and_the_pictures_wait(self):
        calls = []
        def still(comp, props, out): calls.append((comp, props)); png(out)
        with mock.patch.object(B, "_remotion", still): self.assertEqual(B.render("blog-001"), 0)
        self.assertEqual([c[0] for c in calls], ["BlogCover", "BlogCover", "BlogFigure"])
        self.assertEqual([(c[1]["width"], c[1]["height"]) for c in calls], [(1000, 420), (1200, 627), (1080, 1500)])   # the flow figure is the tallest
        self.assertEqual(calls[0][1]["title"], "Why answers sound sure", "the cover carries the post's own title"); self.assertEqual((calls[0][1]["palette"], calls[0][1]["motif"], calls[0][1]["seed"]), ("midnight", "nodes", "blog-001"))
        m = json.load(open(os.path.join(self.D, "post_images.json"))); self.assertEqual(sorted(m["cover"]), ["devto", "linkedin"]); self.assertEqual([i["id"] for i in m["inline"]], ["i1"])
        self.assertTrue(B.rendered(self.D)); self.assertFalse(B.pictures_done(self.D), "the picture still has to be made")

    def test_every_figure_treatment_has_a_height_and_a_checklist_is_shorter_than_a_flow(self):
        self.assertEqual(set(B.FIGURE_H), set(B.FIGURES)); self.assertLess(B.FIGURE_H["checklist"], B.FIGURE_H["flow"])

    def test_without_remotion_the_cover_is_drawn_with_pillow_and_a_figure_is_skipped_with_a_note(self):
        with mock.patch.object(B, "_remotion", self.fake_still(fail=("BlogCover", "BlogFigure"))), mock.patch("builtins.print"): self.assertEqual(B.render("blog-001"), 0)
        self.assertEqual(Image.open(os.path.join(self.D, "post_cover_devto.png")).size, (1000, 420)); self.assertEqual(Image.open(os.path.join(self.D, "post_cover_linkedin.png")).size, (1200, 627))
        m = json.load(open(os.path.join(self.D, "post_images.json"))); self.assertEqual(m["inline"], []); self.assertEqual(len(m["notes"]), 3)
        self.assertTrue(any("figure i1 was skipped" in n for n in m["notes"]))
        self.assertTrue(os.path.exists(os.path.join(self.D, "post_images.json")), "the step still finishes: it must not block on a missing renderer")

    def test_an_unusable_plan_draws_nothing(self):
        json.dump({**PLAN, "cover": {**COVER, "palette": "neon"}}, open(os.path.join(self.D, "images.json"), "w"))
        with mock.patch.object(B, "_remotion") as r, mock.patch("builtins.print"): self.assertEqual(B.render("blog-001"), 2)
        r.assert_not_called(); self.assertFalse(B.plan_ok(self.D))

    def test_the_check_command_says_what_is_wrong_or_what_will_be_made(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out): self.assertEqual(B.check("blog-001"), 0)
        self.assertIn("1 figure(s), 1 picture(s) (only pictures cost money)", out.getvalue())
        json.dump({**PLAN, "inline": [{**FLOW, "treatment": "nope"}]}, open(os.path.join(self.D, "images.json"), "w")); out = io.StringIO()
        with contextlib.redirect_stdout(out): self.assertEqual(B.check("blog-001"), 1)
        self.assertIn("treatment must be one of", out.getvalue())


class Pictures(Env):
    def setUp(self):
        super().setUp()
        import media_cfg, image_openai as IO
        self.M, self.IO = media_cfg, IO; self.sent, self.spent = [], []
        buf = io.BytesIO(); Image.new("RGB", (1536, 1024), "teal").save(buf, "PNG"); self.raw = buf.getvalue()
        old = (IO.request_image, media_cfg.get_key, media_cfg.add_usage, media_cfg.load)
        IO.request_image = lambda p, q, k, size, model=None: (self.sent.append((p, size)), self.raw)[1]; media_cfg.get_key = lambda n: "k"; media_cfg.add_usage = lambda **kw: self.spent.append(kw["openai_usd"])
        media_cfg.load = lambda: {"image_quality": "low", "image_size_landscape": "1536x1024", "max_run_usd": 5.0, "image_model": ""}
        self.addCleanup(lambda: (setattr(IO, "request_image", old[0]), setattr(media_cfg, "get_key", old[1]), setattr(media_cfg, "add_usage", old[2]), setattr(media_cfg, "load", old[3])))

    def test_only_the_planned_picture_is_made_with_the_shorts_look_and_the_limits_and_it_is_not_paid_twice(self):
        with mock.patch("builtins.print"): self.assertEqual(B.make_pictures("blog-001"), 0)
        self.assertEqual(len(self.sent), 1); p, size = self.sent[0]; self.assertEqual(size, "1536x1024")
        self.assertTrue(p.startswith("A hand-written note")); self.assertIn("Paper-cut collage", p); self.assertIn("No words, letters, numbers", p)
        self.assertEqual(Image.open(os.path.join(self.D, "post_pic_i2.jpg")).size, (1200, 800)); self.assertEqual(len(self.spent), 1)
        with mock.patch("builtins.print"): B.make_pictures("blog-001")
        self.assertEqual((len(self.sent), len(self.spent)), (1, 1), "a picture that exists is not made again")
        self.assertTrue(B.pictures_done(self.D))

    def test_the_estimate_costs_nothing_and_a_plan_with_no_picture_is_done(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out): B.make_pictures("blog-001", estimate_only=True)
        e = json.loads(out.getvalue()); self.assertEqual((e["pictures"], e["size"]), (1, "1536x1024")); self.assertGreater(e["usd"], 0); self.assertEqual((self.sent, self.spent), ([], []))
        json.dump({**PLAN, "inline": [FLOW]}, open(os.path.join(self.D, "images.json"), "w")); self.assertTrue(B.pictures_done(self.D))

    def test_a_picture_over_the_run_cap_or_without_a_key_is_refused_before_any_spend(self):
        self.M.load = lambda: {"image_quality": "low", "image_size_landscape": "1536x1024", "max_run_usd": 0.0001, "image_model": ""}
        with mock.patch("builtins.print") as pr: self.assertEqual(B.make_pictures("blog-001"), 4)
        self.assertIn("over the run cap", pr.call_args[0][0]); self.assertEqual(self.sent, [])
        self.M.load = lambda: {"image_quality": "low", "image_size_landscape": "1536x1024", "max_run_usd": 5.0, "image_model": ""}; self.M.get_key = lambda n: ""
        with mock.patch("builtins.print") as pr: self.assertEqual(B.make_pictures("blog-001"), 4)
        self.assertIn("no OpenAI key", pr.call_args[0][0]); self.assertEqual(self.sent, [])


class Embed(Env):
    def drawn(self):
        with mock.patch.object(B, "_remotion", lambda c, p, o: png(o)), mock.patch("builtins.print"): B.render("blog-001")
        png(os.path.join(self.D, "post_pic_i2.jpg"))
        m = json.load(open(os.path.join(self.D, "post_images.json"))); m["inline"].append({"id": "i2", "kind": "picture", "file": "post_pic_i2.jpg", "alt": PIC["alt"], "after": PIC["after"]}); json.dump(m, open(os.path.join(self.D, "post_images.json"), "w"))

    def test_the_images_go_under_their_headings_the_cover_into_the_front_matter_and_a_second_run_changes_nothing(self):
        self.drawn()
        with mock.patch("builtins.print"): self.assertEqual(B.embed("blog-001"), 0)
        dv = open(os.path.join(self.D, "devto.md")).read(); la = open(os.path.join(self.D, "linkedin_article.md")).read(); base = "https://navaan.online/img/blog/blog-001/"
        self.assertRegex(dv, r"cover_image: https://navaan\.online/img/blog/blog-001/post_cover_devto-[0-9a-f]{8}\.png\n")
        fm = dv.split("---")[1]; self.assertIn("cover_image:", fm); self.assertNotIn("![", fm, "never inside the front matter")
        fig = re.search(r"!\[How an answer is made\]\((" + re.escape(base) + r"post_fig_i1-[0-9a-f]{8}\.png)\)", dv); self.assertTrue(fig)
        self.assertLess(dv.index("## Why it sounds sure"), dv.index(fig.group(0))); self.assertLess(dv.index(fig.group(0)), dv.index("Second paragraph."))   # after the first paragraph under its heading, not inside it
        self.assertIn("Still the same paragraph.\n\n![How an answer is made]", dv)
        self.assertRegex(dv, r"## What to do\n\nCheck the source\.\n\n!\[A crossed-out answer on a note\]"); self.assertIn("```py\nprint(1)\n```", dv, "code is left alone")
        self.assertNotIn("cover_image", la); self.assertEqual(la.count("!["), 2)   # the LinkedIn article has no front matter; its cover is uploaded in LinkedIn
        self.assertTrue(B.embedded(self.D)); self.assertEqual(len(os.listdir(os.path.join(self.bucket, "navaan", "blog", "blog-001"))), 4)   # two covers and two images, each under a hashed name
        with mock.patch("builtins.print"): B.embed("blog-001")
        self.assertEqual((open(os.path.join(self.D, "devto.md")).read(), open(os.path.join(self.D, "linkedin_article.md")).read()), (dv, la), "run twice: unchanged")

    def test_a_replaced_image_has_a_new_address_and_the_old_line_is_replaced_not_added(self):
        self.drawn()
        with mock.patch("builtins.print"): B.embed("blog-001")
        before = open(os.path.join(self.D, "devto.md")).read()
        Image.new("RGB", (40, 20), (200, 10, 10)).save(os.path.join(self.D, "post_fig_i1.png"))   # the figure is drawn again, different pixels
        with mock.patch("builtins.print"): B.embed("blog-001")
        after = open(os.path.join(self.D, "devto.md")).read(); self.assertNotEqual(before, after); self.assertEqual(after.count("![How an answer is made]"), 1)

    def test_a_skipped_figure_does_not_leave_the_step_waiting_forever(self):
        self.drawn(); m = json.load(open(os.path.join(self.D, "post_images.json"))); m["inline"] = [i for i in m["inline"] if i["id"] != "i1"]; json.dump(m, open(os.path.join(self.D, "post_images.json"), "w"))
        with mock.patch("builtins.print"): B.embed("blog-001")
        self.assertTrue(B.embedded(self.D)); self.assertNotIn("![How an answer is made]", open(os.path.join(self.D, "devto.md")).read())

    def test_the_address_is_the_public_host_and_a_missing_host_still_gives_a_working_path(self):
        self.assertEqual(B.public_base(), "https://navaan.online")
        with mock.patch.dict(os.environ, {"NAVAAN_PUBLIC_URL": "https://example.test/"}): self.assertEqual(B.public_base(), "https://example.test")
        with mock.patch.dict(os.environ, {"NAVAAN_LISTENER_HOSTS": "", "NAVAAN_PUBLIC_HOST": ""}): self.assertEqual(B.public_base(), "")


class Public(Env):
    def test_the_bucket_serves_only_the_images_the_studio_made_under_a_hashed_name(self):
        import media
        png(os.path.join(self.D, "post_cover_devto.png")); url, name = B.store("blog-001", os.path.join(self.D, "post_cover_devto.png"))
        self.assertRegex(name, r"^post_cover_devto-[0-9a-f]{8}\.png$"); data, etag, mime = media.blog_image("blog-001", name); self.assertEqual(mime, "image/png"); self.assertTrue(data.startswith(b"\x89PNG"))
        for bad_slug, bad_name in (("blog-001", "post_cover_devto.png"), ("blog-001", "../x-12345678.png"), ("blog-001", "x-12345678.gif"), ("../blog", name), ("blog-002", name), ("blog-001", "")): self.assertIsNone(media.blog_image(bad_slug, bad_name), (bad_slug, bad_name))


class Steps(Env):
    def due(self):
        import navaan as N
        return N.plan("blog-001")[1]

    def test_the_image_steps_follow_the_humanizer_and_only_the_picture_step_waits_for_credits(self):
        import navaan as N, navaan_common as C
        ids = [s["id"] for s in N.steps("blog-001", self.D)]; i = ids.index("humanize_check")
        self.assertEqual(ids[i + 1:i + 5], ["images_plan", "images", "blog_pictures", "images_embed"])
        rows = {s["id"]: s for s in N.steps("blog-001", self.D)}
        self.assertEqual({k for k, s in rows.items() if s.get("before") == "credits"}, {"blog_pictures"}); self.assertIn("credits", C.type_gates("blog"))
        self.assertIn("1 picture with OpenAI (about $", rows["blog_pictures"]["label"]); self.assertIn("about $", N.spend_what(rows["blog_pictures"]))
        json.dump({**PLAN, "inline": [FLOW]}, open(os.path.join(self.D, "images.json"), "w")); self.assertIn("none planned", {s["id"]: s for s in N.steps("blog-001", self.D)}["blog_pictures"]["label"])

    def test_the_skill_asks_for_figures_first_one_picture_at_most_and_a_checked_plan(self):
        t = open(os.path.join(HERE, "..", "skills", "blog-images", "SKILL.md"), encoding="utf-8").read()
        for w in ("Prefer `kind: \"figure\"`", "at most one per post", "blog_images.py check", "source_url", "Do not edit the drafts", "palette", "motif"): self.assertIn(w, t)


if __name__ == "__main__":
    unittest.main()
