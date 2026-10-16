"""NAV-6 stage 1: the catalog is built from the studio's items (tracks, assets, albums from labels), search finds a title in either script (SC-012), albums keep their order, and a licence that is not confirmed is never offerable (FR-017)."""
import json, os, random, statistics, sys, tempfile, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import translit as T


class Translit(unittest.TestCase):
    def test_hindi_titles_become_roman_the_way_people_type_them(self):
        for dev, roman in [("तेरे होने से", "tere hone se"), ("चाँद बनकर आ जाओ", "chand bankar aa jao"), ("ख़त जो कभी लिखा नहीं", "khat jo kabhi likha nahin"), ("प्यार", "pyar"), ("तेरे होने सेऽऽ…", "tere hone se …")]:
            self.assertEqual(T.to_roman(dev), roman)
        self.assertEqual(T.to_roman("Chaanak Ijot"), "Chaanak Ijot")   # Roman text passes through

    def test_fold_merges_spellings_but_keeps_devanagari_vowel_signs(self):
        self.assertEqual(T.fold("चाँद"), T.fold("चांद")); self.assertEqual(T.fold("क़िस्मत"), T.fold("किस्मत"))
        self.assertEqual(T.fold("Café, Ünï!"), "cafe uni"); self.assertIn("े", T.fold("तेरे"))
        self.assertEqual(T.search_text("Pata Hi Na Chala"), "pata hi na chala")   # no duplicate of the Roman form


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); os.environ["NAVAAN_ROOT"] = self.tmp.name; self.addCleanup(os.environ.pop, "NAVAAN_ROOT", None)
        import navaan_common as C, catalog_store as K
        self.C, self.K = C, K; K._LOCAL.conn = None; self.addCleanup(lambda: getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close())

    def song(self, slug, title, state="published", album=None, cloud=True, extra=None):
        D = os.path.join(self.C.songs_root(), slug); os.makedirs(D)
        open(os.path.join(D, "title.txt"), "w", encoding="utf-8").write(title + "\n"); open(os.path.join(D, "lyrics.txt"), "w", encoding="utf-8").write("line one\nline two\n")
        m = {"slug": slug, "type": "music", "state": state, "suno_model": "v6", **({"album": album} if album else {}), **(extra or {})}
        if cloud: m["cloud"] = {"verified": True, "uploaded_at": "2026-10-01T10:00:00Z", "prefix": f"navaan/songs/{slug}/", "objects": {"final.mp3": {"size": 100}, "cover_1x1.png": {"size": 50}, "brief.md": {"size": 1}}}
        json.dump(m, open(os.path.join(D, "meta.json"), "w")); return D


class Catalog(Base):
    def test_a_published_song_becomes_a_track_with_assets_from_the_bucket(self):
        self.song("song-001", "तेरे होने से")
        self.assertEqual(self.K.sync_item("song-001"), "song-001"); self.assertEqual(self.K.sync_item("song-001"), "song-001")   # idempotent
        c = self.K._conn()
        t = c.execute("SELECT status, origin, origin_detail, license_status, published_at FROM tracks WHERE slug = 'song-001'").fetchone()
        self.assertEqual((t["status"], t["origin"], t["license_status"]), ("published", "suno", "unconfirmed")); self.assertEqual(t["origin_detail"], {"suno_model": "v6"}); self.assertIsNotNone(t["published_at"])
        keys = sorted(r["storage_key"] for r in c.execute("SELECT storage_key FROM assets").fetchall())
        self.assertEqual(keys, ["navaan/songs/song-001/cover_1x1.png", "navaan/songs/song-001/final.mp3"])   # only audio and cover, only because the cloud record is verified
        self.assertEqual(c.execute("SELECT count(*) AS n FROM tracks").fetchone()["n"], 1)

    def test_nothing_is_an_asset_until_the_bucket_copy_is_verified_and_a_draft_is_not_searchable(self):
        self.song("song-002", "Draft Song", state="drafted", cloud=False); self.K.sync_item("song-002")
        c = self.K._conn()
        self.assertEqual(c.execute("SELECT count(*) AS n FROM assets").fetchone()["n"], 0); self.assertEqual(c.execute("SELECT count(*) AS n FROM search_documents").fetchone()["n"], 0)
        self.assertIsNone(self.K.sync_item("insp-001")); os.makedirs(os.path.join(self.C.songs_root(), "insp-001")); json.dump({"type": "inspiration"}, open(os.path.join(self.C.songs_root(), "insp-001", "meta.json"), "w"))
        self.assertIsNone(self.K.sync_item("insp-001"))   # only songs are catalog tracks

    def test_an_album_label_becomes_an_album_with_the_song_in_it(self):
        self.song("song-001", "One", album="First Light"); self.song("song-002", "Two", album="First Light")
        self.assertEqual(self.K.sync_all(), ["song-001", "song-002"]); self.K.sync_all()
        a = self.K.albums()[0]
        self.assertEqual((a["slug"], a["title"], a["status"]), ("first-light", "First Light", "published")); self.assertEqual([(t["slug"], t["position"]) for t in a["tracks"]], [("song-001", 1), ("song-002", 2)])

    def test_album_crud_and_reorder_in_one_transaction(self):
        for i, n in enumerate(("One", "Two", "Three"), 1): self.song(f"song-00{i}", n); self.K.sync_item(f"song-00{i}")
        slug = self.K.save_album("", "My Album", "ep", "draft", "2026-11-01", "d")
        self.assertEqual(self.K.save_album("", "My Album"), "my-album-2")   # a second one gets its own slug
        self.K.reorder(slug, ["song-003", "song-001", "song-002"]); self.assertEqual([t["slug"] for t in self.K.albums()[1 if self.K.albums()[0]["slug"] != slug else 0]["tracks"]], ["song-003", "song-001", "song-002"])
        self.K.reorder(slug, ["song-002", "song-003"])   # song-001 leaves, the rest close ranks
        mine = [a for a in self.K.albums() if a["slug"] == slug][0]; self.assertEqual([(t["slug"], t["position"]) for t in mine["tracks"]], [("song-002", 1), ("song-003", 2)])
        self.assertRaises(ValueError, self.K.reorder, slug, ["song-002", "song-002"]); self.assertRaises(ValueError, self.K.reorder, slug, ["nope"])
        self.assertRaises(ValueError, self.K.save_album, "", " "); self.assertRaises(ValueError, self.K.save_album, "", "x", "box"); self.assertRaises(LookupError, self.K.save_album, "ghost", "x")
        self.assertTrue(self.K.delete_album(slug)); self.assertFalse(self.K.delete_album(slug))
        self.assertEqual(self.K._conn().execute("SELECT count(*) AS n FROM tracks").fetchone()["n"], 3)   # tracks stay

    def test_a_published_album_holds_only_published_songs_and_albums_report_each_songs_cover(self):
        self.song("song-001", "One"); self.song("song-002", "Two", state="drafted", cloud=False); self.K.sync_item("song-001"); self.K.sync_item("song-002")
        slug = self.K.save_album("", "My Album", "album", "draft")
        c = self.K._conn(); aid = c.execute("SELECT id FROM albums WHERE slug = ?", (slug,)).fetchone()["id"]
        for sl in ("song-001", "song-002"): c.execute("INSERT INTO album_tracks (album_id, track_id, position) SELECT ?::uuid, id, (SELECT count(*) + 1 FROM album_tracks WHERE album_id = ?::uuid) FROM tracks WHERE slug = ?", (str(aid), str(aid), sl))
        c.commit()
        with self.assertRaises(ValueError) as cm: self.K.save_album(slug, "My Album", "album", "published")
        self.assertIn("song-002", str(cm.exception))
        self.K.reorder(slug, ["song-001"]); self.assertEqual(self.K.save_album(slug, "My Album", "album", "published"), slug)
        a = self.K.albums()[0]; self.assertEqual((a["status"], [(t["slug"], t["status"], t["art"] is not None) for t in a["tracks"]]), ("published", [("song-001", "published", True)]))   # the cover comes from the song
        empty = self.K.save_album("", "Empty"); self.assertRaises(ValueError, self.K.save_album, empty, "Empty", "album", "published")

    def test_only_a_confirmed_licence_can_be_offered_and_a_sync_never_confirms(self):
        self.song("song-001", "One"); self.K.sync_item("song-001"); self.assertFalse(self.K.offerable("song-001")); self.assertFalse(self.K.offerable("ghost"))
        c = self.K._conn(); c.execute("UPDATE tracks SET license_status = 'confirmed' WHERE slug = 'song-001'"); c.commit()
        self.assertTrue(self.K.offerable("song-001")); self.K.sync_item("song-001"); self.assertTrue(self.K.offerable("song-001"))   # the owner's decision survives a sync
        c.execute("UPDATE tracks SET license_status = 'not_allowed' WHERE slug = 'song-001'"); c.commit(); self.assertFalse(self.K.offerable("song-001"))

    def test_the_owners_licence_decision_is_recorded_and_survives_a_sync(self):
        self.song("song-001", "One", extra={"suno_plan": "pro"}); self.K.sync_item("song-001")
        self.assertEqual(self.K.tracks()[0]["plan"], "pro")
        self.assertTrue(self.K.set_license("song-001", "confirmed", "owner", "  paid plan, all songs ", plan="paid"))
        t = self.K.tracks()[0]; self.assertEqual((t["license_status"], t["plan"], t["decided_by"], t["note"], t["model"]), ("confirmed", "paid", "owner", "paid plan, all songs", "v6"))
        self.K.sync_item("song-001"); t = self.K.tracks()[0]; self.assertEqual((t["license_status"], t["decided_by"], t["model"]), ("confirmed", "owner", "v6"))   # the sync keeps the decision
        self.assertTrue(self.K.offerable("song-001")); self.assertFalse(self.K.set_license("ghost", "confirmed", "owner", "x"))
        self.assertRaises(ValueError, self.K.set_license, "song-001", "yes", "owner", "x"); self.assertRaises(ValueError, self.K.set_license, "song-001", "confirmed", "owner", " ")
        self.assertTrue(self.K.offerable("song-001"))   # a refused call changes nothing

    def test_the_studios_id3_style_tags_give_language_and_genre_and_never_become_search_words(self):
        D = self.song("song-001", "Tere Hone Se"); json.dump({"title": "x", "artist": "NAVAAN", "album": "a", "genre": "Hindi Romantic", "language": "Hindi", "composer": "NAVAAN", "isrc": ""}, open(os.path.join(D, "tags.json"), "w"))
        self.K.sync_item("song-001"); self.K.sync_item("song-001")   # twice: nothing doubles
        c = self.K._conn()
        self.assertEqual(c.execute("SELECT language FROM tracks WHERE slug = 'song-001'").fetchone()["language"], "Hindi")
        self.assertEqual([r["name"] for r in c.execute("SELECT g.name FROM genres g JOIN track_genres tg ON tg.genre_id = g.id").fetchall()], ["Hindi Romantic"])
        text = c.execute("SELECT search_text, tags FROM search_documents").fetchone(); self.assertEqual(text["tags"], ["Hindi Romantic"])
        for noise in ("composer", "artist", "isrc", "album"): self.assertNotIn(noise, text["search_text"])   # the object's key names are not words about the song
        import search as S; self.assertEqual(S.search("composer"), []); self.assertEqual(S.search("hindi romantic")[0]["slug"], "song-001")
        json.dump({"genre": "Acoustic ballad"}, open(os.path.join(D, "tags.json"), "w")); self.K.sync_item("song-001")   # a changed genre replaces the old link
        self.assertEqual([r["name"] for r in c.execute("SELECT g.name FROM genres g JOIN track_genres tg ON tg.genre_id = g.id").fetchall()], ["Acoustic ballad"])

    def test_timing_file_in_the_bucket_becomes_a_lyrics_timed_asset(self):
        self.song("song-001", "One", extra=None)
        m = json.load(open(os.path.join(self.C.song_dir("song-001"), "meta.json"))); m["cloud"]["objects"]["caption_timing.json"] = {"size": 99}; json.dump(m, open(os.path.join(self.C.song_dir("song-001"), "meta.json"), "w")); self.K.sync_item("song-001")
        self.assertEqual([r["storage_key"] for r in self.K._conn().execute("SELECT storage_key FROM assets WHERE role = 'lyrics_timed'").fetchall()], ["navaan/songs/song-001/caption_timing.json"])

    def test_the_pipelines_caption_cues_are_timed_lyrics_too_and_the_timing_file_wins_when_both_exist(self):
        self.song("song-001", "One", extra=None)
        D = self.C.song_dir("song-001"); m = json.load(open(os.path.join(D, "meta.json")))
        m["cloud"]["objects"]["caption_cues.json"] = {"size": 50}; json.dump(m, open(os.path.join(D, "meta.json"), "w")); self.K.sync_item("song-001")   # a song with only the cues (song-006 on prod)
        self.assertEqual(self.K.timed_asset("song-001")["storage_key"], "navaan/songs/song-001/caption_cues.json")
        m["cloud"]["objects"]["caption_timing.json"] = {"size": 99}; json.dump(m, open(os.path.join(D, "meta.json"), "w")); self.K.sync_item("song-001")
        self.assertEqual(self.K.timed_asset("song-001")["storage_key"], "navaan/songs/song-001/caption_timing.json")

    def test_folders_that_are_not_items_are_skipped(self):
        os.makedirs(os.path.join(self.C.songs_root(), "_template")); json.dump({"type": "music"}, open(os.path.join(self.C.songs_root(), "_template", "meta.json"), "w"))
        self.song("song-001", "One"); self.assertEqual(self.K.sync_all(), ["song-001"])


class Search(Base):
    def test_either_script_finds_the_title_and_typos_are_tolerated(self):
        import search as S
        self.song("song-001", "तेरे होने से"); self.song("song-002", "Pata Hi Na Chala"); self.song("song-003", "चाँद बनकर आ जाओ"); self.song("song-004", "Draft", state="drafted", cloud=False)
        self.K.sync_all()
        for q in ("tere hone se", "तेरे होने से", "tere hone", "Tere Hōne Sé", "tera hone se", "तेरे होने"): self.assertEqual(S.search(q)[0]["slug"], "song-001", q)
        self.assertEqual(S.search("chaand bankar")[0]["slug"], "song-003"); self.assertEqual(S.search("चांद बनकर")[0]["slug"], "song-003")   # chandrabindu and anusvara are the same word
        self.assertEqual(S.search("pata hi na")[0]["slug"], "song-002")
        self.assertEqual(S.search("draft"), []); self.assertEqual(S.search("x"), []); self.assertEqual(S.search("zzzzqq"), [])
        self.assertEqual(S.search("100%_"), [])   # LIKE wildcards in the query are literal

    def test_a_published_album_is_found_too(self):
        import search as S
        self.song("song-001", "One", album="First Light"); self.K.sync_all()
        hit = S.search("first light", kinds=["album"])[0]; self.assertEqual((hit["kind"], hit["slug"]), ("album", "first-light")); self.assertEqual(S.search("first light", kinds=["track"]), [])

    def test_benchmark_on_10000_tracks(self):
        """SC-012: on 10,000 tracks 'tere hone se' returns तेरे होने से in the first three and p95 is under 200 ms."""
        import search as S
        self.song("song-001", "तेरे होने से"); self.K.sync_item("song-001")
        c = self.K._conn(); aid = str(c.execute("SELECT id FROM artists").fetchone()["id"]); rnd = random.Random(7)
        words = "dil raat chand tum hum pyar safar khwab yaad baat aankhon neend zindagi mohabbat tere mere hone jaana aana rang barish sapne ishq".split()
        rows = []
        for i in range(10000):
            title = " ".join(rnd.choice(words) for _ in range(rnd.randint(2, 4)))
            rows.append((f"synth-{i}", title)) if title != "tere hone se" else None
        with c.cursor() as cur:
            cur.executemany("INSERT INTO tracks (artist_id, slug, title, status) VALUES (%s::uuid, %s, %s, 'published')", [(aid, s, t) for s, t in rows])
            cur.executemany("INSERT INTO search_documents (kind, subject_id, artist_id, title_native, title_roman, search_text) SELECT 'track', id, artist_id, title, title, %s FROM tracks WHERE slug = %s", [(T.search_text(t), s) for s, t in rows])
        c.commit(); c.execute("ANALYZE search_documents"); c.commit()
        self.assertGreater(c.execute("SELECT count(*) AS n FROM search_documents").fetchone()["n"], 9900)
        times = []
        for q in ["tere hone se", "तेरे होने से"] * 30:
            t0 = time.perf_counter(); hits = S.search(q); times.append((time.perf_counter() - t0) * 1000)
            self.assertIn("song-001", [h["slug"] for h in hits[:3]], q)
        times.sort(); p95 = times[int(len(times) * .95) - 1]
        print(f"\nsearch over {c.execute('SELECT count(*) AS n FROM search_documents').fetchone()['n']} documents: median {statistics.median(times):.1f} ms, p95 {p95:.1f} ms")
        self.assertLess(p95, 200)


if __name__ == "__main__":
    unittest.main()
