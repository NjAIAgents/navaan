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

    def test_a_keyword_in_a_second_idea_section_counts_when_the_first_is_still_the_placeholder(self):
        open(os.path.join(self.D, "brief.md"), "w").write("## Idea\n\n(write the keyword, field or area here)\n\n## Options\n\n- audience: auto\n\n## Idea\n\nAI agents\n")
        self.assertEqual(self.T.keyword(self.D), "AI agents")   # a brief written this way before the creation fix still works
        open(os.path.join(self.D, "brief.md"), "w").write("## Idea\n\n\n## Options\n\n- audience: auto\n")
        self.assertEqual(self.T.keyword(self.D), "")

    def test_a_blog_started_from_a_keyword_has_that_keyword_in_its_brief(self):
        import new_song
        new_song.create("blog-002", "blog", "Postgres tuning")
        brief = open(os.path.join(self.C.songs_root(), "blog-002", "brief.md")).read()
        self.assertEqual(self.T.keyword(os.path.join(self.C.songs_root(), "blog-002")), "Postgres tuning"); self.assertEqual(brief.count("## Idea"), 1)   # in the template's own place, not a second section after it

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
        self.cap = B.MAX_ROUNDS; B.MAX_ROUNDS = 2   # the loop's logic is tested with a short cap
        json.dump({"slug": "blog-001", "type": "blog", "state": "draft", "approvals": {}}, open(os.path.join(self.D, "meta.json"), "w"))

    def tearDown(self):
        os.environ.pop("NAVAAN_ROOT", None); self.tmp.cleanup(); self.B.MAX_ROUNDS = self.cap

    def put(self, name, body=""):
        """Write a file one second after the previous one, so the order of steps is the order of mtimes."""
        self.t += 1; p = os.path.join(self.D, name)
        with open(p, "w") as f: f.write(body if isinstance(body, str) else json.dumps(body))
        os.utime(p, (self.t, self.t))

    def loop(self):
        """Run the loop step, then move what it just wrote onto the test's clock, as if it ran right after the last file."""
        names = ("fix_notes.md", "factcheck_rounds.json", "needs_you.txt", "research_more.md"); mt = lambda n: os.path.getmtime(os.path.join(self.D, n)) if os.path.exists(os.path.join(self.D, n)) else None
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
        self.assertIn("still fails after 2 rounds", open(os.path.join(self.D, "needs_you.txt")).read())
        self.draft(); self.check("pass"); self.assertEqual(self.loop(), 0); self.assertFalse(os.path.exists(os.path.join(self.D, "needs_you.txt")))   # the owner's fix clears the wait

    def test_after_the_stop_the_owners_own_edit_is_fact_checked_again(self):   # blog-003: Run re-read the old verdict and stopped again, forever
        self.put("outline.md"); self.draft(); self.check("fail"); self.loop(); self.draft(); self.check("fail"); self.loop(); self.draft(); self.check("fail")
        self.assertEqual(self.loop(), 5); self.assertTrue(self.B.checked(self.D))
        self.put("devto.md", "fixed")      # the owner edits in the Posts tab: draft.json is untouched
        self.assertFalse(self.B.checked(self.D)); self.assertFalse(next(r for r in self.N.plan("blog-001")[0] if r["id"] == "factcheck")["done"])   # so the fact check runs again on the edit
        self.check("pass"); self.assertEqual(self.loop(), 0); self.assertFalse(os.path.exists(os.path.join(self.D, "needs_you.txt"))); self.assertTrue(self.B.passed(self.D))

    def test_a_reset_count_starts_a_new_round_and_clears_the_old_stop(self):   # blog-003: the stop notice stayed up while the new loop ran
        self.put("outline.md"); self.draft(); self.check("fail"); self.loop(); self.draft(); self.check("fail"); self.loop(); self.draft(); self.check("fail")
        self.assertEqual(self.loop(), 5)
        os.remove(os.path.join(self.D, "factcheck_rounds.json"))
        self.assertEqual(self.loop(), 0); self.assertTrue(self.B.fix_pending(self.D)); self.assertFalse(os.path.exists(os.path.join(self.D, "needs_you.txt")))

    def test_run_again_on_the_stop_without_an_edit_starts_two_more_rounds(self):   # blog-003: Run only stopped again with the same message
        self.put("outline.md"); self.draft(); self.check("fail"); self.loop(); self.draft(); self.check("fail"); self.loop(); self.draft(); self.check("fail")
        self.assertEqual(self.loop(), 5)
        self.assertEqual(self.loop(), 0); self.assertEqual(self.B.rounds(self.D), 1); self.assertTrue(self.B.fix_pending(self.D))
        self.assertFalse(os.path.exists(os.path.join(self.D, "needs_you.txt")))
        self.draft(); self.check("fail"); self.loop(); self.draft(); self.check("fail"); self.assertEqual(self.loop(), 5)   # still bounded: two rounds per press

    def test_a_pass_in_the_second_round_ends_the_loop(self):
        self.put("outline.md"); self.draft(); self.check("fail"); self.loop()
        self.draft(); self.check("pass"); self.assertEqual(self.loop(), 0); self.assertTrue(self.B.passed(self.D))

    def test_a_new_topic_starts_the_count_again(self):
        self.put("outline.md"); self.draft(); self.check("fail"); self.loop(); self.assertEqual(self.B.rounds(self.D), 1)
        self.put("outline.md"); self.assertEqual(self.B.rounds(self.D), 1)   # a loop back through research may not reset the cap
        self.put("topics.json", {}); self.assertEqual(self.B.rounds(self.D), 0)

    def test_an_unsourced_statement_goes_to_research_first_then_the_writer_without_a_new_outline(self):   # blog-003: the writer could only guess, twice
        json.dump({"candidates": [{"title": "T"}], "chosen": {"title": "T", "index": 0}}, open(os.path.join(self.D, "topics.json"), "w")); os.utime(os.path.join(self.D, "topics.json"), (self.t, self.t))
        json.dump({**json.load(open(os.path.join(self.D, "meta.json"))), "approvals": {"topic": {"by": "test"}}}, open(os.path.join(self.D, "meta.json"), "w"))
        claims = {"claims": [{"id": "c1", "text": "A", "source_url": "https://a.dev", "evidence": "A", "primary": True}]}
        self.put("trend_sources.json", {}); self.put("research.md", "r"); self.put("claims.json", claims); self.put("outline.md", "o"); self.draft()
        self.put("factcheck.json", {"verdict": "fail", "claims": [{"id": None, "text": "Most teams never assign it.", "draft": "linkedin_article.md", "status": "unsourced", "note": "no marker"},
                                                                  {"id": "c1", "text": "A", "status": "contradicted", "note": "the source says B"}]})
        self.assertEqual(self.loop(), 0); self.t += 1; os.utime(os.path.join(self.D, "research_more.md"), (self.t - 1, self.t - 1))
        ask = open(os.path.join(self.D, "research_more.md")).read(); self.assertIn("Most teams never assign it.", ask); self.assertIn("c1 (contradicted): A", ask)   # a wrong claim goes to research too
        notes = open(os.path.join(self.D, "fix_notes.md")).read(); self.assertIn("no marker: Most teams", notes); self.assertIn("both drafts", notes); self.assertNotIn("None:", notes)
        self.assertEqual(self.due()["step"], "research")   # look for a source before the rewrite
        self.put("claims.json", {"claims": claims["claims"] + [{"id": "c2", "text": "Most teams never assign it.", "source_url": "https://b.dev", "evidence": "B", "primary": True}]})
        self.assertEqual(self.due()["step"], "write")      # the outline is not redone, the writer fixes
        self.draft(); self.check("pass"); self.assertEqual(self.loop(), 0); self.assertEqual(self.due()["step"], "review")

    def test_a_wrong_claim_goes_back_to_research_too(self):   # owner, 2026-10-28: whatever the fact check finds goes to research first
        self.put("claims.json", {}); self.put("outline.md"); self.draft(); self.check("fail"); self.loop()
        ask = open(os.path.join(self.D, "research_more.md")).read(); self.assertIn("c2 (contradicted): X is 40% faster", ask); self.assertIn("the source says 14%", ask)
        self.assertTrue(self.B.research_pending(self.D))

    def test_the_cap_is_five_rounds(self):
        self.assertEqual(self.cap, 5)

    def test_the_steps_run_in_order_and_the_editor_does_not_restart_the_fact_check(self):
        json.dump({"candidates": [{"title": "T"}], "chosen": {"title": "T", "index": 0}}, open(os.path.join(self.D, "topics.json"), "w")); os.utime(os.path.join(self.D, "topics.json"), (self.t, self.t))
        json.dump({**json.load(open(os.path.join(self.D, "meta.json"))), "approvals": {"topic": {"by": "test"}}}, open(os.path.join(self.D, "meta.json"), "w"))
        self.put("trend_sources.json", {}); self.assertEqual(self.due(), {"type": "run", "step": "research"})
        self.put("research.md", "r"); self.put("claims.json", {"claims": [{"id": "c1", "text": "A", "source_url": "https://a.dev", "evidence": "A", "primary": True}]})
        self.assertEqual(self.due()["step"], "outline"); self.put("outline.md", "o")
        self.assertEqual(self.due()["step"], "write"); self.draft()
        self.assertEqual(self.due()["step"], "factcheck"); self.check("fail")
        self.assertEqual(self.due()["step"], "factcheck_loop"); self.loop()
        self.assertEqual(self.due()["step"], "research"); self.put("claims.json", {"claims": [{"id": "c1", "text": "A", "source_url": "https://a.dev", "evidence": "A", "primary": True}]})   # research looks again first
        self.assertEqual(self.due()["step"], "write"); self.draft(); self.check("pass")
        self.assertEqual(self.due()["step"], "review"); self.put("review_notes.md", "n")
        self.assertEqual(self.due()["step"], "edit"); self.put("devto.md", "edited"); self.put("linkedin_article.md", "edited"); self.put("edit.json", {})
        self.assertNotIn(self.due().get("step"), ("write", "factcheck", "factcheck_loop", "review", "edit"))

    # ---- NAV-74 / NAV-89: the humanizer changes the sound, never the facts ----
    FRONT = '---\ntitle: "Why answers sound sure"\ndescription: "Confidence is not evidence"\ntags: ai, llm\npublished: false\n---\n\n'
    BODY = ("In today's fast-paced world, models are not just fast, they are robust [c1]. The study found 40% fewer errors across 1,200 runs [c2], see https://example.org/study.\n\n"
            "```py\nprint(1 + 2)\n```\n\n![chart](https://x.test/c1.png)\n\nIt took 3 ms on 2 cores [c3].\n")

    def test_a_rewrite_that_only_changes_the_sound_passes_the_check(self):
        after = self.FRONT + ("Models are fast and they hold up [c1]. The study found 40% fewer errors across 1,200 runs [c2]; the details are at https://example.org/study.\n\n"
                              "```py\nprint(1 + 2)\n```\n\n![chart](https://x.test/c1.png)\n\nThat was 3 ms on 2 cores [c3].\n")
        self.assertEqual(self.B.humanize_problems(self.FRONT + self.BODY, after, devto=True), [])

    def test_a_rewrite_that_drops_or_moves_a_fact_is_named(self):
        before = self.FRONT + self.BODY
        for old, new, word in (("[c2]", "", "claim markers"), ("40%", "50%", "numbers"), ("1,200", "1,000", "numbers"), ("https://example.org/study", "https://example.org/other", "links"),
                               ("print(1 + 2)", "print(3)", "code blocks"), ("![chart](https://x.test/c1.png)", "", "images"), ("3 ms on 2 cores", "3 ms on 2 cores and 4 threads", "numbers")):
            problems = self.B.humanize_problems(before, before.replace(old, new), devto=True)
            self.assertTrue(any(word in x for x in problems), (old, problems))

    def test_the_front_matter_must_stay_valid_and_the_length_close(self):
        before = self.FRONT + self.BODY
        self.assertTrue(any("front matter is gone" in x for x in self.B.humanize_problems(before, self.BODY, devto=True)))
        self.assertTrue(any("published must stay false" in x for x in self.B.humanize_problems(before, before.replace("published: false", "published: true"), devto=True)))
        self.assertTrue(any("tags" in x for x in self.B.humanize_problems(before, before.replace("tags: ai, llm", "tags: ai, llm, a, b, c"), devto=True)))
        self.assertTrue(any("tags" in x for x in self.B.humanize_problems(before, before.replace("tags: ai, llm", "tags: AI, llm"), devto=True)))
        self.assertTrue(any("160" in x for x in self.B.humanize_problems(before, before.replace("Confidence is not evidence", "x" * 170), devto=True)))
        self.assertTrue(any("words" in x for x in self.B.humanize_problems(before, before + "word " * 200, devto=True)))

    def test_prep_keeps_the_edited_drafts_and_the_check_reads_them_and_asks_the_owner_when_a_fact_moved(self):
        self.put("devto.md", self.FRONT + self.BODY); self.put("linkedin_article.md", self.BODY)
        self.assertEqual(self.B.humanize_prep("blog-001"), 0); self.assertTrue(os.path.isfile(os.path.join(self.D, "humanize_before", "devto.md")))
        self.assertEqual(self.B.humanize_check("blog-001"), 0); self.assertTrue(json.load(open(os.path.join(self.D, "humanize_check.json")))["ok"])   # nothing changed yet
        self.put("devto.md", (self.FRONT + self.BODY).replace("40%", "45%")); rc = self.B.humanize_check("blog-001")
        self.assertEqual(rc, 5); said = open(os.path.join(self.D, "needs_you.txt")).read(); self.assertIn("humanize_before/", said); self.assertIn("devto.md: the numbers changed", said)
        self.put("devto.md", self.FRONT + self.BODY); self.assertEqual(self.B.humanize_check("blog-001"), 0); self.assertFalse(os.path.exists(os.path.join(self.D, "needs_you.txt")), "fixed: no longer waiting")

    def test_the_humanizer_runs_after_the_edit_in_three_steps_and_does_not_restart_the_fact_check(self):
        json.dump({"candidates": [{"title": "T"}], "chosen": {"title": "T", "index": 0}}, open(os.path.join(self.D, "topics.json"), "w")); os.utime(os.path.join(self.D, "topics.json"), (self.t, self.t))
        json.dump({**json.load(open(os.path.join(self.D, "meta.json"))), "approvals": {"topic": {"by": "test"}}}, open(os.path.join(self.D, "meta.json"), "w"))
        self.put("trend_sources.json", {}); self.put("research.md", "r"); self.put("claims.json", {"claims": [{"id": "c1", "text": "A", "source_url": "https://a.dev", "evidence": "A", "primary": True}]}); self.put("outline.md", "o")
        self.draft(); self.check("pass"); self.put("review_notes.md", "n"); self.put("edit.json", {})
        self.assertEqual(self.due()["step"], "humanize_prep")
        self.put("devto.md", self.FRONT + self.BODY); self.put("linkedin_article.md", self.BODY); self.put("edit.json", {}); self.B.humanize_prep("blog-001")
        for n in ("devto.md", "linkedin_article.md"): self.t += 1; os.utime(os.path.join(self.D, "humanize_before", n), (self.t, self.t))
        self.assertEqual(self.due()["step"], "humanize")
        self.put("humanize.json", {"changed": ["opener"]}); self.put("devto.md", self.FRONT + self.BODY.replace("In today's fast-paced world, ", "")); self.put("linkedin_article.md", self.BODY)   # the drafts change, draft.json does not
        self.assertEqual(self.due()["step"], "humanize_check"); self.assertTrue(self.B.checked(self.D), "the fact check still stands")
        self.B.humanize_check("blog-001"); self.t += 1; os.utime(os.path.join(self.D, "humanize_check.json"), (self.t, self.t))
        self.assertNotIn(self.due().get("step"), ("humanize_prep", "humanize", "humanize_check", "factcheck", "write", "edit"))

    def test_the_skill_keeps_markers_numbers_links_code_and_does_not_touch_the_fact_check_files(self):
        t = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills", "blog-humanizer", "SKILL.md"), encoding="utf-8").read()
        for w in ("claim marker", "fenced code block", "humanize.json", "draft.json", "factcheck.json", "published: false", "Do not add a fact"): self.assertIn(w, t)


if __name__ == "__main__":
    unittest.main()
