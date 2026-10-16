"""NAV-6 stage 2: cover sizes with ETags and a cache, the 30 second preview, signed links from the SDK (faked here), share links, and the one seam that decides what may be played."""
import io, json, os, shutil, subprocess, sys, tempfile, types, unittest
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
from PIL import Image


def png(w=400, h=400, colour=(200, 40, 40)):
    b = io.BytesIO(); Image.new("RGB", (w, h), colour).save(b, "PNG"); return b.getvalue()


def mp3(seconds=40):
    p = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440", "-t", str(seconds), "-c:a", "libmp3lame", "-b:a", "64k", "-f", "mp3", "pipe:1"], capture_output=True, timeout=60)
    return p.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for k, v in (("NAVAAN_ROOT", self.tmp.name), ("NAVAAN_CACHE_DIR", os.path.join(self.tmp.name, "cache"))):
            p = mock.patch.dict(os.environ, {k: v}); p.start(); self.addCleanup(p.stop)
        import navaan_common as C, catalog_store as K, media, objstore
        self.C, self.K, self.M, self.O = C, K, media, objstore
        K._LOCAL.conn = None; self.addCleanup(lambda: getattr(K._LOCAL, "conn", None) and K._LOCAL.conn.close())
        self.bucket = {}; self.gets = []
        def get(key): self.gets.append(key); return self.bucket[key]
        for name, fn in (("get", get), ("put", lambda key, data, ct="x": self.bucket.__setitem__(key, data)), ("par_url", lambda key, seconds=300: "https://bucket.example/p/" + key)):
            p = mock.patch.object(objstore, name, fn); p.start(); self.addCleanup(p.stop)

    def song(self, slug="song-001", licence=None, status="published"):
        D = os.path.join(self.C.songs_root(), slug); os.makedirs(D, exist_ok=True)
        open(os.path.join(D, "title.txt"), "w", encoding="utf-8").write("Tere Hone Se\n")
        pre = f"navaan/songs/{slug}/"; cover = png(); audio = b"ID3audio" * 100
        self.bucket[pre + "cover_1x1.png"] = cover; self.bucket[pre + "final.mp3"] = audio
        json.dump({"slug": slug, "type": "music", "state": status, "cloud": {"verified": True, "uploaded_at": "2026-10-01T10:00:00Z", "prefix": pre, "objects": {"cover_1x1.png": {"size": len(cover)}, "final.mp3": {"size": len(audio)}}}}, open(os.path.join(D, "meta.json"), "w"))
        self.K.sync_item(slug)
        if licence: self.K.set_license(slug, licence, "owner", "test")
        return slug


class Covers(Base):
    def test_sizes_formats_etag_and_cache(self):
        self.song()
        for fmt, mime in (("webp", "image/webp"), ("avif", "image/avif"), ("jpg", "image/jpeg")):
            data, etag, m = self.M.variant("song-001", 320, fmt); self.assertEqual(m, mime)
            im = Image.open(io.BytesIO(data)); self.assertLessEqual(max(im.size), 320)
        data, etag, _ = self.M.variant("song-001", 640, "webp"); n = len(self.gets)
        again = self.M.variant("song-001", 640, "webp"); self.assertEqual(again[1], etag); self.assertEqual(again[0], data); self.assertEqual(len(self.gets), n)   # served from the cache, the bucket is not asked again
        self.assertNotEqual(self.M.variant("song-001", 320, "webp")[1], etag)
        self.assertRaises(ValueError, self.M.variant, "song-001", 999, "webp"); self.assertRaises(ValueError, self.M.variant, "song-001", 320, "gif")
        self.assertIsNone(self.M.variant("ghost", 320, "webp"))

    def test_the_first_resize_records_size_and_dominant_colour(self):
        self.song(); self.M.variant("song-001", 320, "webp")
        a = self.K.cover_asset("song-001"); self.assertEqual(a["dominant_colour"], "#c82828")
        r = self.K._conn().execute("SELECT width, height FROM assets WHERE id = ?::uuid", (a["id"],)).fetchone(); self.assertEqual((r["width"], r["height"]), (400, 400))

    def test_a_draft_track_has_no_public_cover(self):
        self.song(status="drafted"); self.assertIsNone(self.M.variant("song-001", 320, "webp"))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
class Preview(Base):
    def test_the_preview_is_30_seconds_cut_once_and_stored_as_its_own_asset(self):
        self.song(); self.bucket["navaan/songs/song-001/final.mp3"] = mp3(40)
        key = self.M.ensure_preview("song-001"); self.assertEqual(key, "navaan/songs/song-001/derived/preview-30s.mp3")
        f = os.path.join(self.tmp.name, "p.mp3"); open(f, "wb").write(self.bucket[key])
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f], capture_output=True).stdout)
        self.assertAlmostEqual(dur, 30, delta=1.5)
        n = len(self.gets); self.assertEqual(self.M.ensure_preview("song-001"), key); self.assertEqual(len(self.gets), n)   # made once
        self.assertEqual(self.K.preview_asset("song-001")["storage_key"], key)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is not installed")
class PreviewCover(unittest.TestCase):
    def test_a_songs_embedded_cover_picture_and_tags_do_not_end_up_in_the_preview(self):
        import media
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d)
        open(os.path.join(d, "c.png"), "wb").write(png(1400, 1400))
        src = os.path.join(d, "song.mp3")
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440", "-i", os.path.join(d, "c.png"), "-t", "40", "-map", "0:a", "-map", "1:v", "-c:a", "libmp3lame", "-b:a", "64k", "-c:v", "mjpeg",
                        "-metadata", "title=Secret working title", "-id3v2_version", "3", src], check=True, timeout=60)
        self.assertIn("video", subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", src], capture_output=True, text=True).stdout)   # the source really has a picture
        out = media.cut_preview(open(src, "rb").read()); f = os.path.join(d, "p.mp3"); open(f, "wb").write(out)
        streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", f], capture_output=True, text=True).stdout.split()
        self.assertEqual(streams, ["audio"]); self.assertNotIn(b"Secret working title", out)
        self.assertLess(len(out), 30 * 12000 * 1.1)   # 96 kbit/s for 30 s is about 360 KB; a carried picture made it 470 KB


class Links(Base):
    def test_only_a_confirmed_published_track_can_be_shared_and_a_link_can_be_revoked(self):
        self.song()
        with self.assertRaises(ValueError): self.K.create_share("song-001", "owner")   # licence not confirmed
        self.K.set_license("song-001", "confirmed", "owner", "paid plan")
        with self.assertRaises(LookupError): self.K.create_share("ghost", "owner")
        tok = self.K.create_share("song-001", "owner", 92000)
        self.assertEqual(self.K.open_share(tok, count=True)["start_ms"], 92000); self.K.open_share(tok); self.K.open_share(tok, count=True)
        self.assertEqual(self.K.shares()[0]["opens"], 2)
        self.assertFalse(self.K.revoke_share(tok, "someone else")); self.assertIsNotNone(self.K.open_share(tok))   # not theirs
        self.assertTrue(self.K.revoke_share(tok, "owner")); self.assertIsNone(self.K.open_share(tok)); self.assertFalse(self.K.revoke_share(tok, "owner", True))
        self.assertEqual(self.K.shares("owner")[0]["revoked_at"] is not None, True)

    def test_a_link_stops_resolving_when_the_licence_is_withdrawn(self):
        self.song(licence="confirmed"); tok = self.K.create_share("song-001", "owner")
        self.K.set_license("song-001", "not_allowed", "owner", "terms changed"); self.assertIsNone(self.K.open_share(tok))

    def test_play_key_is_the_one_seam(self):
        self.song(); self.assertEqual(self.K.play_key("song-001"), "navaan/songs/song-001/final.mp3")   # unconfirmed may still be heard, not sold
        self.K.set_license("song-001", "not_allowed", "owner", "x"); self.assertIsNone(self.K.play_key("song-001")); self.assertIsNone(self.K.play_key("ghost"))
        self.song("song-002", status="drafted"); self.assertIsNone(self.K.play_key("song-002"))


class Signed(unittest.TestCase):
    """The SDK path, with a fake client: a link per object is made once and reused until it is nearly over."""
    def test_links_are_cached_and_renewed(self):
        import objstore
        made = []
        class Models:
            class CreatePreauthenticatedRequestDetails:
                def __init__(self, **kw): self.kw = kw
        fake_oci = types.SimpleNamespace(object_storage=types.SimpleNamespace(models=Models))
        class Client:
            def create_preauthenticated_request(self, ns, b, d): made.append(d.kw); return types.SimpleNamespace(data=types.SimpleNamespace(access_uri=f"/p/{len(made)}/n/ns/b/{b}/o/{d.kw['object_name']}"))
        with mock.patch.dict(sys.modules, {"oci": fake_oci}), mock.patch.object(objstore, "_CLIENT", (Client(), "ns")), mock.patch.object(objstore, "bucket", lambda: "navaan"), mock.patch.object(objstore, "_LINKS", {}), mock.patch.object(objstore, "_setting", lambda k, d="": "us-chicago-1"):
            u1 = objstore.par_url("a/b.mp3", 300, now=1000); self.assertTrue(u1.startswith("https://objectstorage.us-chicago-1.oraclecloud.com/p/1/"))
            self.assertEqual(objstore.par_url("a/b.mp3", 300, now=1100), u1); self.assertEqual(len(made), 1)       # still valid: reused
            self.assertNotEqual(objstore.par_url("a/b.mp3", 300, now=1000 + 300), u1); self.assertEqual(len(made), 2)   # within the last minute: renewed
            self.assertEqual(made[0]["access_type"], "ObjectRead"); self.assertEqual(made[0]["object_name"], "a/b.mp3")


if __name__ == "__main__":
    unittest.main()
