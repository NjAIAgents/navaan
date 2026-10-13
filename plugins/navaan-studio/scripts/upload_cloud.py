#!/usr/bin/env python3
"""upload_cloud.py  archive a finished song folder to your cloud bucket.

  upload_cloud.py <slug> [--yes]     dry run by default; --yes sends (needs the cloud_upload gate approved by you)
  upload_cloud.py <slug> --record    read only: list the bucket, verify it against the local folder and record the URLs in meta.json
  upload_cloud.py --verify [--write] check the local folder and the cloud location from the profile

While you work, everything stays in the local folder (storage.local_dir). Run this once a song is final.
Credentials are your own CLI login (oci, aws or gcloud). Nothing is stored in the project.
"""
import os, sys, json, datetime, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import song_dir, cfg, require_approval, meta_path, load_json
import storage


def verify(write=False):
    bad = False
    for lvl, msg in storage.check_local(cfg("storage.local_dir")): print(f"[{lvl}] local: {msg}"); bad |= lvl == "error"
    for lvl, msg in storage.check_cloud(cfg("storage.cloud_provider", "none"), cfg("storage.cloud_bucket", ""), cfg("storage.cloud_prefix", ""), cfg("storage.cloud_region", ""), write=write):
        print(f"[{lvl}] cloud: {msg}"); bad |= lvl == "error"
    return 1 if bad else 0


def record(slug, uploaded_at=None, uri=None):
    """List the bucket, compare it with the local folder, and write meta.json cloud: provider, bucket, prefix, one URL per file and verified yes or no."""
    prov, bucket, region = cfg("storage.cloud_provider", "none"), cfg("storage.cloud_bucket"), cfg("storage.cloud_region", "")
    D = song_dir(slug)
    dest, ns, local, remote, missing, mism = storage.compare(prov, bucket, cfg("storage.cloud_prefix", ""), region, D, slug)
    m = load_json(meta_path(slug), default={}); old = m.get("cloud", {})
    objs = {k: {"size": local[k], "url": storage.object_url(prov, bucket, region, ns, dest + k)} for k in sorted(local) if dest + k in remote}
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    m["cloud"] = {"uploaded_at": uploaded_at or old.get("uploaded_at") or now, "uri": uri or old.get("uri") or f"{prov}://{ns + '/' if ns else ''}{bucket}/{dest}",
                  "provider": prov, "bucket": bucket, "region": region, "namespace": ns, "prefix": dest, "folder_url": storage.object_url(prov, bucket, region, ns, dest),
                  "files": len(objs), "bytes": sum(o["size"] for o in objs.values()), "verified": not missing and not mism, "verified_at": now,
                  "missing": missing, "size_mismatch": mism, "objects": objs}
    if old.get("cleanup_ok") is not None: m["cloud"]["cleanup_ok"] = old["cleanup_ok"]
    m.setdefault("history", []).append(f"{now} cloud record {len(objs)} files verified={m['cloud']['verified']}")
    json.dump(m, open(meta_path(slug), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"recorded {len(objs)} objects under {dest}, verified={m['cloud']['verified']}" + (f", missing {missing}" if missing else "") + (f", size mismatch {mism}" if mism else ""))
    return 0 if m["cloud"]["verified"] else 1


def main(argv):
    if "--verify" in argv: return verify("--write" in argv)
    if "--record" in argv and argv and not argv[0].startswith("-"): return record(argv[0])
    if not argv or argv[0].startswith("-"): print(__doc__); return 2
    slug, yes = argv[0], "--yes" in argv
    prov = cfg("storage.cloud_provider", "none")
    if prov in ("none", None, ""): print("Cloud upload is off. Set storage.cloud_provider in navaan.config.json (python scripts/setup_profile.py --edit)."); return 4
    D = song_dir(slug)
    cmds, uri = storage.upload_commands(prov, cfg("storage.cloud_bucket"), cfg("storage.cloud_prefix", ""), cfg("storage.cloud_region", ""), D, slug)
    total = sum(os.path.getsize(os.path.join(r, f)) for r, ds, fs in os.walk(D) if not any(x in r.split(os.sep) for x in storage.EXCLUDES) for f in fs)
    print(f"from {D} ({total/1e6:.0f} MB, without .cache and logs)\nto   {uri}")
    for c in cmds: print("  $", " ".join(c))
    if not yes: print("\nDRY RUN. Nothing sent. Re-run with --yes after you approve the cloud_upload gate."); return 0
    require_approval(slug, "cloud_upload")
    for c in cmds:
        rc = subprocess.call(c)
        if rc: print("upload failed, exit", rc); return 1
    up = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print("uploaded", uri, "verifying against the bucket")
    rc = record(slug, uploaded_at=up, uri=uri)
    m = load_json(meta_path(slug), default={}); m.setdefault("history", []).append(f"{up} cloud upload to {uri}")
    json.dump(m, open(meta_path(slug), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    if rc: print("the bucket does not match the local folder. Nothing may be cleaned up until it does. Run the archive step again."); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
