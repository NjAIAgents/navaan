"""NAV-4: item state in Postgres (studio_store). Each test gets its own songs folder and so its own throwaway schema (_pgenv)."""
import json, os, sys, tempfile, threading, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import navaan_common as C
import studio_store as S

# the shape of a real production item (keys and value types), with made-up values
REAL = {"slug": "song-001", "state": "published", "type": "music", "lyrics_loops": 2, "style_loops": 1, "suno_url": "https://suno.com/s/x", "suno_model": "v5",
        "history": ["2026-10-13T05:00:00Z import started", "2026-10-13T05:01:20Z approved lyrics via ui", "free text without a stamp"],
        "approvals": {"lyrics": {"at": "2026-10-13T05:01:20Z", "via": "ui", "sha": "b3f3a4112fc0"}, "go_public": {"at": "2026-10-14T01:00:00Z", "via": "cli"}},
        "published": {"youtube": "", "instagram": "https://www.instagram.com/reel/Abc/",
                      "youtube_items": [{"id": "vid1", "url": "https://youtu.be/vid1", "privacy": "public", "file": "final_16x9.mp4"},
                                        {"id": "sh1", "url": "https://youtube.com/shorts/sh1", "privacy": "public", "file": "short.mp4"}]},
        "cloud": {"verified": True, "files": 50, "objects": {"a.mp3": {"size": 5, "url": "u"}}}, "cleanup": {"removed": 3, "removed_files": ["x", "y"]},
        "title_hindi": "पहला गीत"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = os.path.join(self.tmp.name, "songs"); os.makedirs(self.root)
        p = mock.patch.object(C, "songs_root", lambda: self.root); p.start(); self.addCleanup(p.stop)
        S._LOCAL.conn = None
        self.addCleanup(lambda: getattr(S._LOCAL, "conn", None) and S._LOCAL.conn.close())

    def meta_file(self, slug):
        with open(os.path.join(self.root, slug, "meta.json"), encoding="utf-8") as f: return json.load(f)


class Basics(Base):
    def test_save_load_roundtrip_keeps_every_key_and_unicode(self):
        S.save("song-001", REAL)
        self.assertEqual(S.load("song-001"), REAL)
        self.assertEqual(S.load("song-404", default={"x": 1}), {"x": 1})
        self.assertIsNone(S.load("song-404"))

    def test_the_loaded_copy_is_independent(self):
        S.save("song-001", REAL); a = S.load("song-001"); a["state"] = "changed"
        self.assertEqual(S.load("song-001")["state"], "published")

    def test_meta_json_is_written_through_after_each_save(self):
        S.save("song-001", REAL)
        self.assertEqual(self.meta_file("song-001"), REAL)
        S.update("song-001", lambda d: d.update(state="x"))
        self.assertEqual(self.meta_file("song-001")["state"], "x")

    def test_bad_slugs_are_refused(self):
        for bad in ("", "../x", "a/b", "x" * 80, None): self.assertRaises(ValueError, S.load, bad)

    def test_exists_delete_slugs(self):
        S.save("song-002", {"state": "draft"}); S.save("song-001", {"state": "draft"})
        self.assertEqual(S.slugs(), ["song-001", "song-002"]); self.assertTrue(S.exists("song-001"))
        S.delete("song-001"); self.assertFalse(S.exists("song-001"))


class UpdateContract(Base):
    def test_the_return_value_of_fn_never_replaces_the_document(self):
        S.save("song-001", {"album": "A", "redo_pending": "lyrics", "keep": 1})
        S.update("song-001", lambda d: d.pop("album", None))             # returns "A"
        S.update("song-001", lambda d: (d.pop("redo_pending", None), 1))   # returns a tuple
        self.assertEqual(S.load("song-001"), {"keep": 1})

    def test_update_creates_a_new_item(self):
        self.assertEqual(S.update("song-050", lambda d: d.update(state="draft")), {"state": "draft"})
        self.assertEqual(S.load("song-050"), {"state": "draft"}); self.assertTrue(os.path.exists(os.path.join(self.root, "song-050", "meta.json")))


class Concurrency(Base):
    def test_update_never_loses_a_write_between_threads(self):
        S.save("song-001", {"n": 0})
        def work():
            for _ in range(20): S.update("song-001", lambda d: d.__setitem__("n", d["n"] + 1))
        ts = [threading.Thread(target=work) for _ in range(8)]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(S.load("song-001")["n"], 160)


class Projections(Base):
    def rows(self, sql):
        c = S._conn()
        try: return [dict(r) for r in c.execute(sql).fetchall()]
        finally: c.commit()

    def test_history_approvals_publications_are_projected(self):
        S.save("song-001", REAL)
        h = self.rows("SELECT seq, text, at IS NOT NULL AS stamped FROM item_history ORDER BY seq")
        self.assertEqual([x["seq"] for x in h], [0, 1, 2]); self.assertEqual([x["stamped"] for x in h], [True, True, False])
        a = {r["gate"]: r for r in self.rows("SELECT gate, via, content_hash FROM approvals")}
        self.assertEqual(a["lyrics"]["content_hash"], "b3f3a4112fc0"); self.assertIsNone(a["go_public"]["content_hash"])   # NULL = legacy-approved
        p = sorted((r["platform"], r["kind"]) for r in self.rows("SELECT platform, kind FROM publications"))
        self.assertEqual(p, [("instagram", "reel"), ("youtube", "short"), ("youtube", "video")])

    def test_schedule_status_and_replacement_on_every_save(self):
        d = dict(REAL, schedule={"youtube_at": "2026-10-20T10:00:00Z", "instagram_at": "2026-10-20T11:00:00Z", "attempts": {"publish_youtube": {"n": 2}}, "blocked": {"publish_instagram": "login missing"}})
        S.save("song-001", d)
        r = {x["platform"]: x for x in self.rows("SELECT platform, status, attempts FROM schedules")}
        self.assertEqual((r["youtube"]["status"], r["youtube"]["attempts"], r["instagram"]["status"]), ("waiting", 2, "blocked"))
        S.update("song-001", lambda m: m["schedule"].update(done=True))
        self.assertEqual({x["status"] for x in self.rows("SELECT status FROM schedules")}, {"done"})
        S.update("song-001", lambda m: m.pop("schedule"))
        self.assertEqual(self.rows("SELECT * FROM schedules"), [])

    def test_version_counts_saves(self):
        S.save("song-001", {"a": 1}); S.save("song-001", {"a": 2})
        self.assertEqual(self.rows("SELECT version FROM items")[0]["version"], 2)


class OutsideEdits(Base):
    """A Claude step, a person or the previous release (after a rollback) edits meta.json directly: that content is the newer state."""
    def write_file(self, slug, doc, raw=None):
        with open(os.path.join(self.root, slug, "meta.json"), "w", encoding="utf-8") as f: f.write(raw if raw is not None else json.dumps(doc, ensure_ascii=False))

    def test_a_file_edited_outside_wins_and_is_stored(self):
        S.save("song-001", REAL)
        self.write_file("song-001", dict(REAL, state="edited-by-an-agent"))
        self.assertEqual(S.load("song-001")["state"], "edited-by-an-agent")
        self.assertEqual(S.load("song-001")["state"], "edited-by-an-agent")   # stored, not re-read each time
        c = S._conn(); n = c.execute("SELECT version FROM items").fetchone()["version"]; c.commit(); self.assertEqual(n, 2)

    def test_update_starts_from_the_outside_edit(self):
        S.save("song-001", {"a": 1})
        self.write_file("song-001", {"a": 1, "added_by_agent": True})
        out = S.update("song-001", lambda d: d.__setitem__("b", 2))
        self.assertEqual(out, {"a": 1, "added_by_agent": True, "b": 2})

    def test_same_content_in_another_format_is_not_a_new_version(self):
        S.save("song-001", {"a": 1, "b": 2})
        self.write_file("song-001", None, raw='{"b":2,\n"a":1}')
        self.assertEqual(S.load("song-001"), {"a": 1, "b": 2})
        c = S._conn(); n = c.execute("SELECT version FROM items").fetchone()["version"]; c.commit(); self.assertEqual(n, 1)

    def test_a_broken_file_is_ignored_and_the_stored_state_kept(self):
        S.save("song-001", {"a": 1})
        self.write_file("song-001", None, raw="{broken")
        self.assertEqual(S.load("song-001"), {"a": 1})

    def test_a_failed_export_rolls_the_save_back(self):
        S.save("song-001", {"a": 1})
        with mock.patch.object(S, "_export", side_effect=OSError("disk full")):
            self.assertRaises(OSError, S.save, "song-001", {"a": 2})
        self.assertEqual(S.load("song-001"), {"a": 1})


class Import(Base):
    def put(self, slug, doc):
        os.makedirs(os.path.join(self.root, slug), exist_ok=True)
        with open(os.path.join(self.root, slug, "meta.json"), "w", encoding="utf-8") as f: json.dump(doc, f, ensure_ascii=False)

    def test_an_item_only_in_a_file_is_imported_on_first_use(self):
        self.put("song-009", REAL)
        self.assertEqual(S.load("song-009"), REAL); self.assertEqual(S.slugs(), ["song-009"])

    def test_import_all_dry_run_then_real_then_unchanged(self):
        self.put("song-001", REAL); self.put("song-002", {"state": "draft"}); os.makedirs(os.path.join(self.root, "_template"))
        self.assertEqual({r[1] for r in S.import_all(dry_run=True)}, {"would import"}); self.assertEqual(S.slugs(), [])
        self.assertEqual({r[1] for r in S.import_all()}, {"imported"}); self.assertEqual(S.slugs(), ["song-001", "song-002"])
        self.assertEqual({r[1] for r in S.import_all()}, {"unchanged"})

    def test_auto_imports_once_and_a_broken_file_stops_the_start(self):
        self.put("song-001", REAL)
        self.assertEqual(S.auto(), "imported 1"); self.assertEqual(S.auto(), "already in postgres")

    def test_a_broken_meta_json_is_reported_not_skipped(self):
        os.makedirs(os.path.join(self.root, "song-003"))
        with open(os.path.join(self.root, "song-003", "meta.json"), "w") as f: f.write("{not json")
        with self.assertRaises(SystemExit) as cm: S.auto()
        self.assertIn("song-003", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
