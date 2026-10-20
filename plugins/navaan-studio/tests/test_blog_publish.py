"""Author: Navjyot Nishant
Created: 2026-10-20
Last updated: 2026-10-20
Description: posting a finished blog post through the APIs (NAV-78): the dev.to article as a draft first and live only when asked, the LinkedIn post as a link card with the cover, the owner's keys saved in Settings, and no key ever in a message.
"""
import io, json, os, sys, tempfile, unittest, urllib.error
from unittest import mock
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, HERE)
import _pgenv  # noqa: F401
import blog_publish as P
import media_cfg

KEY, TOKEN, AUTHOR = "devkey-0123456789abcdef", "AQV" + "x" * 60, "urn:li:person:abc123"
DEVTO = '---\ntitle: "Why answers sound sure"\ndescription: "Confidence is not evidence"\ntags: ai, llm\npublished: false\ncover_image: https://navaan.online/img/blog/blog-001/post_cover_devto-1a2b3c4d.png\n---\n\nThe hook [c1].\n\n## Why\n\nBody text [c2].\n'
POST = "Confident answers are not evidence.\n\n- Check the source\n- Check the date\n\nWhat do you check first?\n\n[ARTICLE_URL]\n\n#AIEngineering #Evals"


class Fake:
    """A stand-in for the network: records every call and answers from a script of (status, headers, body)."""
    def __init__(self, *answers): self.calls, self.answers = [], list(answers)
    def __call__(self, method, url, headers=None, body=None, timeout=30):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "body": body})
        st, h, b = self.answers.pop(0) if self.answers else (500, {}, b"no answer scripted")
        return st, h, (b if isinstance(b, bytes) else json.dumps(b).encode())


class Env(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name; self.addCleanup(lambda: os.environ.pop("NAVAAN_ROOT", None))
        import navaan_common as C
        if hasattr(C, "_CFG"): C._CFG = None
        self.D = os.path.join(self.tmp.name, "songs", "blog-001"); os.makedirs(self.D)
        json.dump({"slug": "blog-001", "type": "blog", "state": "draft", "approvals": {}}, open(os.path.join(self.D, "meta.json"), "w"))
        open(os.path.join(self.D, "devto.md"), "w").write(DEVTO); open(os.path.join(self.D, "linkedin_post.md"), "w").write(POST)
        self.keys = {"devto": KEY, "linkedin": TOKEN}
        for p in (mock.patch.object(media_cfg, "get_key", lambda n: self.keys.get(n, "")), mock.patch.object(media_cfg, "linkedin_author", lambda: AUTHOR)): p.start(); self.addCleanup(p.stop)

    def meta(self): return json.load(open(os.path.join(self.D, "meta.json")))
    def live_devto(self, url="https://dev.to/me/why-answers-sound-sure-1a2b"):
        m = self.meta(); m["published"] = {"devto": {"id": 77, "url": url, "published": True}}; json.dump(m, open(os.path.join(self.D, "meta.json"), "w"))


class DevTo(Env):
    ANS = (201, {}, {"id": 77, "url": "https://dev.to/me/why-answers-sound-sure-1a2b"})

    def test_the_article_is_made_from_the_draft_with_its_cover_and_without_markers_or_front_matter(self):
        a = P.devto_article(self.D, False)["article"]
        self.assertEqual((a["title"], a["tags"], a["description"], a["published"]), ("Why answers sound sure", "ai,llm", "Confidence is not evidence", False))
        self.assertEqual(a["main_image"], "https://navaan.online/img/blog/blog-001/post_cover_devto-1a2b3c4d.png"); self.assertEqual(a["body_markdown"], "The hook.\n\n## Why\n\nBody text.")
        open(os.path.join(self.D, "devto.md"), "w").write("---\ndescription: x\n---\n\nbody"); self.assertRaises(ValueError, P.devto_article, self.D, False)

    def test_the_first_post_is_a_draft_the_second_updates_it_and_going_live_is_asked_for(self):
        f = Fake(self.ANS, self.ANS, self.ANS, self.ANS)
        with mock.patch.object(P, "HTTP", f):
            r = P.devto_post("blog-001"); self.assertEqual((r["id"], r["published"], r["updated"]), (77, False, False))
            c = f.calls[0]; self.assertEqual((c["method"], c["url"]), ("POST", "https://dev.to/api/articles")); self.assertEqual(c["headers"]["api-key"], KEY); self.assertFalse(c["body"]["article"]["published"])
            r = P.devto_post("blog-001"); self.assertEqual((f.calls[1]["method"], f.calls[1]["url"]), ("PUT", "https://dev.to/api/articles/77")); self.assertTrue(r["updated"]); self.assertFalse(f.calls[1]["body"]["article"]["published"])
            r = P.devto_post("blog-001", publish=True); self.assertTrue(r["published"]); self.assertTrue(f.calls[2]["body"]["article"]["published"])
            P.devto_post("blog-001"); self.assertTrue(f.calls[3]["body"]["article"]["published"], "an article that is live stays live when it is saved again")
        self.assertEqual(self.meta()["published"]["devto"]["url"], "https://dev.to/me/why-answers-sound-sure-1a2b"); self.assertNotIn(KEY, json.dumps(self.meta()))

    def test_every_refusal_is_a_sentence_and_the_key_is_never_in_it(self):
        for ans, word in (((401, {}, {"error": "unauthorized"}), "refused the key"), ((422, {}, {"error": f"Title is too long {KEY}"}), "HTTP 422"), ((200, {}, {"id": 1}), "without the article's address")):
            with mock.patch.object(P, "HTTP", Fake(ans)):
                with self.assertRaises(RuntimeError) as cm: P.devto_post("blog-001")
            self.assertIn(word, str(cm.exception)); self.assertNotIn(KEY, str(cm.exception))
        self.keys["devto"] = ""; self.assertRaises(ValueError, P.devto_post, "blog-001")
        self.keys["devto"] = KEY; self.live_devto()
        with mock.patch.object(P, "HTTP", Fake((404, {}, {"error": "not found"}))): self.assertRaises(RuntimeError, P.devto_post, "blog-001")


class LinkedIn(Env):
    OK = (201, {"x-restli-id": "urn:li:share:123"}, {})
    INIT = (200, {}, {"value": {"uploadUrl": "https://upload.linkedin.test/u/1", "image": "urn:li:image:C49"}})

    def setUp(self):
        super().setUp(); self.live_devto()
        with open(os.path.join(self.D, "post_cover_linkedin.png"), "wb") as f: f.write(b"\x89PNGfake")

    def test_it_posts_the_text_with_the_article_as_a_link_card_and_the_cover_as_its_picture(self):
        f = Fake(self.INIT, (201, {}, b""), self.OK)
        with mock.patch.object(P, "HTTP", f): r = P.linkedin_post("blog-001")
        init, put, post = f.calls
        self.assertEqual((init["method"], init["url"]), ("POST", "https://api.linkedin.com/rest/images?action=initializeUpload")); self.assertEqual(init["body"], {"initializeUploadRequest": {"owner": AUTHOR}})
        self.assertEqual((put["method"], put["url"], put["body"]), ("PUT", "https://upload.linkedin.test/u/1", b"\x89PNGfake"))
        self.assertEqual((post["method"], post["url"]), ("POST", "https://api.linkedin.com/rest/posts"))
        h = post["headers"]; self.assertEqual((h["Authorization"], h["X-Restli-Protocol-Version"], h["Linkedin-Version"]), ("Bearer " + TOKEN, "2.0.0", "202610"))
        b = post["body"]; self.assertEqual((b["author"], b["visibility"], b["lifecycleState"], b["distribution"]["feedDistribution"]), (AUTHOR, "PUBLIC", "PUBLISHED", "MAIN_FEED"))
        self.assertIn("https://dev.to/me/why-answers-sound-sure-1a2b", b["commentary"]); self.assertNotIn("[ARTICLE_URL]", b["commentary"]); self.assertTrue(b["commentary"].endswith("#AIEngineering #Evals"))
        self.assertEqual(b["content"]["article"], {"source": "https://dev.to/me/why-answers-sound-sure-1a2b", "thumbnail": "urn:li:image:C49", "title": "Why answers sound sure", "description": "Confidence is not evidence"})
        self.assertEqual((r["id"], r["url"], r["card"]), ("urn:li:share:123", "https://www.linkedin.com/feed/update/urn:li:share:123/", True)); self.assertEqual(self.meta()["published"]["linkedin_post"]["id"], "urn:li:share:123")

    def test_a_picture_that_will_not_upload_still_gives_a_post_with_the_link_in_the_text(self):
        f = Fake((403, {}, {"message": "no"}), self.OK)
        with mock.patch.object(P, "HTTP", f): r = P.linkedin_post("blog-001")
        self.assertFalse(r["card"]); self.assertNotIn("content", f.calls[1]["body"]); self.assertIn("https://dev.to/me/", f.calls[1]["body"]["commentary"])

    def test_without_the_placeholder_the_address_goes_at_the_end_and_the_version_can_be_set(self):
        os.remove(os.path.join(self.D, "post_cover_linkedin.png")); open(os.path.join(self.D, "linkedin_post.md"), "w").write("Just text [c1]")
        f = Fake(self.OK)
        with mock.patch.object(P, "HTTP", f), mock.patch.object(P.C, "cfg", lambda k, d=None: "202701" if k == "blog.linkedin_version" else d): P.linkedin_post("blog-001")
        self.assertEqual(f.calls[0]["body"]["commentary"], "Just text\n\nhttps://dev.to/me/why-answers-sound-sure-1a2b"); self.assertEqual(f.calls[0]["headers"]["Linkedin-Version"], "202701")

    def test_it_waits_for_the_article_to_be_live_for_the_keys_and_is_posted_once(self):
        m = self.meta(); m["published"]["devto"]["published"] = False; json.dump(m, open(os.path.join(self.D, "meta.json"), "w"))
        with self.assertRaises(ValueError) as cm: P.linkedin_post("blog-001")
        self.assertIn("Publish the dev.to article first", str(cm.exception)); self.live_devto()
        self.keys["linkedin"] = ""; self.assertRaises(ValueError, P.linkedin_post, "blog-001"); self.keys["linkedin"] = TOKEN
        open(os.path.join(self.D, "linkedin_post.md"), "w").write("x" * 3001); self.assertRaises(ValueError, P.linkedin_post, "blog-001"); open(os.path.join(self.D, "linkedin_post.md"), "w").write(POST)
        with mock.patch.object(P, "HTTP", Fake(self.INIT, (201, {}, b""), self.OK)): P.linkedin_post("blog-001")
        with mock.patch.object(P, "HTTP", Fake()) as _:
            with self.assertRaises(ValueError) as cm: P.linkedin_post("blog-001")
        self.assertIn("already on LinkedIn", str(cm.exception))

    def test_every_refusal_is_a_sentence_and_the_token_is_never_in_it(self):
        for ans, word in (((401, {}, {"message": "bad"}), "refused the token"), ((403, {}, {"message": "ACCESS_DENIED"}), "w_member_social"), ((422, {}, {"message": f"nope {TOKEN}"}), "HTTP 422"), ((201, {}, {}), "no post id")):
            os.remove(os.path.join(self.D, "post_cover_linkedin.png")) if os.path.exists(os.path.join(self.D, "post_cover_linkedin.png")) else None
            with mock.patch.object(P, "HTTP", Fake(ans)):
                with self.assertRaises(RuntimeError) as cm: P.linkedin_post("blog-001")
            self.assertIn(word, str(cm.exception)); self.assertNotIn(TOKEN, str(cm.exception))

    def test_status_says_what_is_possible_and_never_holds_a_key(self):
        s = P.status(self.D, self.meta()); self.assertEqual(s["devto"], {"key": True, "posted": True, "published": True, "url": "https://dev.to/me/why-answers-sound-sure-1a2b"})
        self.assertEqual((s["linkedin"]["key"], s["linkedin"]["ready"], s["linkedin"]["text"], s["linkedin"]["posted"]), (True, True, True, False)); self.assertNotIn(KEY, json.dumps(s)); self.assertNotIn(TOKEN, json.dumps(s))
        self.keys.update(devto="", linkedin=""); s = P.status(self.D, {}); self.assertEqual((s["devto"]["key"], s["linkedin"]["key"], s["devto"]["posted"], s["linkedin"]["ready"]), (False, False, False, False))


class Keys(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        p = mock.patch.dict(os.environ, {"NAVAAN_CONF_DIR": self.tmp.name, "NAVAAN_CONF_DIR_X": "1"}); p.start(); self.addCleanup(p.stop)
        for v in ("DEVTO_API_KEY", "LINKEDIN_TOKEN"): os.environ.pop(v, None)

    def answer(self, status=200, body=None):
        def urlopen(req, timeout=20):
            if status != 200: raise urllib.error.HTTPError(req.full_url, status, "x", {}, io.BytesIO(json.dumps({"message": "refused"}).encode()))
            return io.BytesIO(json.dumps(body or {}).encode())
        return mock.patch.object(media_cfg.urllib.request, "urlopen", urlopen)

    def test_the_devto_key_is_tested_with_one_read_saved_with_mode_600_and_a_wrong_one_changes_nothing(self):
        with self.answer(200, {"username": "me"}): r = media_cfg.key_save("devto", "DEVTO_API_KEY=" + KEY)
        self.assertTrue(r["ok"]); path = os.path.join(self.tmp.name, "devto.env"); self.assertEqual(open(path).read(), f"DEVTO_API_KEY={KEY}\n"); self.assertEqual(oct(os.stat(path).st_mode & 0o777), "0o600"); self.assertEqual(media_cfg.get_key("devto"), KEY)
        with self.answer(401): self.assertRaises(ValueError, media_cfg.key_save, "devto", "newkey-0123456789abcdef"); 
        self.assertEqual(media_cfg.get_key("devto"), KEY); self.assertTrue(media_cfg.key_state()["devto"])
        self.assertRaises(ValueError, media_cfg.key_save, "devto", "a b")

    def test_the_linkedin_token_gives_its_member_from_openid_or_needs_the_id_and_a_wrong_one_changes_nothing(self):
        with self.answer(200, {"sub": "abc123", "name": "Navjyot N"}): r = media_cfg.linkedin_save(TOKEN)
        self.assertIn("Navjyot N", r["note"]); self.assertEqual(media_cfg.linkedin_author(), "urn:li:person:abc123"); self.assertEqual(media_cfg.get_key("linkedin"), TOKEN)
        with self.answer(401): self.assertRaises(ValueError, media_cfg.linkedin_save, "AQV" + "y" * 60, "zzz999")
        self.assertEqual(media_cfg.get_key("linkedin"), TOKEN, "a wrong paste never replaces a working login")
        with self.answer(403):
            with self.assertRaises(ValueError) as cm: media_cfg.linkedin_save("AQV" + "y" * 60)
            self.assertIn("member id", str(cm.exception))
            media_cfg.linkedin_save("AQV" + "y" * 60, "urn:li:person:Q1w2"); self.assertEqual(media_cfg.linkedin_author(), "urn:li:person:Q1w2"); media_cfg.linkedin_save("AQV" + "z" * 60, "plainid77"); self.assertEqual(media_cfg.linkedin_author(), "urn:li:person:plainid77")
        for bad in ("has space", "x"): self.assertRaises(ValueError, media_cfg.linkedin_save, bad, "abc123")
        with self.answer(200, {}): self.assertRaises(ValueError, media_cfg.linkedin_save, "AQV" + "q" * 60, "bad id!")


class Steps(Env):
    def test_the_linkedin_post_is_written_after_the_images_and_the_posting_is_not_a_step(self):
        import navaan as N
        ids = [s["id"] for s in N.steps("blog-001", self.D)]; self.assertEqual(ids[ids.index("images_embed") + 1], "linkedin_post"); self.assertFalse(any(i in ids for i in ("devto_post", "post_devto", "publish_devto")))
        t = open(os.path.join(HERE, "..", "skills", "blog-linkedin-post", "SKILL.md"), encoding="utf-8").read()
        for w in ("[ARTICLE_URL]", "plain text only", "3,000", "Do not post anything"): self.assertIn(w, t)


if __name__ == "__main__":
    unittest.main()
