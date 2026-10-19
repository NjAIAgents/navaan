"""NAV-71: a blog item starts from a keyword, looks up what is trending in free sources, and waits for the owner to pick one of 5 topics."""
import json, os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401

HN = json.dumps({"hits": [{"title": "Agents in prod", "url": "https://example.com/a", "objectID": "1", "points": 412, "num_comments": 90}]})
DEVTO = json.dumps([{"title": "Building agents", "url": "https://dev.to/x/agents", "public_reactions_count": 50, "comments_count": 4, "tag_list": ["ai"]}])
GT_EXPLORE = ")]}'\n" + json.dumps({"widgets": [{"id": "RELATED_QUERIES", "token": "t", "request": {"x": 1}}]})
GT_RSS = '<?xml version="1.0"?><rss xmlns:ht="https://trends.google.com/trending/rss" version="2.0"><channel><item><title>openai devday</title><ht:approx_traffic>200K+</ht:approx_traffic></item></channel></rss>'
GT_RELATED = ")]}',\n" + json.dumps({"default": {"rankedList": [{"rankedKeyword": []}, {"rankedKeyword": [{"query": "ai agents mcp", "formattedValue": "+250%"}]}]}})


def fake_get(fail=()):
    def get(url, timeout=15):
        for k in fail:
            if k in url: raise OSError("HTTP Error 429: Too Many Requests")
        if "hn.algolia" in url: return HN
        if "dev.to" in url: return DEVTO
        if "trending/rss" in url: return GT_RSS
        if "relatedsearches" in url: return GT_RELATED
        if "trends.google" in url: return GT_EXPLORE
        raise AssertionError(url)
    return get


class Blog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan_common as C, navaan as N, trend_sources as T
        self.C, self.N, self.T = C, N, T
        if hasattr(C, "_CFG"): C._CFG = None
        self.D = os.path.join(C.songs_root(), "blog-001"); os.makedirs(self.D)
        json.dump({"slug": "blog-001", "type": "blog", "state": "draft", "approvals": {}}, open(os.path.join(self.D, "meta.json"), "w"))
        open(os.path.join(self.D, "brief.md"), "w").write("# Blog\n\n## Idea\n\nAI agents\n\n## Options\n\n- audience: auto\n")

    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup()

    def test_it_is_a_type_of_its_own_with_the_topic_approval_and_no_channel_account(self):
        self.assertIn("blog", self.C.CONTENT_TYPES); self.assertEqual(self.C.TYPE_PREFIX["blog"], "blog")
        self.assertEqual(self.C.type_gates("blog")[0], "topic"); self.assertFalse(self.C.is_short("blog")); self.assertFalse(self.N.ig_enabled({"type": "blog"}))
        st = self.N.steps("blog-001", self.D); ids = [s["id"] for s in st]
        self.assertEqual(ids[:2], ["trends", "topics"]); self.assertIn("archive", ids); self.assertIn("cleanup", ids)
        topics = st[1]; self.assertEqual(topics["after"], "topic"); self.assertEqual(topics["skill"], "blog-topics"); self.assertIn("WebSearch", topics["tools"])
        self.assertEqual(self.C.with_site_link("Post body", None, itype="blog"), "Post body")   # the owner's own byline: no NAVAAN line

    def test_the_keyword_comes_from_the_brief_and_the_template_placeholder_is_not_one(self):
        self.assertEqual(self.T.keyword(self.D), "AI agents")
        open(os.path.join(self.D, "brief.md"), "w").write("## Idea\n\n(write the keyword, field or area here)\n")
        self.assertEqual(self.T.keyword(self.D), "")

    def test_every_source_is_read_when_all_answer(self):
        with mock.patch.object(self.T, "get", fake_get()): r = self.T.collect("AI agents", now=1_800_000_000)
        s = r["sources"]; self.assertTrue(all(v["ok"] for v in s.values()))
        self.assertEqual(s["hacker_news"]["items"][0]["points"], 412); self.assertEqual(s["devto"]["items"][0]["url"], "https://dev.to/x/agents")
        self.assertEqual(s["google_trends"]["items"], [{"query": "ai agents mcp", "rise": "+250%"}])

    def test_one_failing_source_is_recorded_and_the_others_still_count(self):
        with mock.patch.object(self.T, "get", fake_get(fail=("trends.google",))): s = self.T.collect("AI agents")["sources"]
        self.assertFalse(s["google_trends"]["ok"]); self.assertIn("429", s["google_trends"]["error"]); self.assertTrue(s["hacker_news"]["ok"]); self.assertTrue(s["devto"]["ok"])

    def test_a_refused_rising_query_falls_back_to_the_daily_trending_searches(self):
        with mock.patch.object(self.T, "get", fake_get(fail=("relatedsearches",))): s = self.T.collect("AI agents")["sources"]
        self.assertTrue(s["google_trends"]["ok"]); self.assertEqual(s["google_trends"]["items"], [{"query": "openai devday", "traffic": "200K+", "daily": True}])

    def test_all_sources_failing_still_writes_the_file_so_the_web_search_can_carry_on(self):
        with mock.patch.object(self.T, "get", fake_get(fail=("hn.algolia", "dev.to", "trends.google"))): self.T.main(["blog-001"])
        r = json.load(open(os.path.join(self.D, "trend_sources.json"))); self.assertFalse(any(v["ok"] for v in r["sources"].values())); self.assertEqual(r["keyword"], "AI agents")

    def test_no_topic_counts_as_chosen_until_the_owner_picks_one(self):
        self.assertFalse(self.N.topic_chosen(self.D))
        t = {"candidates": [{"title": f"T{i}"} for i in range(5)], "chosen": None}; json.dump(t, open(os.path.join(self.D, "topics.json"), "w"))
        self.assertFalse(self.N.topic_chosen(self.D))
        t["chosen"] = {"title": "T2", "index": 2}; json.dump(t, open(os.path.join(self.D, "topics.json"), "w"))
        self.assertTrue(self.N.topic_chosen(self.D))


class Loop(unittest.TestCase):
    """NAV-72/73: claims are checked for shape; a failing fact check sends the claims back to the writer twice at most, then stops for the owner."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan_common as C, navaan as N, blog_loop as B
        self.C, self.N, self.B = C, N, B
        if hasattr(C, "_CFG"): C._CFG = None
        self.D = os.path.join(C.songs_root(), "blog-001"); os.makedirs(self.D); self.t = 1_800_000_000
        json.dump({"slug": "blog-001", "type": "blog", "state": "draft", "approvals": {}}, open(os.path.join(self.D, "meta.json"), "w"))

    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup()

    def put(self, name, body=""):
        """Write a file one second after the previous one, so the order of steps is the order of mtimes."""
        self.t += 1; p = os.path.join(self.D, name)
        with open(p, "w") as f: f.write(body if isinstance(body, str) else json.dumps(body))
        os.utime(p, (self.t, self.t))

    def loop(self):
        """Run the loop step, then move what it just wrote onto the test's clock, as if it ran right after the last file."""
        names = ("fix_notes.md", "factcheck_rounds.json", "needs_you.txt"); mt = lambda n: os.path.getmtime(os.path.join(self.D, n)) if os.path.exists(os.path.join(self.D, n)) else None
        before = {n: mt(n) for n in names}; rc = self.B.factcheck("blog-001"); self.t += 1
        for n in names:
            if mt(n) is not None and mt(n) != before[n]: os.utime(os.path.join(self.D, n), (self.t, self.t))
        return rc

    def draft(self):
        for n in ("devto.md", "linkedin_article.md", "draft.json"): self.put(n, "x")

    def check(self, verdict):
        self.put("factcheck.json", {"verdict": verdict, "claims": [{"id": "c2", "text": "X is 40% faster", "status": "verified" if verdict == "pass" else "contradicted", "note": "the source says 14%"}]})

    def due(self): return self.N.plan("blog-001")[1]

    def test_claims_need_ids_text_a_web_source_and_whether_it_is_primary(self):
        ok = {"claims": [{"id": "c1", "text": "A", "source_url": "https://a.dev/x", "evidence": "A.", "primary": True}]}
        self.assertEqual(self.B.claims_errors(ok), [])
        self.assertTrue(self.B.claims_errors({"claims": []}))
        bad = self.B.claims_errors({"claims": [{"id": "c1", "text": "", "source_url": "a.dev", "primary": "yes"}, {"id": "c1", "text": "B", "source_url": "https://b", "primary": False}]})
        self.assertEqual(len(bad), 4)   # no text, not a web address, primary not a bool, repeated id

    def test_a_pass_on_the_first_check_ends_the_loop(self):
        self.put("outline.md"); self.draft(); self.check("pass")
        self.assertEqual(self.loop(), 0); self.assertTrue(self.B.passed(self.D)); self.assertFalse(os.path.exists(os.path.join(self.D, "fix_notes.md")))

    def test_a_fail_goes_back_to_the_writer_twice_and_then_stops_for_the_owner(self):
        self.put("outline.md"); self.draft(); self.check("fail")
        self.assertEqual(self.loop(), 0); self.assertTrue(self.B.fix_pending(self.D)); self.assertEqual(self.B.rounds(self.D), 1)
        self.assertIn("c2", open(os.path.join(self.D, "fix_notes.md")).read())
        self.draft(); self.assertFalse(self.B.fix_pending(self.D)); self.assertFalse(self.B.checked(self.D))   # the rewrite needs a new check
        self.check("fail"); self.assertEqual(self.loop(), 0); self.assertEqual(self.B.rounds(self.D), 2)
        self.draft(); self.check("fail"); notes = os.path.getmtime(os.path.join(self.D, "fix_notes.md"))
        self.assertEqual(self.loop(), 5)   # a third rewrite is not asked for
        self.assertEqual(os.path.getmtime(os.path.join(self.D, "fix_notes.md")), notes); self.assertFalse(self.B.fix_pending(self.D))
        self.assertIn("still fails after 2 rewrites", open(os.path.join(self.D, "needs_you.txt")).read())
        self.draft(); self.check("pass"); self.assertEqual(self.loop(), 0); self.assertFalse(os.path.exists(os.path.join(self.D, "needs_you.txt")))   # the owner's fix clears the wait

    def test_a_pass_in_the_second_round_ends_the_loop(self):
        self.put("outline.md"); self.draft(); self.check("fail"); self.loop()
        self.draft(); self.check("pass"); self.assertEqual(self.loop(), 0); self.assertTrue(self.B.passed(self.D))

    def test_a_new_outline_starts_the_count_again(self):
        self.put("outline.md"); self.draft(); self.check("fail"); self.loop(); self.assertEqual(self.B.rounds(self.D), 1)
        self.put("outline.md"); self.assertEqual(self.B.rounds(self.D), 0)

    def test_the_steps_run_in_order_and_the_editor_does_not_restart_the_fact_check(self):
        json.dump({"candidates": [{"title": "T"}], "chosen": {"title": "T", "index": 0}}, open(os.path.join(self.D, "topics.json"), "w")); os.utime(os.path.join(self.D, "topics.json"), (self.t, self.t))
        json.dump({**json.load(open(os.path.join(self.D, "meta.json"))), "approvals": {"topic": {"by": "test"}}}, open(os.path.join(self.D, "meta.json"), "w"))
        self.put("trend_sources.json", {}); self.assertEqual(self.due(), {"type": "run", "step": "research"})
        self.put("research.md", "r"); self.put("claims.json", {"claims": [{"id": "c1", "text": "A", "source_url": "https://a.dev", "evidence": "A", "primary": True}]})
        self.assertEqual(self.due()["step"], "outline"); self.put("outline.md", "o")
        self.assertEqual(self.due()["step"], "write"); self.draft()
        self.assertEqual(self.due()["step"], "factcheck"); self.check("fail")
        self.assertEqual(self.due()["step"], "factcheck_loop"); self.loop()
        self.assertEqual(self.due()["step"], "write"); self.draft(); self.check("pass")
        self.assertEqual(self.due()["step"], "review"); self.put("review_notes.md", "n")
        self.assertEqual(self.due()["step"], "edit"); self.put("devto.md", "edited"); self.put("linkedin_article.md", "edited"); self.put("edit.json", {})
        self.assertNotIn(self.due().get("step"), ("write", "factcheck", "factcheck_loop", "review", "edit"))


if __name__ == "__main__":
    unittest.main()
