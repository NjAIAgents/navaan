"""NAV-7 stage 1: plans and the one check behind them, playlists that belong to one person and keep both edits, saved items, plays in monthly partitions, and a person's export and erase."""
import datetime, json, os, random, sys, tempfile, threading, unittest, uuid
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import positions as P


class Positions(unittest.TestCase):
    def test_a_key_always_sorts_between_its_neighbours(self):
        keys = []; rnd = random.Random(5)
        for _ in range(2000):
            i = rnd.randint(0, len(keys)); a = keys[i - 1] if i else None; b = keys[i] if i < len(keys) else None
            k = P.between(a, b); self.assertTrue((a is None or a < k) and (b is None or k < b) and not k.endswith("0"), (a, b, k)); keys.insert(i, k)
        self.assertEqual(keys, sorted(keys)); self.assertEqual(len(set(keys)), len(keys))
        self.assertRaises(ValueError, P.between, "b", "a")

    def test_spread_gives_short_ordered_keys(self):
        for n in (1, 2, 50, 3000):
            s = P.spread(n); self.assertEqual(s, sorted(s)); self.assertEqual(len(set(s)), n); self.assertFalse(any(k.endswith("0") for k in s)); self.assertLessEqual(max(map(len, s)), 4)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        p = mock.patch.dict(os.environ, {"NAVAAN_ROOT": self.tmp.name}); p.start(); self.addCleanup(p.stop)
        import navaan_common as C, catalog_store as K, entitlements as E, library_store as L
        self.C, self.K, self.E, self.L = C, K, E, L
        K._LOCAL.conn = None
        def close():
            for m in (K, E, L):
                t = getattr(m, "_tx", None)
                if t is not None and hasattr(t, "close"): t.close()
            getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close()
        self.addCleanup(close)

    def songs(self, n=5, published=True):
        for i in range(1, n + 1):
            slug = f"song-{i:03d}"; D = os.path.join(self.C.songs_root(), slug); os.makedirs(D)
            open(os.path.join(D, "title.txt"), "w", encoding="utf-8").write(f"Song {i}\n")
            json.dump({"slug": slug, "type": "music", "state": "published" if published else "drafted"}, open(os.path.join(D, "meta.json"), "w")); self.K.sync_item(slug)

    def person(self, role="listener"): return {"user_id": str(uuid.uuid4()), "roles": [role]}


class Plans(Base):
    def test_a_new_person_is_on_free_and_the_limit_is_data(self):
        u = self.person()
        self.assertEqual(self.E.plan_for(u["user_id"])["key"], "free")
        d = self.E.can(u, "playlists.max", used=2); self.assertTrue(d); self.assertEqual(d.limit, 3)
        d = self.E.can(u, "playlists.max", used=3); self.assertFalse(d); self.assertEqual((d.reason, d.limit), ("limit", 3)); self.assertIn("3", d.message())
        self.assertTrue(self.E.set_entitlement("free", "playlists.max", True, 5))   # SC-008: a row changes, nothing is deployed
        self.assertTrue(self.E.can(u, "playlists.max", used=4)); self.assertFalse(self.E.can(u, "playlists.max", used=5))
        self.assertFalse(self.E.set_entitlement("ghost", "playlists.max", True, 9)); self.assertRaises(ValueError, self.E.set_entitlement, "free", "x", True, -1)

    def test_features_premium_overrides_and_the_owner(self):
        u = self.person(); self.assertFalse(self.E.can(u, "audio.quality_hi")); self.assertEqual(self.E.can(u, "audio.quality_hi").reason, "not_in_plan"); self.assertFalse(self.E.can(u, "no.such.feature"))
        self.assertTrue(self.E.can(u, "audio.play"))
        self.E.switch_plan(u["user_id"], "premium"); self.assertEqual(self.E.plan_for(u["user_id"])["key"], "premium")
        self.assertTrue(self.E.can(u, "audio.quality_hi")); self.assertTrue(self.E.can(u, "playlists.max", used=10_000))   # no limit
        f = self.person(); self.E.override(f["user_id"], "playlists.max", "a friend of the artist", limit=10)
        self.assertTrue(self.E.can(f, "playlists.max", used=9)); self.assertFalse(self.E.can(f, "playlists.max", used=10))
        self.assertRaises(ValueError, self.E.override, f["user_id"], "offline", " ", enabled=True)
        self.E.override(f["user_id"], "offline", "expired", enabled=True, expires_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.timezone.utc)); self.assertFalse(self.E.can(f, "offline"))
        self.assertTrue(self.E.can({"user_id": str(uuid.uuid4()), "roles": ["owner"]}, "playlists.max", used=99))   # the owner is never limited
        self.assertRaises(LookupError, self.E.switch_plan, u["user_id"], "ghost")

    def test_plans_page_data_says_premium_cannot_be_bought_yet(self):
        ps = self.E.plans(); self.assertEqual([p["key"] for p in ps], ["free", "premium"]); self.assertTrue(all(p["buyable"] is False for p in ps))
        free = {e["feature"]: e for e in ps[0]["entitlements"]}; self.assertEqual(free["playlists.max"]["limit"], 3); self.assertFalse(free["offline"]["enabled"])


class Playlists(Base):
    def test_the_free_limit_applies_and_playlists_belong_to_one_person(self):
        self.songs(); a, b = self.person(), self.person()
        ids = [self.L.create_playlist(a, f"List {i}") for i in range(3)]
        with self.assertRaises(self.L.LimitError) as cm: self.L.create_playlist(a, "A fourth")
        self.assertEqual(cm.exception.decision.limit, 3); self.assertIn("plan", str(cm.exception))
        self.assertTrue(self.L.create_playlist(b, "Mine"))   # a limit is per person
        for fn in (lambda: self.L.get_playlist(b["user_id"], ids[0]), lambda: self.L.update_playlist(b["user_id"], ids[0], name="x"), lambda: self.L.delete_playlist(b["user_id"], ids[0]),
                   lambda: self.L.add_track(b["user_id"], ids[0], "song-001"), lambda: self.L.move_track(b["user_id"], ids[0], "song-001", None)):
            with self.assertRaises(LookupError): fn()   # not found, never "forbidden": SC-005
        self.assertEqual(len(self.L.playlists(b["user_id"])), 1)
        self.L.delete_playlist(a["user_id"], ids[0]); self.assertTrue(self.L.create_playlist(a, "Room again"))

    def test_order_add_after_move_remove(self):
        self.songs(); u = self.person(); pid = self.L.create_playlist(u, "  Evening   list "); uid = u["user_id"]
        self.assertEqual(self.L.get_playlist(uid, pid)["name"], "Evening list")
        for s in ("song-001", "song-002", "song-003"): self.L.add_track(uid, pid, s)
        names = lambda: [t["slug"] for t in self.L.get_playlist(uid, pid)["tracks"]]
        self.assertEqual(names(), ["song-001", "song-002", "song-003"])
        self.L.add_track(uid, pid, "song-004", after="song-001"); self.assertEqual(names(), ["song-001", "song-004", "song-002", "song-003"])
        self.L.add_track(uid, pid, "song-005", after=""); self.assertEqual(names()[0], "song-005")
        self.L.move_track(uid, pid, "song-003", after="song-005"); self.assertEqual(names(), ["song-005", "song-003", "song-001", "song-004", "song-002"])
        self.L.move_track(uid, pid, "song-005", after=None); self.assertEqual(names()[-1], "song-005")
        self.L.remove_track(uid, pid, "song-001"); self.assertNotIn("song-001", names())
        with self.assertRaises(ValueError): self.L.add_track(uid, pid, "song-002")                       # already there
        with self.assertRaises(ValueError): self.L.add_track(uid, pid, "ghost")                         # not a published track
        with self.assertRaises(LookupError): self.L.remove_track(uid, pid, "song-001")
        with self.assertRaises(ValueError): self.L.add_track(uid, pid, "song-001", after="nope")
        self.L.update_playlist(uid, pid, name="Night", visibility="unlisted"); g = self.L.get_playlist(uid, pid); self.assertEqual((g["name"], g["visibility"]), ("Night", "unlisted"))
        for bad in (dict(name=" "), dict(visibility="everyone")):
            with self.assertRaises(ValueError): self.L.update_playlist(uid, pid, **bad)

    def test_a_draft_track_cannot_be_added(self):
        self.songs(2, published=False); u = self.person(); pid = self.L.create_playlist(u, "x")
        with self.assertRaises(ValueError): self.L.add_track(u["user_id"], pid, "song-001")

    def test_two_people_saving_at_once_both_keep_their_edits(self):
        self.songs(8); owner = self.person("owner"); pid = self.L.create_playlist(owner, "Shared edit"); uid = owner["user_id"]; errs = []
        def add(s):
            try: self.L.add_track(uid, pid, s)
            except Exception as e: errs.append(repr(e))
        ts = [threading.Thread(target=add, args=(f"song-{i:03d}",)) for i in range(1, 9)]
        for t in ts: t.start()
        for t in ts: t.join()
        self.assertEqual(errs, [])
        g = self.L.get_playlist(uid, pid)["tracks"]; self.assertEqual(sorted(t["slug"] for t in g), [f"song-{i:03d}" for i in range(1, 9)]); self.assertEqual(len({t["position"] for t in g}), 8)

    def test_a_long_run_of_appends_renumbers_with_short_keys(self):
        self.songs(60); u = self.person("owner"); pid = self.L.create_playlist(u, "Long"); uid = u["user_id"]
        for i in range(1, 61): self.L.add_track(uid, pid, f"song-{i:03d}")
        g = self.L.get_playlist(uid, pid)["tracks"]; self.assertEqual([t["slug"] for t in g], [f"song-{i:03d}" for i in range(1, 61)]); self.assertLessEqual(max(len(t["position"]) for t in g), self.L.MAX_KEY)


class Keeping(Base):
    def test_saved_songs_albums_and_follows(self):
        self.songs(2); u = self.person()["user_id"]
        D = os.path.join(self.C.songs_root(), "song-001"); m = json.load(open(os.path.join(D, "meta.json"))); m["album"] = "First Light"; json.dump(m, open(os.path.join(D, "meta.json"), "w")); self.K.sync_item("song-001")
        self.L.save(u, "track", "song-002"); self.L.save(u, "track", "song-002"); self.L.save(u, "album", "first-light"); self.L.follow(u)
        lib = self.L.library(u); self.assertEqual([t["slug"] for t in lib["tracks"]], ["song-002"]); self.assertEqual([a["slug"] for a in lib["albums"]], ["first-light"]); self.assertTrue(lib["following"])
        self.L.save(u, "track", "song-002", on=False); self.L.follow(u, False); lib = self.L.library(u); self.assertEqual((lib["tracks"], lib["following"]), ([], False))
        with self.assertRaises(ValueError): self.L.save(u, "track", "ghost")
        with self.assertRaises(ValueError): self.L.save(u, "podcast", "x")
        self.assertEqual(self.L.library(self.person()["user_id"]), {"tracks": [], "albums": [], "following": False})   # someone else's is empty

    def test_plays_are_recorded_by_month_and_old_detail_is_dropped_by_partition(self):
        self.songs(1); u = self.person()["user_id"]
        self.assertTrue(self.L.record_play(u, "song-001", "playlist", "p1")); self.assertFalse(self.L.record_play(u, "ghost"))
        n = lambda: self.L._conn().execute("SELECT count(*) AS n FROM play_events WHERE user_id = ?::uuid", (u,)).fetchone()["n"]; self.assertEqual(n(), 1)
        old = datetime.date.today() - datetime.timedelta(days=500); self.L.ensure_partition(old); self.L.ensure_partition(old)   # idempotent
        self.L._tx(lambda c: c.execute("INSERT INTO play_events (user_id, track_id, started_at) SELECT ?::uuid, track_id, ? FROM play_events WHERE user_id = ?::uuid LIMIT 1", (u, old.isoformat() + "T12:00:00Z", u)))
        self.assertEqual(n(), 2)
        dropped = self.L.drop_old_partitions(keep_months=13); self.assertEqual(len(dropped), 1); self.assertEqual(n(), 1)   # only the old month went
        self.L.rebuild_daily_stats(datetime.date.today() - datetime.timedelta(days=1))
        r = self.L._conn().execute("SELECT plays, listeners FROM play_stats_daily").fetchone(); self.assertEqual((r["plays"], r["listeners"]), (1, 1))

    def test_export_and_erase_cover_everything_held_about_a_person(self):
        self.songs(3); u = self.person(); uid = u["user_id"]; o = self.person()
        pid = self.L.create_playlist(u, "Mine"); self.L.add_track(uid, pid, "song-001"); self.L.save(uid, "track", "song-002"); self.L.follow(uid); self.L.record_play(uid, "song-003"); self.E.switch_plan(uid, "premium")
        other = self.L.create_playlist(o, "Not yours"); self.L.add_track(o["user_id"], other, "song-001")
        x = self.L.export(uid); self.assertEqual([p["name"] for p in x["playlists"]], ["Mine"]); self.assertEqual([t["slug"] for t in x["saved_tracks"]], ["song-002"]); self.assertTrue(x["following"]); self.assertEqual([p["slug"] for p in x["plays"]], ["song-003"])
        self.assertEqual(self.E.export(uid)["subscriptions"][-1]["plan"], "premium")
        self.L.erase(uid); self.E.erase(uid)
        y = self.L.export(uid); self.assertEqual((y["playlists"], y["saved_tracks"], y["plays"], y["following"]), ([], [], [], False)); self.assertEqual(self.E.export(uid), {"subscriptions": [], "overrides": []})
        self.assertEqual(len(self.L.playlists(o["user_id"])), 1)   # nobody else's data was touched


if __name__ == "__main__":
    unittest.main()
