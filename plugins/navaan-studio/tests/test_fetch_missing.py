"""A song archived in the bucket and cleaned locally gets single files back on demand. Run: python3 -W ignore -m unittest test_fetch_missing"""
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import storage as ST


class Fetch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["NAVAAN_ROOT"] = self.tmp.name
        import navaan_common as C
        self.root = C.songs_root(); self.D = os.path.join(self.root, "song-9"); os.makedirs(self.D)
        self.cloud = {"provider": "oci", "bucket": "b", "namespace": "ns", "prefix": "navaan/songs/song-9/", "uploaded_at": "2026-10-13T00:00:00Z"}
        json.dump({"slug": "song-9", "cloud": self.cloud}, open(os.path.join(self.D, "meta.json"), "w"))
        self.calls = []; self.have = {"navaan/songs/song-9/thumb_16x9.jpg": b"JPEGDATA", "navaan/songs/song-9/sub/a.png": b"PNG"}
        self.o = ST._run; ST._run = self.fake; ST._MISSING.clear(); ST._FETCHING.clear()

    def tearDown(self): ST._run = self.o; self.tmp.cleanup(); os.environ.pop("NAVAAN_ROOT", None)

    def fake(self, cmd, timeout=40):
        self.calls.append(cmd); key = cmd[cmd.index("--name") + 1]; out = cmd[cmd.index("--file") + 1]
        if key in self.have: open(out, "wb").write(self.have[key]); return 0, "", ""
        return 1, "", "ObjectNotFound"

    def test_missing_file_is_fetched_with_the_recorded_prefix(self):
        p = os.path.join(self.D, "thumb_16x9.jpg")
        self.assertTrue(ST.fetch_missing(p)); self.assertEqual(open(p, "rb").read(), b"JPEGDATA")
        c = self.calls[0]; self.assertEqual((c[c.index("-ns") + 1], c[c.index("-bn") + 1], c[c.index("--name") + 1]), ("ns", "b", "navaan/songs/song-9/thumb_16x9.jpg"))
        self.assertFalse(os.path.exists(p + ".part"))

    def test_nested_file(self):
        p = os.path.join(self.D, "sub", "a.png"); self.assertTrue(ST.fetch_missing(p)); self.assertTrue(os.path.exists(p))

    def test_existing_file_costs_no_call(self):
        p = os.path.join(self.D, "x.txt"); open(p, "w").write("hi")
        self.assertTrue(ST.fetch_missing(p)); self.assertEqual(self.calls, [])

    def test_not_in_bucket_is_remembered_and_leaves_nothing_behind(self):
        p = os.path.join(self.D, "nope.png")
        self.assertFalse(ST.fetch_missing(p)); self.assertFalse(ST.fetch_missing(p)); self.assertEqual(len(self.calls), 1)
        self.assertEqual(os.listdir(self.D).count("nope.png") + os.listdir(self.D).count("nope.png.part"), 0)

    def test_paths_outside_a_song_are_refused(self):
        for p in (os.path.join(self.D, "..", "..", "etc", "passwd"), os.path.join(self.root, "other.txt"), "/nonexistent/outside.txt", os.path.join(self.D, "..", "meta.json")):
            self.assertFalse(ST.fetch_missing(p), p)
        self.assertEqual(self.calls, [])

    def test_song_that_was_never_archived_or_not_oci_is_left_alone(self):
        m = json.load(open(os.path.join(self.D, "meta.json")))
        for bad in ({}, dict(self.cloud, uploaded_at=""), dict(self.cloud, provider="s3")):
            m["cloud"] = bad; json.dump(m, open(os.path.join(self.D, "meta.json"), "w")); ST._MISSING.clear()
            self.assertFalse(ST.fetch_missing(os.path.join(self.D, "thumb_16x9.jpg")))
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
