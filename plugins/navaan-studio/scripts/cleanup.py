#!/usr/bin/env python3
"""cleanup.py  free the local disk once a song is safe in the cloud. The last step of a song.

  cleanup.py <slug> [--yes]     dry run by default; --yes deletes (needs the local_cleanup gate approved by you)

Before anything is deleted the bucket is listed again, and every local file must be there with the same size. The song must be
published (YouTube, and Instagram when it is set up). Deleted: audio, video, images and clips. Kept: all text and json (lyrics,
meta.json with the cloud URLs, youtube.json, instagram.txt, plans) and logs. Nothing outside the song folder is touched.
"""
import os, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import song_dir, cfg, require_approval, meta_path, load_json
import storage

KEEP_EXT = (".txt", ".json", ".md", ".srt", ".log")


def main(argv):
    if not argv or argv[0].startswith("-"): print(__doc__); return 2
    slug, yes = argv[0], "--yes" in argv
    prov = cfg("storage.cloud_provider", "none")
    if prov in ("none", None, ""): print("Cloud storage is off, so nothing is safe to delete."); return 4
    D = song_dir(slug); m = load_json(meta_path(slug), default={})
    if not m.get("cloud", {}).get("uploaded_at"): print("This song is not archived yet. Run the archive step first."); return 4
    pub = m.get("published", {})
    if not pub.get("youtube_items"): print("The song is not on YouTube yet. Clean up only after publishing."); return 4
    if cfg("publish.instagram_handle") and not pub.get("instagram"): print("Instagram is set up but the Reel is not posted yet. Clean up after it is."); return 4
    try:
        dest, ns, local, remote, missing, mism = storage.compare(prov, cfg("storage.cloud_bucket"), cfg("storage.cloud_prefix", ""), cfg("storage.cloud_region", ""), D, slug)
    except RuntimeError as e: print(f"cannot check the bucket: {e}"); return 1
    if missing or mism:
        print(f"The bucket does not hold every local file. Missing: {missing}. Different size: {mism}. Run the archive step again. Nothing deleted."); return 1
    kill = [k for k in sorted(local) if not k.lower().endswith(KEEP_EXT)]
    size = sum(local[k] for k in kill)
    print(f"verified: all {len(local)} local files are in the bucket under {dest}\nwill delete {len(kill)} media files, {size/1e6:.0f} MB; keeps {len(local) - len(kill)} text files and the logs")
    for k in kill: print("  -", k)
    if not yes: print("\nDRY RUN. Nothing deleted. Re-run with --yes after you approve the local_cleanup gate."); return 0
    require_approval(slug, "local_cleanup")
    for k in kill:
        try: os.remove(os.path.join(D, k))
        except OSError as e: print(f"could not delete {k}: {e}")
    for r, ds, fs in sorted(os.walk(D, topdown=False)):
        if r != D and not os.listdir(r):
            try: os.rmdir(r)
            except OSError: pass
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    m = load_json(meta_path(slug), default={}); m["cleanup"] = {"at": now, "removed": len(kill), "freed_mb": round(size / 1e6), "removed_files": kill, "restore_from": m.get("cloud", {}).get("uri")}
    m.setdefault("history", []).append(f"{now} local cleanup removed {len(kill)} files ({round(size / 1e6)} MB), copy is in {m['cleanup']['restore_from']}")
    json.dump(m, open(meta_path(slug), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"deleted {len(kill)} files, freed {size/1e6:.0f} MB. Copy stays in the bucket."); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
