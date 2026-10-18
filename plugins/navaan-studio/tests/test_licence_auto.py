"""Author: Navjyot Nishant
Created: 2026-10-18
Last updated: 2026-10-18
Description: automatic licence confirmation: off by default, needs the owner's statement, confirms only a published unconfirmed track, and never touches a decision the owner already made.
"""
import os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_catalog import Base
import _pgenv  # noqa: F401


class Auto(Base):
    def setUp(self):
        super().setUp()
        import licence_cfg
        self.L = licence_cfg
        d = tempfile.mkdtemp(); p = mock.patch.dict(os.environ, {"NAVAAN_CONF_DIR": d}); p.start(); self.addCleanup(p.stop)

    def lic(self, slug): return self.K._conn().execute("SELECT license_status, origin_detail FROM tracks WHERE slug = ?", (slug,)).fetchone()

    def test_it_is_off_by_default_and_a_published_song_stays_unconfirmed(self):
        self.assertEqual(self.L.load()["auto"], False)
        self.song("song-001", "Tere Hone Se"); self.K.sync_item("song-001"); self.assertEqual(self.lic("song-001")["license_status"], "unconfirmed")

    def test_switching_it_on_needs_the_statement_and_remembers_who_and_when(self):
        with self.assertRaises(ValueError) as c: self.L.save(True, "   ", "owner1")
        self.assertIn("statement", str(c.exception)); self.assertFalse(self.L.load()["auto"])
        with self.assertRaises(ValueError): self.L.save(True, "x" * 401, "owner1")
        r = self.L.save(True, "Every song I publish is made on a paid Suno plan.", "owner1")
        self.assertEqual((r["auto"], r["set_by"]), (True, "owner1")); self.assertTrue(r["set_at"].endswith("Z"))
        off = self.L.save(False, "", "owner1"); self.assertFalse(off["auto"]); self.assertEqual(off["statement"], "Every song I publish is made on a paid Suno plan.")   # off keeps the words for next time
        self.assertIn("paid Suno plan", self.L.status()["suggested"])

    def test_a_song_published_while_it_is_on_is_confirmed_with_the_statement_as_the_reason(self):
        self.L.save(True, "Owner statement: every song is on a paid Suno plan.", "owner1")
        self.song("song-001", "Tere Hone Se"); self.K.sync_item("song-001")
        r = self.lic("song-001"); self.assertEqual(r["license_status"], "confirmed")
        d = r["origin_detail"]; self.assertEqual((d["license_set_by"], d["license_note"], d["suno_plan"]), ("owner (auto-confirm setting)", "Owner statement: every song is on a paid Suno plan.", "paid"))
        rows = self.K.browse(); self.assertEqual([t["slug"] for t in rows], ["song-001"])   # a listener sees it

    def test_it_never_changes_a_decision_the_owner_made_or_a_draft(self):
        self.L.save(True, "Every song is on a paid plan.", "owner1")
        self.song("song-001", "One"); self.song("song-002", "Two", state="drafted", cloud=False); self.song("song-003", "Three")
        self.K.sync_item("song-003"); self.K.set_license("song-003", "not_allowed", "owner", "the vocals are a cover"); self.K.sync_item("song-003")
        self.assertEqual(self.lic("song-003")["license_status"], "not_allowed")   # the owner said no: stays no
        self.K.sync_item("song-002"); self.assertEqual(self.lic("song-002")["license_status"], "unconfirmed")   # not published yet: nothing to confirm
        self.assertFalse(self.K.auto_confirm("song-001") and self.K.auto_confirm("song-999"))   # a song that is not in the catalog is simply not found


if __name__ == "__main__":
    unittest.main()
