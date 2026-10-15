"""Storage checks and cloud upload for NAVAAN Studio.

Local: the folder where songs are created and exported while you work. It must sit outside the plugin folder and outside the
repository that ships the plugin. The folder you started your workspace in is a good choice.
Cloud: where a finished song is archived (oci, s3 or gcs). It is checked with the provider's own CLI and your own credentials.
"""
import os, sys, json, shutil, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import plugin_dir, plugin_repo_root
import navaan_log as L
LOG = L.get("storage")

PROVIDERS = ("none", "oci", "s3", "gcs")
CLI = {"oci": "oci", "s3": "aws", "gcs": "gcloud"}
EXCLUDES = (".cache", "logs")
# Videos are not archived: they are already on YouTube and Instagram, and they are the heavy files. Audio, images, text and json are.
VIDEO_EXT = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi")


def _inside(child, parent):
    c, p = os.path.realpath(child), os.path.realpath(parent)
    return c == p or c.startswith(p + os.sep)


def _git_root(path):
    d = os.path.realpath(path)
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        p = os.path.dirname(d)
        if p == d:
            return None
        d = p


def check_local(path, create=False):
    """Return a list of (level, message) with level error, warn or ok."""
    out = []
    if not path:
        return [("error", "local folder is empty")]
    p = os.path.realpath(os.path.expanduser(path))
    if not os.path.isabs(os.path.expanduser(path)):
        out.append(("error", f"use an absolute path, not '{path}'"))
    if _inside(p, plugin_dir()):
        out.append(("error", f"{p} is inside the plugin folder ({plugin_dir()}). Choose another folder."))
    repo = plugin_repo_root()
    if _inside(p, repo):
        out.append(("error", f"{p} is inside the repository that ships the plugin ({repo}). Choose a folder outside it."))
    if any(l == "error" for l, _ in out):
        return out
    if not os.path.isdir(p):
        if create:
            try: os.makedirs(p, exist_ok=True)
            except OSError as e: L.ignored(LOG, "check_local: OSError (optional or expected)", e); return [("error", f"cannot create {p}: {e}")]
            out.append(("ok", f"created {p}"))
        else:
            out.append(("warn", f"{p} does not exist yet (it will be created)"))
            probe = p
            while not os.path.isdir(probe):
                probe = os.path.dirname(probe)
            if not os.access(probe, os.W_OK): out.append(("error", f"cannot write under {probe}"))
            return out
    try:
        with tempfile.NamedTemporaryFile(dir=p, prefix=".navaan-check-", delete=True) as f: f.write(b"ok")
        out.append(("ok", f"{p} is writable"))
    except OSError as e:
        L.ignored(LOG, "check_local: OSError (optional or expected)", e)
        out.append(("error", f"{p} is not writable: {e}"))
    g = _git_root(p)
    if g:
        out.append(("warn", f"{p} is inside a git repository ({g}). Songs and media may get committed by accident."))
    try:
        free = shutil.disk_usage(p).free / 1e9
        out.append(("warn" if free < 2 else "ok", f"{free:.1f} GB free"))
    except OSError as _e:
        L.ignored(LOG, "check_local: OSError (optional or expected)", _e)
        pass
    return out


def _run(cmd, timeout=40):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError as _e:
        L.ignored(LOG, "_run: FileNotFoundError (optional or expected)", _e)
        return 127, "", f"{cmd[0]} not found"
    except subprocess.TimeoutExpired as _e:
        L.ignored(LOG, "_run: TimeoutExpired (optional or expected)", _e)
        return 124, "", "timed out"


def _oci_ns():
    rc, out, err = _run(["oci", "os", "ns", "get", "--query", "data", "--raw-output"])
    return (out if rc == 0 else None), err


_MISSING = {}  # path -> time of the last failed fetch, so a file that is not in the bucket is not asked for on every request
_FETCHING = set()


def fetch_missing(path, retry_after=3600):
    """One file of a song that was archived and then cleaned locally, brought back from the bucket. True when the file exists afterwards.
    Only paths inside a song folder whose meta.json records a cloud copy; the bucket key comes from that record (cloud.prefix). oci only."""
    import time, navaan_common as C
    if os.path.exists(path): return True
    root = os.path.abspath(C.songs_root()); full = os.path.abspath(path)
    parts = os.path.relpath(full, root).split(os.sep)
    if full == root or len(parts) < 2 or any(x in ("", ".", "..") for x in parts) or not full.startswith(root + os.sep): return False
    if time.time() - _MISSING.get(full, 0) < retry_after or full in _FETCHING: return False
    try: cl = (json.load(open(os.path.join(root, parts[0], "meta.json"), encoding="utf-8")).get("cloud") or {})
    except (OSError, ValueError) as _e: L.ignored(LOG, "fetch_missing: OSError/ValueError (optional or expected)", _e); return False
    if cl.get("provider") != "oci" or not (cl.get("bucket") and cl.get("namespace") and cl.get("uploaded_at")): return False
    key = (cl.get("prefix") or "").strip("/") + "/" + "/".join(parts[1:])
    tmp = full + ".part"; _FETCHING.add(full)
    try:
        os.makedirs(os.path.dirname(full), exist_ok=True)
        rc, _, err = _run(["oci", "os", "object", "get", "-ns", cl["namespace"], "-bn", cl["bucket"], "--name", key, "--file", tmp], timeout=300)
        if rc == 0 and os.path.exists(tmp): os.replace(tmp, full); return True
        _MISSING[full] = time.time(); return False
    finally:
        _FETCHING.discard(full)
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except OSError as _e: L.ignored(LOG, "fetch_missing: OSError (optional or expected)", _e); pass


def check_cloud(provider, bucket, prefix="", region="", write=False):
    """Check the cloud location with the provider CLI. write=True also puts and deletes a tiny test object."""
    if provider in (None, "", "none"):
        return [("ok", "cloud upload is off (provider none)")]
    if provider not in PROVIDERS:
        return [("error", f"provider must be one of {', '.join(PROVIDERS)}")]
    if not bucket:
        return [("error", "bucket name is empty")]
    cli = CLI[provider]
    if not shutil.which(cli):
        return [("error", f"the {cli} command line tool is not installed or not on PATH")]
    key = (prefix.strip("/") + "/" if prefix else "") + ".navaan-verify"
    out = []
    if provider == "oci":
        ns, err = _oci_ns()
        if not ns: return [("error", f"oci is not configured or not signed in: {err[:200]}")]
        rc, _, err = _run(["oci", "os", "bucket", "get", "-ns", ns, "-bn", bucket])
        if rc: return [("error", f"cannot read bucket '{bucket}' in namespace {ns}: {err[:200]}")]
        out.append(("ok", f"oci bucket '{bucket}' found (namespace {ns})"))
        if write:
            with tempfile.NamedTemporaryFile(suffix=".txt") as f:
                f.write(b"navaan verify"); f.flush()
                rc, _, err = _run(["oci", "os", "object", "put", "-ns", ns, "-bn", bucket, "--file", f.name, "--name", key, "--force"])
            if rc: return out + [("error", f"cannot write to the bucket: {err[:200]}")]
            _run(["oci", "os", "object", "delete", "-ns", ns, "-bn", bucket, "--object-name", key, "--force"])
            out.append(("ok", "test write and delete worked"))
    elif provider == "s3":
        base = ["aws"] + (["--region", region] if region else [])
        rc, _, err = _run(base + ["s3api", "head-bucket", "--bucket", bucket])
        if rc: return [("error", f"cannot access s3 bucket '{bucket}': {err[:200]}")]
        out.append(("ok", f"s3 bucket '{bucket}' is reachable"))
        if write:
            with tempfile.NamedTemporaryFile(suffix=".txt") as f:
                f.write(b"navaan verify"); f.flush()
                rc, _, err = _run(base + ["s3", "cp", f.name, f"s3://{bucket}/{key}"])
            if rc: return out + [("error", f"cannot write to the bucket: {err[:200]}")]
            _run(base + ["s3", "rm", f"s3://{bucket}/{key}"])
            out.append(("ok", "test write and delete worked"))
    else:
        rc, _, err = _run(["gcloud", "storage", "buckets", "describe", f"gs://{bucket}", "--format=value(name)"])
        if rc: return [("error", f"cannot access gcs bucket '{bucket}': {err[:200]}")]
        out.append(("ok", f"gcs bucket '{bucket}' is reachable"))
        if write:
            with tempfile.NamedTemporaryFile(suffix=".txt") as f:
                f.write(b"navaan verify"); f.flush()
                rc, _, err = _run(["gcloud", "storage", "cp", f.name, f"gs://{bucket}/{key}"])
            if rc: return out + [("error", f"cannot write to the bucket: {err[:200]}")]
            _run(["gcloud", "storage", "rm", f"gs://{bucket}/{key}"])
            out.append(("ok", "test write and delete worked"))
    return out


def upload_commands(provider, bucket, prefix, region, src_dir, slug):
    """Commands that copy one song folder to <bucket>/<prefix>/<slug>/. Excludes .cache and logs."""
    dest_prefix = (prefix.strip("/") + "/" if prefix else "") + slug + "/"
    if provider == "oci":
        ns, err = _oci_ns()
        if not ns: raise RuntimeError(f"oci is not configured: {err[:200]}")
        cmd = ["oci", "os", "object", "bulk-upload", "-ns", ns, "-bn", bucket, "--src-dir", src_dir, "--object-prefix", dest_prefix, "--overwrite"]
        for e in EXCLUDES: cmd += ["--exclude", f"{e}/*"]
        for e in VIDEO_EXT: cmd += ["--exclude", f"*{e}"]
        return [cmd], f"oci://{ns}/{bucket}/{dest_prefix}"
    if provider == "s3":
        cmd = ["aws"] + (["--region", region] if region else []) + ["s3", "sync", src_dir, f"s3://{bucket}/{dest_prefix}"]
        for e in EXCLUDES: cmd += ["--exclude", f"{e}/*"]
        for e in VIDEO_EXT: cmd += ["--exclude", f"*{e}"]
        return [cmd], f"s3://{bucket}/{dest_prefix}"
    if provider == "gcs":
        return [["gcloud", "storage", "rsync", "--recursive", "--exclude", "^(\\.cache|logs)/.*|.*(" + "|".join(e.replace(".", "\\.") for e in VIDEO_EXT) + ")$", src_dir, f"gs://{bucket}/{dest_prefix}"]], f"gs://{bucket}/{dest_prefix}"
    raise RuntimeError("cloud upload is off. Set storage.cloud_provider in the profile.")


def object_url(provider, bucket, region, ns, key):
    """Plain object URL. A private bucket needs a signed or pre-authenticated link to open it, so this is the address, not a share link."""
    from urllib.parse import quote
    if provider == "oci": return f"https://objectstorage.{region}.oraclecloud.com/n/{ns}/b/{bucket}/o/{quote(key)}"
    if provider == "s3": return f"https://{bucket}.s3{'.' + region if region else ''}.amazonaws.com/{quote(key)}"
    if provider == "gcs": return f"https://storage.googleapis.com/{bucket}/{quote(key)}"
    return ""


def list_objects(provider, bucket, prefix, region=""):
    """Return {object name: size in bytes} for everything under prefix, read with the provider CLI. Raises RuntimeError on failure."""
    if provider == "oci":
        ns, err = _oci_ns()
        if not ns: raise RuntimeError(f"oci is not configured: {err[:200]}")
        rc, out, err = _run(["oci", "os", "object", "list", "-ns", ns, "-bn", bucket, "--prefix", prefix, "--all", "--fields", "name,size"], timeout=120)
        if rc: raise RuntimeError(f"cannot list the bucket: {err[:200]}")
        return {o["name"]: int(o.get("size") or 0) for o in (json.loads(out).get("data", []) if out else [])}
    if provider == "s3":
        rc, out, err = _run(["aws"] + (["--region", region] if region else []) + ["s3api", "list-objects-v2", "--bucket", bucket, "--prefix", prefix, "--output", "json"], timeout=120)
        if rc: raise RuntimeError(f"cannot list the bucket: {err[:200]}")
        return {o["Key"]: int(o["Size"]) for o in (json.loads(out or "{}").get("Contents") or [])}
    if provider == "gcs":
        rc, out, err = _run(["gcloud", "storage", "ls", "--long", "--recursive", f"gs://{bucket}/{prefix}"], timeout=120)
        if rc: raise RuntimeError(f"cannot list the bucket: {err[:200]}")
        res = {}
        for ln in out.splitlines():
            parts = ln.split()
            if len(parts) >= 3 and parts[2].startswith(f"gs://{bucket}/") and parts[0].isdigit(): res[parts[2][len(f"gs://{bucket}/"):]] = int(parts[0])
        return res
    raise RuntimeError("cloud storage is off")


def local_files(src_dir):
    """Relative paths and sizes of what the archive uploads (everything except .cache, logs and videos)."""
    res = {}
    for r, ds, fs in os.walk(src_dir):
        rel = os.path.relpath(r, src_dir)
        if rel.split(os.sep)[0] in EXCLUDES: ds[:] = []; continue
        for f in fs:
            if f.lower().endswith(VIDEO_EXT): continue  # videos are not archived
            full = os.path.join(r, f); res[os.path.normpath(os.path.join(rel, f)).replace(os.sep, "/")] = os.path.getsize(full)
    return res


def compare(provider, bucket, prefix, region, src_dir, slug):
    """Compare the local song folder with the bucket. Returns (dest_prefix, ns, local, remote, missing, mismatched)."""
    dest = (prefix.strip("/") + "/" if prefix else "") + slug + "/"
    ns = _oci_ns()[0] if provider == "oci" else ""
    remote = list_objects(provider, bucket, dest, region); local = local_files(src_dir)
    missing = sorted(k for k in local if dest + k not in remote)
    # meta.json changes by design after the upload (the cloud block is written into it), so a size difference there is not a mismatch
    mism = sorted(k for k in local if k != "meta.json" and dest + k in remote and remote[dest + k] != local[k])
    return dest, ns, local, remote, missing, mism


def signed_url(provider, bucket, region, key, hours=1):
    """A link that opens one object for a short time, made with the user's own CLI login. oci: pre-authenticated request, s3: presign."""
    import datetime
    if provider == "oci":
        ns, err = _oci_ns()
        if not ns: raise RuntimeError(f"oci is not configured: {err[:200]}")
        exp = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        rc, out, err = _run(["oci", "os", "preauth-request", "create", "-ns", ns, "-bn", bucket, "--name", f"navaan-browse-{int(datetime.datetime.now().timestamp())}",
                             "--access-type", "ObjectRead", "--object-name", key, "--time-expires", exp, "--query", 'data."access-uri"', "--raw-output"])
        if rc or not out: raise RuntimeError(f"cannot make a link: {err[:200]}")
        return f"https://objectstorage.{region}.oraclecloud.com{out}"
    if provider == "s3":
        rc, out, err = _run(["aws"] + (["--region", region] if region else []) + ["s3", "presign", f"s3://{bucket}/{key}", "--expires-in", str(hours * 3600)])
        if rc: raise RuntimeError(f"cannot make a link: {err[:200]}")
        return out
    raise RuntimeError("links are supported for oci and s3 only")
