"""Local web UI for NAVAAN Studio. Bound to 127.0.0.1 unless NAVAAN_BIND says otherwise. Standard library only.
Create songs, edit and review text, play media, approve gates (human clicks only), and start the next step."""
import os, re, json, glob, gzip, hashlib, hmac, mimetypes, threading, secrets, subprocess, sys, html, logging
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import time
from urllib.parse import parse_qs, urlparse
import navaan, navaan_common as C, storage, analytics_api, settings_api
import clip_share as CLIP, poster as POST, album_pipeline as ALB, visuals_cfg as V, prompt_pack, shots_prep, publish_schedule as PS, besttime, analytics_auto
import auth
import jobs, worker
import catalog_store, search as SEARCH
import media, objstore, share_page
import library_store, entitlements, uuid, pgconn
import navaan_log as L
LOG = L.get("web")

TOKEN = secrets.token_urlsafe(24)
def _hosts(var): return [h.strip().lower() for h in os.environ.get(var, "").split(",") if h.strip()]
PUBLIC_HOST = lambda: ",".join(_hosts("NAVAAN_PUBLIC_HOST"))  # extra allowed Hosts (a comma list), e.g. navaan.njlabs.dev,studio.navaan.online,navaan.online
LISTENER_HOSTS = lambda: _hosts("NAVAAN_LISTENER_HOSTS")   # the hosts that are the public face (navaan.online): whoever signs in there is treated as a listener, the studio is on the other hosts
TRUST_PROXY = lambda: os.environ.get("NAVAAN_TRUST_PROXY", "0") == "1"  # only behind nginx on a private network
def secrets_status():
    """Vault sync state written by deploy/vault_sync.py: {"status": ok|waiting|sealed, "detail"}; None when this portal does not use Vault (the Mac)."""
    f = os.environ.get("NAVAAN_SECRETS_STATUS") or os.path.expanduser("~/.config/navaan/secrets.status")
    try:
        d = json.load(open(f, encoding="utf-8"))
        if time.time() - d.get("at", 0) > 120: d.update(status="waiting", detail="sync stopped")
        return d
    except (OSError, ValueError) as _e:
        L.ignored(LOG, "secrets_status: OSError/ValueError (optional or expected)", _e)
        return {"status": "waiting", "detail": "no status yet"} if os.environ.get("NAVAAN_VAULT_ADDR") else None


def app_version():
    """The release number, set in one place: plugin.json (tests keep marketplace.json, web/package.json and CHANGELOG.md equal to it)."""
    try:
        with open(os.path.join(navaan.HERE, "..", ".claude-plugin", "plugin.json"), encoding="utf-8") as f: return str(json.load(f).get("version", ""))
    except (OSError, ValueError) as e:
        L.ignored(LOG, "no plugin.json next to the scripts: no version to show", e); return ""


def web_dist():
    """Where the built app (plugins/navaan-studio/web/dist) is; NAVAAN_WEB_DIST overrides it for tests."""
    return os.environ.get("NAVAAN_WEB_DIST") or os.path.join(navaan.HERE, "..", "web", "dist")


def web_file(rel):
    """(bytes, content type, cache header) for a file of the built app, or None. Never leaves the dist folder."""
    root = os.path.realpath(web_dist()); p = os.path.realpath(os.path.join(root, rel))
    if not (p == root or p.startswith(root + os.sep)) or not os.path.isfile(p): return None
    ct = mimetypes.guess_type(p)[0] or "application/octet-stream"
    body = open(p, "rb").read()
    if rel.startswith("assets/"): return body, ct, "public, max-age=31536000, immutable"   # file names carry a content hash
    return body, ct, "no-store"


GZ_TYPES = ("text/css", "text/javascript", "application/javascript", "image/svg+xml", "application/json", "text/html")
GZ_CACHE = {}   # md5 of the bytes -> gzipped bytes; the built app is a handful of files, so this stays small
def gz(data, ctype, accept):
    """(body, extra headers): the file gzipped when the browser accepts it and it is worth it. The built app is served by this process, so without this a phone downloads 300 KB of script uncompressed."""
    if len(data) < 1024 or ctype not in GZ_TYPES or "gzip" not in (accept or ""): return data, {}
    k = hashlib.md5(data).digest()
    if k not in GZ_CACHE:
        if len(GZ_CACHE) > 64: GZ_CACHE.clear()
        GZ_CACHE[k] = gzip.compress(data, 9, mtime=0)
    return GZ_CACHE[k], {"Content-Encoding": "gzip", "Vary": "Accept-Encoding"}


def worker_state():
    """embedded (development: threads of this process) | on (a separate worker has reported in lately) | down (jobs are queued but nobody will run them)."""
    if not worker.external(): return "embedded"
    try: return "on" if jobs.workers_alive() else "down"
    except Exception: L.soft(LOG, "worker_state_failed"); return "down"


def scheduler_on(): return os.environ.get("NAVAAN_SCHEDULER", "on").lower() != "off"  # off on the Mac once the server owns the schedule
def scheduler_state():
    """on | off | paused (secrets not ok: publishing needs the tokens from Vault)."""
    if not scheduler_on(): return "off"
    sec = secrets_status()
    return "paused" if sec and sec["status"] != "ok" else "on"


TRY = {}  # slug -> {"running": bool, "error": str}, the 2 picture test
ALBUM_COVER = {}  # album slug -> {"running": bool, "error": str}, the album cover being made
POSTER = {}  # slug -> {"running": bool, "error": str}, the poster being made
VERT = {}  # slug -> {"running": bool, "error": str}, the native 9:16 recompose of chosen pictures
EDITABLE = {"brief.md", "lyrics.txt", "style.txt", "title.txt", "tags.json", "instagram.txt", "quote.json"}
READABLE = EDITABLE | {"originality.json", "timing.json", "render_report.json", "youtube.json", "shots.json", "visuals.json"}
THUMB_W = (160, 480, 960)  # the only widths served, so the cache cannot grow without bound
THUMB_DIR = os.path.join(os.path.expanduser("~"), ".cache", "navaan", "thumbs")
MEDIA_EXT = {".mp3", ".mp4", ".png", ".jpg", ".jpeg", ".webp", ".json", ".txt", ".md", ".log"}
LOCAL_USER = str(uuid.uuid5(uuid.NAMESPACE_URL, "navaan-local-dev-user"))   # the one person when the login is off
LOCAL_LISTENER = str(uuid.uuid5(uuid.NAMESPACE_URL, "navaan-local-dev-listener"))   # the same, signed in as a listener
LISTENER_ROUTES = (("/api/playlists", "library.view", "playlists.write"), ("/api/library", "library.view", "playlists.write"), ("/api/plans", "library.view", None), ("/api/account", "account.manage", "account.manage"),
                   ("/api/catalog", "library.view", None), ("/api/share", "library.view", "playlists.write"), ("/api/clip", "library.view", "library.view"))   # prefix, permission to read, to change
SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,40}$")


def songs():
    return sorted(os.path.basename(p) for p in glob.glob(f"{C.songs_root()}/*") if os.path.isdir(p) and not os.path.basename(p).startswith("_"))


def song_row(s):
    """One line per song for the dashboard, library and approvals views."""
    D = C.song_dir(s); m = navaan.meta(s)
    try: rows, n = navaan.plan(s)
    except SystemExit as _e: L.ignored(LOG, "song_row: SystemExit (optional or expected)", _e); rows, n = [], {"type": "none"}
    pub = m.get("published", {}); its = list(pub.get("youtube_items", [])) + ([pub["youtube_short"]] if pub.get("youtube_short", {}).get("id") else [])
    cl = m.get("cloud", {}); public = navaan.public_done(m)
    ig_on = navaan.ig_enabled(m)
    if n.get("type") == "gate": status = "approval"
    elif n.get("type") == "done": status = "done"
    else: status = "production"
    tp = os.path.join(D, "title.txt")
    return {"slug": s, "type": C.item_type(m), "state": m.get("state"), "next": n, "title": open(tp, encoding="utf-8").read().strip() if os.path.exists(tp) else "",
            "album": m.get("album", ""), "status": status, "steps_done": sum(1 for r in rows if r.get("done")), "steps_total": len(rows),
            "public": public, "scheduled": PS.status_text(m), "ig_enabled": ig_on, "published": public and (bool(pub.get("instagram")) or not ig_on), "private": bool(its) and not public, "instagram": bool(pub.get("instagram")), "instagram_url": (pub.get("instagram") or "") if str(pub.get("instagram") or "").startswith("http") else "", "archived": bool(cl.get("uploaded_at")),
            "verified": cl.get("verified"), "cleaned": bool(m.get("cleanup")), "youtube": (pub.get("youtube_items") or [{}])[0].get("url", ""),
            "audio": os.path.exists(os.path.join(D, "final.mp3")), "cover": os.path.exists(os.path.join(D, "cover_1x1.png")),
            "thumb_pending": bool(pub.get("thumbnail_pending")), "source": m.get("source", ""), "mtime": int(os.path.getmtime(os.path.join(D, "meta.json"))) if os.path.exists(os.path.join(D, "meta.json")) else 0}


CLOUD = {"at": 0, "data": None}


def cloud_view(refresh=False):
    """List the songs in the bucket (one folder per slug under storage.cloud_prefix) and match them with local songs. Cached for a minute."""
    prov = C.cfg("storage.cloud_provider", "none")
    if prov in ("none", None, ""): return {"configured": False}
    if not refresh and CLOUD["data"] and time.time() - CLOUD["at"] < 60: return CLOUD["data"]
    bucket, region, prefix = C.cfg("storage.cloud_bucket"), C.cfg("storage.cloud_region", ""), C.cfg("storage.cloud_prefix", "")
    pre = (prefix.strip("/") + "/") if prefix else ""
    out = {"configured": True, "provider": prov, "bucket": bucket, "region": region, "prefix": pre, "songs": []}
    try: objs = storage.list_objects(prov, bucket, pre, region)
    except RuntimeError as e: L.ignored(LOG, "cloud_view: RuntimeError (optional or expected)", e); out["error"] = str(e); return out
    by = {}
    for k, sz in objs.items():
        rel = k[len(pre):]; slug, _, name = rel.partition("/")
        if name: by.setdefault(slug, []).append({"name": name, "size": sz, "key": k})
    local = set(songs())
    for slug in sorted(by):
        m = navaan.meta(slug) if slug in local else {}; fl = sorted(by[slug], key=lambda x: x["name"])
        title = ""
        tp = os.path.join(C.songs_root(), slug, "title.txt")
        if os.path.exists(tp): title = open(tp, encoding="utf-8").read().strip()
        out["songs"].append({"slug": slug, "title": title, "files": fl, "bytes": sum(f["size"] for f in fl), "local": slug in local,
                             "cleaned": bool(m.get("cleanup")), "uploaded_at": m.get("cloud", {}).get("uploaded_at"), "verified": m.get("cloud", {}).get("verified"),
                             "youtube": [i.get("url") for i in m.get("published", {}).get("youtube_items", [])], "instagram": m.get("published", {}).get("instagram") or ""})
    CLOUD["at"] = time.time(); CLOUD["data"] = out
    return out


def detail(slug):
    D = C.song_dir(slug)
    try: navaan.auto_gates(slug)   # gates switched off in Settings approve themselves
    except Exception as _e: L.soft(LOG, "detail_error"); pass
    m = navaan.meta(slug); rows, nxt = navaan.plan(slug)
    fl = {}
    for f in sorted(os.listdir(D)):
        p = os.path.join(D, f)
        if os.path.isfile(p) and os.path.splitext(f)[1].lower() in MEDIA_EXT: fl[f] = os.path.getsize(p)
    for cp in sorted(glob.glob(os.path.join(D, "clips", "*.mp4"))): fl["clips~" + os.path.basename(cp)] = os.path.getsize(cp)
    txt = {n: open(os.path.join(D, n), encoding="utf-8").read() for n in READABLE if os.path.exists(os.path.join(D, n))}
    lg = ""
    for lp in sorted(glob.glob(os.path.join(D, "logs", "*.log")), key=os.path.getmtime)[-1:]:
        lg = open(lp, encoding="utf-8", errors="ignore").read()[-4000:]
    logs = {}
    for lp in glob.glob(os.path.join(D, "logs", "*.log")):
        raw = open(lp, encoding="utf-8", errors="ignore").read()
        # The agent command line carries the whole prompt and fills the box. Show a short marker instead, so the real output is visible.
        raw = re.sub(r"(?s)\$ claude -p '.*?'(?= --(?:permission-mode|allowedTools|add-dir|chrome))", "$ claude -p <prompt hidden>", raw)
        logs[os.path.basename(lp)[:-4]] = raw[-6000:]
    jv = jobs.view(slug)   # a worker process runs the steps; it publishes progress through the job row
    rn = dict(jv["progress"] or {})
    if rn.get("started"): rn["elapsed"] = int(__import__("time").time() - rn["started"])
    rn.pop("started", None)
    # rc 5 and 6 are "waiting for you", not failures. The ref is the job id every log line of the run carries (job_id in app.jsonl).
    failure = {"step": rn.get("failed") or "", "error": jv.get("error", ""), "ref": jv.get("id", "")} if (jv.get("status") == "failed" and jv["rc"] not in (0, 5, 6)) else None
    return {"slug": slug, "meta": m, "steps": rows, "next": nxt, "files": fl, "text": txt, "log": lg, "job": {"running": jv["running"], "rc": jv["rc"], "queued": jv["queued"]}, "status_text": jv["status_text"],
            "failure": failure, "gates": C.type_gates(C.item_type(m)), "account": C.account(C.item_type(m)) if C.item_type(m) != "music" else None, "approvals": {g: a for g, a in m.get("approvals", {}).items() if navaan.gate_ok(D, m.get("approvals", {}), g)}, "logs": logs, "run": rn,
            "cameras": list(shots_prep.CAMERAS), "cloud": bool((m.get("cloud") or {}).get("uploaded_at")), "visuals": V.load(D), "images": [os.path.basename(x) for x in V.own_images(D)], "visuals_problems": V.problems(D), "openai_pictures": __import__("media_cfg").load()["image_provider"] == "openai", "prompt_pack": prompt_pack.load(D),
            "try": {**TRY.get(slug, {}), "files": [n for n in ("try_01.png", "try_02.png") if os.path.isfile(os.path.join(D, n))], "v": int(os.path.getmtime(os.path.join(D, "try_01.png"))) if os.path.isfile(os.path.join(D, "try_01.png")) else 0},
            "vertical": {**VERT.get(slug, {}), "done": sorted(int(m.group(1)) for f in (os.listdir(os.path.join(D, "images", "vert")) if os.path.isdir(os.path.join(D, "images", "vert")) else []) for m in [re.match(r"pic_(\d+)\.png$", f)] if m)},
            "poster": {**POST.state(slug), **POSTER.get(slug, {})},
            "narrate": (__import__("narrate_eleven").info(D) if C.item_type(m) == "inspiration" else None),
            "profile": bool(C.profile()), "question": navaan.question_open(slug),
            "thumb_pending": (navaan.meta(slug).get("published", {}).get("thumbnail_pending") or []),
            "needs_you": (open(os.path.join(D, "needs_you.txt"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(D, "needs_you.txt")) else "")}


def start_job(slug, all_steps=False, step=None, redo=False):
    """Queue the run for a worker (jobs.py). False when the item already has a queued or running job."""
    kind = "pipeline" if all_steps else ("redo" if redo else "step")
    return bool(jobs.enqueue(slug, kind, {"all": all_steps, "step": step, "redo": redo}))


CLIENT_LOG = {}  # client address -> times of recent browser error reports
SITE_REACT = {}; SITE_FEEDBACK = {}; SITE_INTEREST = {}; SITE_CLIP = {}   # per address: reactions and messages sent from the public site
GUEST_READ = {}; GUEST_PLAY = {}   # per address: how often a visitor who is not signed in reads the catalogue and asks for songs
GUEST = {"user": "", "user_id": "", "csrf": "", "roles": ["guest"], "permissions": [], "guest": True}   # someone not signed in on a public host
CLIENT_LOG_LOCK = threading.Lock()
def rate_ok(store, ip, n, per=60):
    """At most n requests per `per` seconds per address in this store."""
    t = time.time()
    with CLIENT_LOG_LOCK:
        q = [x for x in store.get(ip, []) if t - x < per]
        if len(q) >= n: store[ip] = q; return False
        q.append(t); store[ip] = q; return True


def client_log_ok(ip, n=30, per=60):
    """At most n browser reports per minute per address, so a broken page cannot flood the log."""
    return rate_ok(CLIENT_LOG, ip, n, per)


PUBLIC_LOG = {}  # client address -> times of recent requests to the public pages (/s and /img)


class H(BaseHTTPRequestHandler):
    server_version = "navaan"
    def log_message(self, fmt, *a): L.event(LOG, "debug", "http_server_message", msg=(fmt % a if a else fmt))
    def send_response(self, code, message=None): self._status = code; super().send_response(code, message)
    def send_header(self, k, v):
        if k.lower() == "content-length" and str(v).isdigit(): self._bytes = int(v)
        super().send_header(k, v)
    def _handle(self, fn):
        """Every request: an id (returned as X-Request-Id), one access record, and any unexpected error logged once with its stack."""
        self._rid = L.new_request_id(self.headers.get("X-Request-Id")); self._status = 0; self._bytes = 0; self._err_logged = False; t0 = time.time()
        with L.ctx(request_id=self._rid, method=self.command, path=self.path.split("?")[0][:200], ip=self._ip()):
            try: fn()
            except (BrokenPipeError, ConnectionResetError) as e: L.ignored(LOG, "the browser closed the connection", e)
            except Exception:
                L.exc(LOG, "request_failed"); self._err_logged = True
                if not self._status:   # once a reply has started, a second status line would corrupt it
                    try: self._send(500, {"error": f"internal error (ref {self._rid})", "request_id": self._rid})
                    except Exception: L.exc(LOG, "request_failed_reply")
            ms = int((time.time() - t0) * 1000)
            pgconn.release_thread()   # this request's thread ends here: give its database connections back now
            routine = self.command == "GET" and (self._status in (200, 206, 304) and ms < 1000 or self._status in (401, 403, 404))  # the page polls; routine polls stay at debug
            L.event(LOG, "debug" if routine else "info", "http_request", status=self._status, ms=ms, bytes=self._bytes)
    def do_GET(self): self._handle(self._do_GET)
    def do_POST(self): self._handle(self._do_POST)
    def _send(self, code, body, ctype="application/json", extra=None):
        b = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text", "application/json")) else ""))
        self.send_header("Content-Length", str(len(b)))
        if "Cache-Control" not in (extra or {}): self.send_header("Cache-Control", "no-store")
        if getattr(self, "_rid", None): self.send_header("X-Request-Id", self._rid)
        for k, v in (extra or {}).items():
            for x in (v if isinstance(v, list) else [v]): self.send_header(k, x)   # a list repeats the header (two Set-Cookie)
        self.end_headers(); self.wfile.write(b)
        if code >= 400 and ctype.startswith("application/json") and not getattr(self, "_err_logged", False):
            err = body.get("error") if isinstance(body, dict) else None
            ei = sys.exc_info() if code >= 500 and sys.exc_info()[0] else None  # inside an except block this is the error that caused the reply
            LOG.log(logging.ERROR if code >= 500 else (logging.DEBUG if code == 401 else logging.INFO), "http_error", exc_info=ei, extra={"fields": {"status": code, "error": str(err)[:300]}})
            if code >= 500: self._err_logged = True
    def _send_ranged(self, data, ctype, cache="public, max-age=86400"):
        """Bytes with Range support (Safari will not play a video without it)."""
        size = len(data); m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range") or ""); hdr = {"Accept-Ranges": "bytes", "Cache-Control": cache}
        if m and (m.group(1) or m.group(2)):
            if m.group(1): start = int(m.group(1)); end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else: start = max(0, size - int(m.group(2))); end = size - 1
            if start > end or start >= size: return self._send(416, b"", ctype, {**hdr, "Content-Range": f"bytes */{size}"})
            return self._send(206, data[start:end + 1], ctype, {**hdr, "Content-Range": f"bytes {start}-{end}/{size}"})
        return self._send(200, data, ctype, hdr)
    def _host_ok(self):
        h = (self.headers.get("Host") or "").split(":")[0]
        return h in ("127.0.0.1", "localhost") or h in _hosts("NAVAAN_PUBLIC_HOST")
    def _surface(self, sess):
        """On a public host nobody has studio powers, not even the owner: the same session there sees the listener app only. Cookies are per host, so signing in on one host does not sign in on the other."""
        if not sess or not self._public_host(): return sess
        roles = [r for r in sess.get("roles", []) if r not in ("owner", "editor")] or ["listener"]
        return {**sess, "roles": roles, "permissions": [x for x in sess.get("permissions", []) if not x.startswith("studio.")], "_studio": auth.can(sess, "studio.access")}   # _studio: this person is the studio's, so the app can link to it
    def _public_host(self): return (self.headers.get("Host") or "").split(":")[0].lower() in LISTENER_HOSTS()
    def _me(self, sess):
        """What the app learns about the person: who, what they may do, and where the other side of the site is. A guest is someone not signed in on a public host."""
        out = {"user": sess.get("user"), "roles": sess.get("roles", []), "permissions": sess.get("permissions", [])}
        sh = os.environ.get("NAVAAN_STUDIO_HOST", "").strip().lower(); lh = (LISTENER_HOSTS() or [""])[0]
        if sess.get("guest"): out["guest"] = True
        if sh and (sess.get("guest") or sess.get("_studio")): out["studio_url"] = f"https://{sh}"   # a guest gets it as the place to sign in, the studio's owner as the way to the studio
        if lh and not self._public_host() and auth.can(sess, "studio.access"): out["public_url"] = f"https://{lh}"
        return out
    def _clip_reply(self, body):
        """A clip of a song to share: 15 or 30 seconds from where they choose; made once and kept. The same for a visitor and a signed in person."""
        try:
            if not rate_ok(SITE_CLIP, self._ip(), 20, 3600): return self._send(429, {"error": "that is a lot of clips, try again later"})
            start, length = int(body.get("start") or 0), int(body.get("length") or 15); slug = str(body.get("slug") or "")
            if not SLUG.match(slug): return self._send(404, {"error": "no such song to clip"})
            CLIP.make(slug, start, length); t = CLIP.token(slug, start, length)
            return self._send(200, {"token": t, "url": f"/c/{t}.mp4", "page": f"{self._base()}/c/{t}"})
        except (TypeError, ValueError) as e: return self._send(400, {"error": str(e) if isinstance(e, ValueError) else "start and length are numbers"})
        except LookupError as e: return self._send(404, {"error": str(e)})
        except RuntimeError: L.exc(LOG, "clip_failed"); return self._send(502, {"error": "cannot make the clip right now"})
    def _site_post(self, p):
        """The two things anyone may send from the public site: a reaction to a song, and a message. Counts and a message: no session, no cookie, nothing about the sender is kept (not even the address). Slowed down per address; a hidden field catches bots."""
        n = int(self.headers.get("Content-Length") or 0)
        if n > 16384: return self._send(413, {"error": "that is too big"})
        try: body = json.loads(self.rfile.read(n) or b"{}")
        except Exception: return self._send(400, {"error": "bad json"})
        if not isinstance(body, dict): return self._send(400, {"error": "bad json"})
        try:
            if p == "/api/site/react":
                if not rate_ok(SITE_REACT, self._ip(), 60, 3600): return self._send(429, {"error": "that is a lot of reactions, try again later"})
                ok = catalog_store.react(str(body.get("slug") or ""), (str(body["reaction"]) if body.get("reaction") is not None else None), body.get("previous") or None)
                return self._send(200, {"ok": True}) if ok else self._send(404, {"error": "no such song"})
            if p == "/api/site/interest":   # "I would like an account": what they like and an optional email
                if not rate_ok(SITE_INTEREST, self._ip(), 5, 3600): return self._send(429, {"error": "you have sent a few already, try again in an hour"})
                if body.get("website"): return self._send(200, {"ok": True})
                catalog_store.add_interest(body.get("moods"), body.get("genres"), body.get("languages"), body.get("email"))
                return self._send(200, {"ok": True})
            if p == "/api/clip": return self._clip_reply(body)
            if not rate_ok(SITE_FEEDBACK, self._ip(), 5, 3600): return self._send(429, {"error": "you have sent a few already, try again in an hour"})
            if body.get("website"): return self._send(200, {"ok": True})   # the hidden field a person never fills: a bot, thanked and ignored
            catalog_store.add_feedback(str(body.get("slug") or ""), str(body.get("message") or ""), body.get("email"))
            return self._send(200, {"ok": True})
        except ValueError as e: return self._send(400, {"error": str(e)})
        except LookupError as e: return self._send(404, {"error": str(e)})
        except RuntimeError: L.exc(LOG, "clip_failed"); return self._send(502, {"error": "cannot make the clip right now"})
    def _guest_get(self, p, sess):
        """What anyone may do without signing in on a public host (the free site): browse, search, read a song's page, play it. Nothing else. True when answered."""
        if p == "/" or p == "/app" or p.startswith("/app/") or p in ("/privacy", "/terms"): return False   # the app itself and the legal pages
        if p == "/api/me": self._send(200, self._me(sess)); return True
        if p.startswith("/api/catalog/"):
            if not rate_ok(GUEST_READ, self._ip(), 240, 60): self._send(429, {"error": "too many requests, try again in a minute"}); return True
            self._listener_get(p, sess); return True   # the catalogue handlers only: published songs with a confirmed licence, no lyrics gate (the songs are free)
        if p == "/api/search":
            if not rate_ok(GUEST_READ, self._ip(), 240, 60): self._send(429, {"error": "too many requests, try again in a minute"}); return True
            q = parse_qs(urlparse(self.path).query)
            try: limit = int((q.get("limit") or ["20"])[0])
            except ValueError: self._send(400, {"error": "limit is a number"}); return True
            self._send(200, {"hits": SEARCH.search((q.get("q") or [""])[0], q.get("kind") or None, min(limit, 50))}); return True
        if p == "/api/play":   # a link that opens the audio for five minutes; many plays from one address are slowed down
            sl = (parse_qs(urlparse(self.path).query).get("slug") or [""])[0]
            if not rate_ok(GUEST_PLAY, self._ip(), 120, 600): self._send(429, {"error": "that is a lot of songs, try again in a few minutes"}); return True
            key = catalog_store.play_key(sl, confirmed_only=True) if SLUG.match(sl) else None
            if not key: self._send(404, {"error": "no such song to play"}); return True
            try: self._send(200, {"url": objstore.par_url(key, 300), "expires_in": 300})
            except Exception: L.exc(LOG, "play_link_failed", item=sl); self._send(502, {"error": "cannot make a play link right now"})
            return True
        self._send(403, {"error": "this is for people with an account", "guest": True}); return True
    def _ip(self):  # real client address; X-Real-IP only when a trusted proxy sits in front (NAVAAN_TRUST_PROXY=1)
        return (self.headers.get("X-Real-IP") or "").strip() if TRUST_PROXY() and self.headers.get("X-Real-IP") else self.client_address[0]
    def _https(self): return TRUST_PROXY() and (self.headers.get("X-Forwarded-Proto") or "").lower() == "https"
    def _acct(self, sess):
        """{user_id, roles} of the signed-in person. With the login off (development) there is one local person."""
        return {"user_id": sess.get("user_id") or (LOCAL_USER if "owner" in sess.get("roles", []) else LOCAL_LISTENER), "roles": sess.get("roles", [])}
    def _listener_get(self, p, sess):
        """Routes a listener may use (they need library.view or account.manage, not the studio). Everything is scoped to the signed-in person."""
        u = self._acct(sess); uid = u["user_id"]
        studio = auth.can(sess, "studio.access")   # the studio sees every published track; a listener only those with a confirmed licence
        if p == "/api/catalog/tracks":
            q = parse_qs(urlparse(self.path).query); one = lambda k: (q.get(k) or [None])[0] or None
            try: lim, off = int(one("limit") or 200), int(one("offset") or 0)
            except ValueError: return self._send(400, {"error": "limit and offset are numbers"})
            return self._send(200, catalog_store.browse(studio, one("album"), one("language"), one("genre"), lim, off))   # a page at a time: ?limit=24&offset=48
        if p == "/api/catalog/filters": return self._send(200, catalog_store.filters(studio))
        if p == "/api/catalog/albums": return self._send(200, catalog_store.public_albums(studio))
        m = re.match(r"^/api/catalog/album/([A-Za-z0-9][A-Za-z0-9_-]{0,80})$", p)
        if m:
            a = next((x for x in catalog_store.public_albums(studio) if x["slug"] == m.group(1)), None)
            return self._send(200, a) if a else self._send(404, {"error": "no such album"})
        m = re.match(r"^/api/catalog/track/([A-Za-z0-9][A-Za-z0-9_-]{0,40})$", p)
        if m:
            v = catalog_store.track_view(m.group(1), studio)
            if not v: return self._send(404, {"error": "no such song"})
            try: v["timed_lines"] = media.timed_lyrics(v["slug"]) if v["timed"] else None
            except Exception: L.exc(LOG, "timed_lyrics_failed", item=v["slug"]); v["timed_lines"] = None   # the page still shows the plain lyrics
            return self._send(200, v)
        if p == "/api/share": return self._send(200, catalog_store.shares(None if auth.can(sess, "studio.settings") else sess.get("user") or "owner"))
        if p == "/api/playlists": return self._send(200, library_store.playlists(uid))
        m = re.match(r"^/api/playlists/([0-9a-f-]{36})$", p)
        if m:
            try: return self._send(200, {**library_store.get_playlist(uid, m.group(1)), "mine": True})
            except LookupError: pass   # expected: not yours; an unlisted or public playlist opens by its link below, a private one is "not found" like any other that is not there
            other = library_store.shared_playlist(m.group(1))
            return self._send(200, {**other, "mine": False}) if other else self._send(404, {"error": "no such playlist"})
        if p == "/api/library": return self._send(200, library_store.library(uid))
        if p == "/api/plans":
            return self._send(200, {"plans": entitlements.plans(), "mine": {"plan": entitlements.plan_for(uid), "entitlements": entitlements.entitlements(uid), "unlimited": "owner" in u["roles"],
                                                                         "usage": {"playlists": len(library_store.playlists(uid))}}})
        if p == "/api/account/export":
            if not auth.can(sess, "account.manage"): return self._send(403, {"error": "this account cannot export"})
            import core_store
            data = {"account": core_store.user_summary(uid), "library": library_store.export(uid), "plan": entitlements.export(uid)}
            return self._send(200, json.dumps(data, ensure_ascii=False, indent=2), "application/json", {"Content-Disposition": 'attachment; filename="navaan-account-export.json"'})
        return self._send(404, {"error": "not found"})
    def _listener_post(self, p, body, sess):
        u = self._acct(sess); uid = u["user_id"]
        try:
            if p == "/api/playlists/create":
                try: return self._send(200, {"id": library_store.create_playlist(u, body.get("name"), body.get("description") or "", body.get("visibility") or "private")})
                except library_store.LimitError as e: d = e.decision; return self._send(403, {"error": str(e), "limit": d.limit, "plan": d.plan, "upgrade": "/app/plans"})
            pid = str(body.get("id") or "")
            if p == "/api/playlists/update": library_store.update_playlist(uid, pid, body.get("name"), body.get("description"), body.get("visibility")); return self._send(200, {"ok": True})
            if p == "/api/playlists/delete": library_store.delete_playlist(uid, pid); return self._send(200, {"ok": True})
            if p == "/api/playlists/add": library_store.add_track(uid, pid, str(body.get("slug") or ""), body.get("after")); return self._send(200, {"ok": True})
            if p == "/api/playlists/remove": library_store.remove_track(uid, pid, str(body.get("slug") or "")); return self._send(200, {"ok": True})
            if p == "/api/playlists/move": library_store.move_track(uid, pid, str(body.get("slug") or ""), body.get("after")); return self._send(200, {"ok": True})
            if p == "/api/library/save": library_store.save(uid, str(body.get("kind") or ""), str(body.get("slug") or ""), bool(body.get("on", True))); return self._send(200, {"ok": True})
            if p == "/api/clip": return self._clip_reply(body)   # a signed in person (the owner on the studio host too) makes a clip the same way a visitor does
            if p in ("/api/share", "/api/share/revoke"):   # a link to a published, licence-confirmed song: the page and preview are public, the owner can stop any link
                who = sess.get("user") or "owner"
                if p.endswith("/revoke"): return self._send(200, {"revoked": catalog_store.revoke_share(str(body.get("token") or ""), who, auth.can(sess, "studio.settings"))})
                sl = str(body.get("slug") or "")
                if not auth.can(sess, "studio.access") and not catalog_store.track_view(sl, False): return self._send(404, {"error": "no such published track"})   # to a listener an unconfirmed song does not exist, so its state is not given away
                tok = catalog_store.create_share(sl, who, int(body.get("start_ms") or 0))
                try: media.ensure_preview(sl)   # cut now, so the first visitor does not wait for it
                except Exception: L.exc(LOG, "preview_failed", item=sl); catalog_store.revoke_share(tok, who, True); return self._send(502, {"error": "could not make the preview from the audio in the bucket"})
                return self._send(200, {"token": tok, "url": f"{self._base()}/s/{tok}"})
            if p == "/api/library/follow": library_store.follow(uid, bool(body.get("on", True))); return self._send(200, {"ok": True})
            if p == "/api/account/delete":
                if "owner" in u["roles"]: return self._send(403, {"error": "the owner account cannot be deleted here"})
                if body.get("confirm") != "delete my account": return self._send(400, {"error": 'type "delete my account" to confirm'})
                import core_store
                who = core_store.user_summary(uid)
                if who:
                    for s in catalog_store.shares(who["username"]): catalog_store.revoke_share(s["token"], who["username"])   # their links stop working
                library_store.erase(uid); entitlements.erase(uid); core_store.delete_user(uid)   # the sessions go with the person
                return self._send(200, {"ok": True, "deleted": True})
        except LookupError as e: return self._send(404, {"error": str(e)})
        except ValueError as e: return self._send(400, {"error": str(e)})
        return self._send(404, {"error": "not found"})
    def _dev_bucket(self, key):
        from urllib.parse import unquote
        path = objstore.local_path(unquote(key))
        if not path or not os.path.isfile(path): return self._send(404, {"error": "not found"})
        data = open(path, "rb").read(); ct = mimetypes.guess_type(path)[0] or "application/octet-stream"; rng = self.headers.get("Range"); hdr = {"Accept-Ranges": "bytes", "Cache-Control": "no-store"}
        m = re.match(r"bytes=(\d*)-(\d*)$", rng or "")
        if m and (m.group(1) or m.group(2)):   # one byte range, as an audio element asks for when seeking
            a = int(m.group(1)) if m.group(1) else max(0, len(data) - int(m.group(2))); b = min(int(m.group(2)) if m.group(1) and m.group(2) else len(data) - 1, len(data) - 1)
            if a > b: return self._send(416, b"", ct, {**hdr, "Content-Range": f"bytes */{len(data)}"})
            return self._send(206, data[a:b + 1], ct, {**hdr, "Content-Range": f"bytes {a}-{b}/{len(data)}"})
        return self._send(200, data, ct, hdr)
    def _base(self):
        h = (LISTENER_HOSTS() or [""])[0] or (_hosts("NAVAAN_PUBLIC_HOST") or [""])[0] or (self.headers.get("Host") or "")   # a shared link is a public link: the public host when there is one
        return f"{'https' if (self._https() or PUBLIC_HOST()) else 'http'}://{h}"
    def _public(self, p):
        """/img/<slug>/<size>.<format> and /s/<token>[/preview.mp3|/play.mp3]. Nothing here needs a session; everything is limited per address."""
        if not rate_ok(PUBLIC_LOG, self._ip(), 240): return self._send(429, {"error": "slow down"}, extra={"Retry-After": "30"})
        try:
            m = re.match(r"^/img/([A-Za-z0-9_-]{1,40})/(\d{2,4})\.(webp|avif|jpg)$", p)
            if m:
                try: r = media.variant(m.group(1), int(m.group(2)), m.group(3))
                except ValueError: r = None   # expected: a size or format that does not exist is simply a 404
                if not r: return self._send(404, {"error": "not found"})
                data, etag, mime = r
                hdr = {"ETag": etag, "Cache-Control": "public, max-age=31536000, immutable"}
                if self.headers.get("If-None-Match") == etag: return self._send(304, b"", mime, hdr)
                return self._send(200, data, mime, hdr)
            m = re.match(r"^/c/([A-Za-z0-9_-]{1,60})(\.mp4)?$", p)
            if m:   # a shared clip: the page, or the video itself (made again when the cache was emptied)
                try: slug, start, length = CLIP.parse(m.group(1))
                except ValueError: return self._send(404, {"error": "not found"})
                try:
                    if m.group(2): return self._send_ranged(open(CLIP.make(slug, start, length), "rb").read(), "video/mp4")
                    CLIP.check(slug, start, length); tv = catalog_store.track_view(slug) or {"title": slug}
                    return self._send(200, share_page.render_clip(slug, tv["title"], m.group(1), self._base()), "text/html")
                except (LookupError, ValueError): return self._send(404, {"error": "not found"})
                except RuntimeError: L.exc(LOG, "clip_failed", item=slug); return self._send(502, {"error": "not available right now"})
            m = re.match(r"^/s/([A-Za-z0-9_-]{8,64})(/preview\.mp3|/play\.mp3)?$", p)
            if m:
                t = catalog_store.open_share(m.group(1), count=not m.group(2))
                if not t: return self._send(404, "<!doctype html><meta charset=utf-8><title>NAVAAN</title><p style=\"font:16px system-ui;padding:2em\">This link is no longer available.</p>", "text/html")
                if m.group(2) == "/play.mp3":   # the whole song: the site is free, so a shared link plays it without a sign in
                    key = catalog_store.play_key(t["slug"], confirmed_only=True)
                    if not key: return self._send(404, {"error": "not found"})
                    return self._send(302, b"", "text/plain", {"Location": objstore.par_url(key, 300)})
                if m.group(2): return self._send(302, b"", "text/plain", {"Location": objstore.par_url(media.ensure_preview(t["slug"]), 300)})
                cv = catalog_store.cover_asset(t["slug"])
                return self._send(200, share_page.render(t, m.group(1), self._base(), (cv or {}).get("dominant_colour"), bool(cv)), "text/html")
        except Exception:
            L.exc(LOG, "public_failed", path=p[:60]); return self._send(502, {"error": "not available right now"})
        return self._send(404, {"error": "not found"})
    def _do_GET(self):
        if not self._host_ok(): return self._send(403, {"error": "bad host"})
        p = self.path.split("?")[0]
        if p in ("/privacy", "/terms"):  # public on purpose: Google asks for these links on the OAuth consent screen
            return self._send(200, open(os.path.join(navaan.HERE, p[1:] + ".html"), encoding="utf-8").read(), "text/html")
        if p.startswith("/dev-bucket/") and objstore.local_dir(): return self._dev_bucket(p[len("/dev-bucket/"):])   # the local stand-in for the bucket (development, browser checks)
        if p.startswith(("/s/", "/img/", "/c/")): return self._public(p)   # shared links and cover pictures: no sign in, published and confirmed tracks only
        if p.startswith(("/app/brand/", "/app/moods/")):   # the logo and the mood pictures are public art: the sign in page shows them before anyone has signed in
            f = web_file(p[5:]) if ".." not in p else None
            if not f: return self._send(404, {"error": "not found"})
            return self._send(200, f[0], f[1], {"Cache-Control": "public, max-age=86400"})
        ck = self.headers.get("Cookie")
        if p == "/auth/state":
            st = auth.state(ck, self.headers.get("Host"), ip=self._ip(), https=self._https()); sec = secrets_status()
            if sec: st["secrets"] = sec if st.get("state") == "authed" else {"status": sec["status"]}  # detail only after sign in
            st["version"] = app_version()   # the version is shown on the sign in page too: it is public (the repository is), and it tells you what is deployed
            if st.get("state") == "authed": st["scheduler"] = scheduler_state(); st["worker"] = worker_state(); st["headless"] = os.environ.get("NAVAAN_HEADLESS", "0") == "1"
            return self._send(200, st)
        sess = self._surface(auth.session(ck))
        if not sess and self._public_host(): sess = GUEST   # the public site needs no sign in
        if not sess:  # not signed in: only the sign in page is served
            if p in ("/", "/legacy") or p == "/app" or p.startswith("/app/"): return self._send(200, open(os.path.join(navaan.HERE, "auth.html"), encoding="utf-8").read(), "text/html")
            return self._send(401, {"error": "sign in", "login": True})
        if sess.get("guest") and self._guest_get(p, sess): return
        if p == "/api/me": return self._send(200, self._me(sess))   # any signed-in person
        if p == "/api/search":   # one search for songs and albums, in Devanagari or Roman letters; a listener may use it (library.view), the studio is not needed
            if not auth.can(sess, "library.view"): return self._send(403, {"error": "this account cannot search"})
            q = parse_qs(urlparse(self.path).query)
            try: limit = int((q.get("limit") or ["20"])[0])
            except ValueError: return self._send(400, {"error": "limit is a number"})
            return self._send(200, {"hits": SEARCH.search((q.get("q") or [""])[0], q.get("kind") or None, limit)})
        csrf = sess.get("csrf") or TOKEN   # one token per session; the process-wide one only when the login is off (development)
        # the app itself (NAV-8) is for every signed-in person, a listener included; what it may call is decided route by route
        if p == "/": return self._send(302, b"", "text/plain", {"Location": "/app/"})   # the new app is the front door (NAV-29); the classic view stays at /legacy for one release
        if p == "/app": return self._send(308, b"", "text/plain", {"Location": "/app/"})
        if p.startswith("/app/"):   # the new app (NAV-8): a built single page app, any route that is not a file gets index.html
            rel = p[5:]
            f = web_file(rel) if rel and "." in os.path.basename(rel) else None
            if f: body, enc = gz(f[0], f[1], self.headers.get("Accept-Encoding")); return self._send(200, body, f[1], {"Cache-Control": f[2], **enc})
            if rel and "." in os.path.basename(rel): return self._send(404, {"error": "not found"})
            idx = web_file("index.html")
            if not idx: return self._send(503, "The new app is not built. In plugins/navaan-studio/web run: npm ci && npm run build", "text/plain")
            return self._send(200, idx[0].replace(b"__TOKEN__", csrf.encode()), "text/html", {"Cache-Control": "no-store"})
        for pre, rd, _wr in LISTENER_ROUTES:
            if p == pre or p.startswith(pre + "/"):
                if not auth.can(sess, rd): return self._send(403, {"error": "this account cannot use that"})
                return self._listener_get(p, sess)
        if p == "/api/play":   # a short-lived link to the audio in the bucket: the audio never passes through this server (FR-016)
            if not auth.can(sess, "library.view"): return self._send(403, {"error": "this account cannot play"})
            sl = (parse_qs(urlparse(self.path).query).get("slug") or [""])[0]
            key = catalog_store.play_key(sl, confirmed_only=not auth.can(sess, "studio.access")) if SLUG.match(sl) else None
            if not key: return self._send(404, {"error": "no such track to play"})
            who = self._acct(sess)
            d = entitlements.can(who, "audio.play")
            if not d: return self._send(403, {"error": d.message(), "plan": d.plan, "upgrade": "/app/plans"})
            try: library_store.record_play(who["user_id"], sl, "direct")
            except Exception: L.exc(LOG, "play_record_failed", item=sl)   # a play that cannot be counted must still play
            try: return self._send(200, {"url": objstore.par_url(key, 300), "expires_in": 300})
            except Exception: L.exc(LOG, "play_link_failed", item=sl); return self._send(502, {"error": "cannot make a play link right now"})
        if not auth.can(sess, "studio.access"): return self._send(403, {"error": "this account cannot use the studio"})   # constitution V: no studio route for a listener
        csrf = sess.get("csrf") or TOKEN   # one token per session; the process-wide one only when the login is off (development)
        try:
            if p == "/legacy":   # the classic view, kept for one release as the way back (NAV-29)
                page = open(os.path.join(navaan.HERE, "ui.html"), encoding="utf-8").read().replace("__TOKEN__", csrf)
                return self._send(200, page, "text/html")
            if p == "/api/cloud": return self._send(200, cloud_view("refresh=1" in self.path))
            if p == "/api/alerts":
                try: return self._send(200, {"alerts": settings_api.alerts()})
                except Exception as e: return self._send(500, {"error": str(e)[:300]})
            if p == "/api/settings":
                try: return self._send(200, settings_api.status("refresh=1" in self.path))
                except Exception as e: return self._send(500, {"error": str(e)[:300]})
            if p == "/api/replies":
                import comment_reply as CR
                pf = (parse_qs(urlparse(self.path).query).get("platform") or [""])[0]
                if pf not in CR.PLATFORMS: return self._send(400, {"error": "bad platform"})
                conn = CR.connect()
                try: return self._send(200, {"items": CR.waiting(conn, pf)})
                finally: conn.close()
            if p == "/api/analytics":
                q = parse_qs(urlparse(self.path).query); acc = (q.get("account") or ["all"])[0]
                if not analytics_api.ACCOUNT_OK.match(acc): return self._send(400, {"error": "bad account"})
                return self._send(200, analytics_api.overview(acc, (q.get("days") or ["30"])[0]))
            if p == "/api/analytics/youtube":
                q = parse_qs(urlparse(self.path).query); acc = (q.get("account") or ["all"])[0]
                if not analytics_api.ACCOUNT_OK.match(acc): return self._send(400, {"error": "bad account"})
                return self._send(200, analytics_api.yt_overview(acc, (q.get("days") or ["30"])[0]))
            if p == "/api/analytics/auto": return self._send(200, analytics_auto.settings())
            if p == "/api/besttime":
                q = parse_qs(urlparse(self.path).query); lab = (q.get("type") or ["music"])[0]
                if not analytics_api.ACCOUNT_OK.match(lab): return self._send(400, {"error": "bad type"})
                if (q.get("platform") or ["instagram"])[0] == "youtube": return self._send(200, besttime.for_label_youtube(lab))
                return self._send(200, besttime.for_label(lab))
            if p == "/api/schedule/suggest":
                sl = (parse_qs(urlparse(self.path).query).get("slug") or [""])[0]
                if not SLUG.match(sl): return self._send(400, {"error": "bad slug"})
                try: return self._send(200, {"suggestion": PS.suggest(sl)})
                except Exception as e: L.soft(LOG, "schedule_suggest_failed", item=sl); return self._send(200, {"suggestion": None, "error": str(e)[:200]})
            if p == "/api/schedule/options":
                ty = (parse_qs(urlparse(self.path).query).get("type") or ["music"])[0]; out = []
                for s in songs():
                    m = navaan.meta(s)
                    if C.item_type(m) != ty or navaan.ig_done(m) or m.get("cleanup"): continue
                    D = C.song_dir(s); ap = m.get("approvals", {}); tp = os.path.join(D, "title.txt")
                    try: _, nx = navaan.plan(s)
                    except SystemExit as _e: L.ignored(LOG, "_do_GET: SystemExit (optional or expected)", _e); continue
                    out.append({"slug": s, "title": open(tp, encoding="utf-8").read().strip() if os.path.exists(tp) else "", "next": nx.get("step") or "done", "public": navaan.public_done(m),
                                "missing_gates": [g for g in ("go_public", "instagram_caption", "publish_instagram") if not navaan.gate_ok(D, ap, g)],
                                "schedule": PS.status_text(m)})
                return self._send(200, {"songs": out})
            if p == "/api/analytics/song":
                q = parse_qs(urlparse(self.path).query); sl = (q.get("slug") or [""])[0]
                if not SLUG.match(sl): return self._send(400, {"error": "bad slug"})
                return self._send(200, analytics_api.song_view(sl))
            if p == "/api/analytics/by-song": return self._send(200, analytics_api.by_song())
            if p == "/api/songs":
                try: art = catalog_store.cover_art()   # published songs with a cover in the bucket: the list asks /img for it and paints the dominant colour first
                except Exception: L.exc(LOG, "cover_art_failed"); art = {}   # the list still works, with letter tiles
                rows = [song_row(s) for s in songs()]
                for r in rows: r["art"] = {"colour": art[r["slug"]]} if r["slug"] in art else None
                return self._send(200, rows)
            if p == "/api/schedule":   # every scheduled publish, for the Schedule screen
                out = []
                for sl in songs():
                    tp = os.path.join(C.song_dir(sl), "title.txt")
                    out += PS.entries(sl, navaan.meta(sl), open(tp, encoding="utf-8").read().strip() if os.path.exists(tp) else "")
                return self._send(200, sorted(out, key=lambda e: e["at"]))
            if p == "/api/albums": return self._send(200, catalog_store.albums())
            if p == "/api/albums/cover":   # the cover's prompt, cost and whether it exists (no spend)
                al = (parse_qs(urlparse(self.path).query).get("album") or [""])[0]
                try: return self._send(200, {**ALB.cover_state(al), **ALBUM_COVER.get(al, {})})
                except LookupError as e: return self._send(404, {"error": str(e)})
                except ValueError as e: return self._send(400, {"error": str(e)})
            m = re.match(r"^/api/albums/cover/([A-Za-z0-9_-]{1,80})\.png$", p)
            if m:   # the made cover picture, for the studio
                f = os.path.join(os.path.dirname(C.songs_root()), "albums", m.group(1), "cover_1x1.png")
                if not os.path.isfile(f): return self._send(404, {"error": "no cover yet"})
                return self._send(200, open(f, "rb").read(), "image/png", {"Cache-Control": "private, no-cache"})
            if p == "/api/site/reactions":   # how the public site's visitors reacted, per song
                q = parse_qs(urlparse(self.path).query)
                try: d = int((q.get("days") or ["0"])[0]) or None
                except ValueError: return self._send(400, {"error": "days is a number"})
                return self._send(200, catalog_store.reactions(d))
            if p == "/api/site/interest": return self._send(200, catalog_store.interest_summary())   # who asked for an account and what they like
            if p == "/api/site/feedback":   # the messages visitors sent
                q = parse_qs(urlparse(self.path).query)
                try: lim, off = int((q.get("limit") or ["50"])[0]), int((q.get("offset") or ["0"])[0])
                except ValueError: return self._send(400, {"error": "limit and offset are numbers"})
                return self._send(200, catalog_store.feedback_list(lim, off, (q.get("unhandled") or ["0"])[0] == "1"))
            if p == "/api/tracks": return self._send(200, catalog_store.tracks())   # the audit table: origin, plan tier, licence status per track
            m = re.match(r"^/api/song/([^/]+)$", p)
            if m and SLUG.match(m.group(1)): return self._send(200, detail(m.group(1)))
            m = re.match(r"^/media/([^/]+)/([^/]+)$", p)
            if m and SLUG.match(m.group(1)):
                q = re.search(r"[?&]w=(\d+)", self.path)
                return self._media(m.group(1), m.group(2), int(q.group(1)) if q else 0)
        except SystemExit as e: return self._send(404, {"error": str(e)})
        self._send(404, {"error": "not found"})
    def _thumb(self, f, w):
        """A small JPEG of a picture for list views (covers are 1-3 MB PNGs). Cached under ~/.cache/navaan/thumbs, keyed by file, mtime and width; any failure serves the original."""
        if w not in THUMB_W or os.path.splitext(f)[1].lower() not in (".png", ".jpg", ".jpeg", ".webp"): return f
        try:
            st = os.stat(f); key = hashlib.sha1(f"{f}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()[:20]
            out = os.path.join(THUMB_DIR, f"{key}-{w}.jpg")
            if os.path.isfile(out): return out
            os.makedirs(THUMB_DIR, exist_ok=True); tmp = f"{out}.{threading.get_ident()}.tmp.jpg"
            r = subprocess.run([C.tool("ffmpeg"), "-v", "error", "-y", "-i", f, "-vf", f"scale='min({w},iw)':-2", "-frames:v", "1", "-q:v", "4", tmp], capture_output=True, timeout=30)
            if r.returncode != 0 or not os.path.isfile(tmp): return f
            os.replace(tmp, out); return out
        except (Exception, SystemExit): L.ignored(LOG, "thumbnail failed, the original is served", sys.exc_info()[1]); return f   # any failure (no ffmpeg, a broken picture) serves the original
    def _client_log(self, body):
        """Errors the browser caught or could not catch (spec FR-035). Capped, rate limited and scrubbed by navaan_log."""
        if not client_log_ok(self._ip()): return self._send(429, {"error": "too many reports"})
        f = {k: str(body.get(k, ""))[:n] for k, n in (("message", 500), ("stack", 3000), ("page", 200), ("src", 200), ("line", 10), ("where", 80), ("path", 200), ("status", 10), ("ui_request_id", 40), ("what", 80))}
        sess = auth.session(self.headers.get("Cookie")); f["user"] = (sess or {}).get("user", "") if isinstance(sess, dict) else ""
        f["kind"] = str(body.get("kind", "error"))[:20]
        L.event(L.get("client"), "error" if f["kind"] in ("error", "rejection", "api_network", "api_json") else "warning", "client_" + f["kind"], **{k: v for k, v in f.items() if v})
        return self._send(200, {"ok": True})
    def _media(self, slug, name, w=0):
        D = C.song_dir(slug); f = os.path.join(D, "clips", os.path.basename(name[6:])) if name.startswith("clips~") else (os.path.join(D, "images", os.path.basename(name[7:])) if name.startswith("images~") else os.path.join(D, os.path.basename(name)))
        if os.path.splitext(f)[1].lower() in MEDIA_EXT and not os.path.isfile(f) and os.path.splitext(f)[1].lower() not in storage.VIDEO_EXT: storage.fetch_missing(f)  # cleaned after archiving: bring the picture or audio back from the bucket
        if os.path.splitext(f)[1].lower() not in MEDIA_EXT or not os.path.isfile(f): return self._send(404, {"error": "no file"})
        f = self._thumb(f, w) if w else f
        st = os.stat(f); size = st.st_size; ct = mimetypes.guess_type(f)[0] or "application/octet-stream"
        etag = f'"{size:x}-{int(st.st_mtime):x}"'  # revalidate every time (a regenerated cover shows at once), but an unchanged one costs a 304, not the file
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304); self.send_header("ETag", etag); self.send_header("Cache-Control", "private, no-cache"); self.end_headers(); return
        rng = self.headers.get("Range"); start, end = 0, size - 1; code = 200
        if rng and (mm := re.match(r"bytes=(\d*)-(\d*)", rng)):
            if mm.group(1): start = int(mm.group(1))
            if mm.group(2): end = min(int(mm.group(2)), size - 1)
            if not mm.group(1) and mm.group(2): start = max(0, size - int(mm.group(2))); end = size - 1
            code = 206
        self.send_response(code); self.send_header("Content-Type", ct); self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", etag); self.send_header("Cache-Control", "private, no-cache")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206: self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with open(f, "rb") as fh:
                fh.seek(start); left = end - start + 1
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk: break
                    self.wfile.write(chunk); left -= len(chunk)
        except (BrokenPipeError, ConnectionResetError) as _e: L.ignored(LOG, "_media: BrokenPipeError/ConnectionResetError (optional or expected)", _e); pass
    def _do_POST(self):
        if not self._host_ok(): return self._send(403, {"error": "forbidden"})
        org = self.headers.get("Origin")
        if org and org != ("https://" if self._https() else "http://") + (self.headers.get("Host") or ""): return self._send(403, {"error": "forbidden origin"})
        ck = self.headers.get("Cookie")
        if self.path in ("/api/site/react", "/api/site/feedback", "/api/site/interest", "/api/clip") and self._public_host(): return self._site_post(self.path)
        if self.path.startswith("/auth/"):
            sec = secrets_status()
            if self.path.startswith("/auth/setup") and sec and sec["status"] != "ok": return self._send(503, {"error": "Secrets are waiting for Vault. The login is restored from Vault once it is unsealed; try again then."})
            try: b = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except Exception: return self._send(400, {"error": "bad json"})
            code, obj, cookies = auth.handle_post(self.path.split("?")[0], b, ck, self.headers.get("Host"), ip=self._ip(), https=self._https())
            return self._send(code, obj, extra={"Set-Cookie": list(cookies)} if cookies else None)
        sess = self._surface(auth.session(ck))
        if not sess: return self._send(401, {"error": "sign in", "login": True})
        need = next((wr for pre, _rd, wr in LISTENER_ROUTES if wr and (self.path == pre or self.path.startswith(pre + "/"))), None)   # routes a listener may change things through
        if not need and not auth.can(sess, "studio.access"): return self._send(403, {"error": "this account cannot use the studio"})
        if need and not auth.can(sess, need): return self._send(403, {"error": "this account cannot do that"})
        if not hmac.compare_digest((self.headers.get("X-Navaan-Token") or "").encode(), (sess.get("csrf") or TOKEN).encode()): return self._send(403, {"error": "forbidden"})   # this session's token
        try: body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except Exception: return self._send(400, {"error": "bad json"})
        slug = body.get("slug", ""); p = self.path
        if need: return self._listener_post(p, body, sess)
        try:
            if p == "/api/billing/entitlement":   # the owner changes what a plan includes: a data change, no screen or release (SC-008)
                if not auth.can(sess, "studio.settings"): return self._send(403, {"error": "only the owner changes plans"})
                try:
                    if not entitlements.set_entitlement(str(body.get("plan") or ""), str(body.get("feature") or ""), bool(body.get("enabled", True)), body.get("limit")): return self._send(404, {"error": "no such plan"})
                except (ValueError, TypeError) as e: return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True})
            if p == "/api/client-log": return self._client_log(body)
            if p == "/api/analytics/link":
                try: analytics_api.link_post(str(body.get("media_id") or ""), str(body.get("slug") or "")); return self._send(200, {"ok": True})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/link-video":
                try: analytics_api.link_video(str(body.get("video_id") or ""), str(body.get("slug") or "")); return self._send(200, {"ok": True})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/analyze":
                try: return self._send(200, {"results": analytics_api.analyze_now(str(body.get("account") or "all"), platform=str(body.get("platform") or "instagram"))})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/ask":
                try: return self._send(200, {"started": analytics_api.start_ask(str(body.get("account") or "all"), str(body.get("platform") or "instagram"))})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/implement":
                try: return self._send(200, analytics_api.implement_rec(str(body.get("id") or "")))
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/schedule/set":
                if not SLUG.match(slug): return self._send(400, {"error": "bad slug"})
                try: return self._send(200, {"ok": True, "schedule": PS.set_schedule(slug, str(body.get("instagram_at") or ""), body.get("youtube_at") or None)})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/auto":
                try: return self._send(200, analytics_auto.set_settings(body.get("enabled"), body.get("every_days", 7), body.get("hour", 9), body.get("ask")))
                except (ValueError, TypeError) as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/auto/run":
                return self._send(200, {"started": True}) if analytics_auto.run_async() else self._send(409, {"error": "a refresh is already running"})
            if p == "/api/schedule/accept":
                if not SLUG.match(slug): return self._send(400, {"error": "bad slug"})
                try: return self._send(200, {"ok": True, "schedule": PS.accept(slug)})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/schedule/clear":
                if not SLUG.match(slug): return self._send(400, {"error": "bad slug"})
                PS.clear(slug); return self._send(200, {"ok": True})
            if p.startswith("/api/replies/"):
                import comment_reply as CR
                act = p.rsplit("/", 1)[1]; pf = str(body.get("platform") or ""); cid = str(body.get("comment_id") or "")
                if act not in ("draft", "edit", "skip", "send"): return self._send(404, {"error": "unknown action"})
                conn = None
                try:
                    conn = CR.connect()   # Claude only drafts. Posting happens only here, when the person presses Approve and send for one comment.
                    if act == "draft": r = CR.draft(conn, pf, cid)
                    elif act == "edit": r = CR.edit(conn, pf, cid, str(body.get("text") or ""))
                    elif act == "skip": r = CR.skip(conn, pf, cid)
                    else: r = CR.send(conn, pf, cid, str(body["text"]) if "text" in body else None)
                    return self._send(200, {"ok": True, "reply": r})
                except ValueError as e: return self._send(400, {"error": str(e)})
                except Exception as e: return self._send(502, {"error": str(e)[:300]})
                finally:
                    if conn: conn.close()
            if p == "/api/analytics/rec":
                try: analytics_api.set_rec_status(str(body.get("id") or ""), str(body.get("status") or ""), body.get("reason")); return self._send(200, {"ok": True})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/collect":
                try: return self._send(200, {"started": analytics_api.start_collect(str(body.get("account") or "all"), str(body.get("platform") or "instagram"))})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p.startswith("/api/settings/"):
                act = p.rsplit("/", 1)[1]; ct = str(body.get("type") or "music")
                try:
                    if act == "ig_refresh": return self._send(200, settings_api.ig_refresh(ct, str(body.get("kind") or "login")))
                    if act == "ig_save": return self._send(200, settings_api.ig_save(ct, str(body.get("kind") or "login"), str(body.get("token") or "")))
                    if act == "yt_signin": return self._send(200, {"started": settings_api.yt_signin(ct)})
                    if act == "claude_save": return self._send(200, settings_api.claude_save(str(body.get("token") or "")))
                    if act == "gates_save": return self._send(200, settings_api.gates_save(body.get("gates") or {}))
                    if act == "media_save": return self._send(200, settings_api.media_save(body.get("settings") or {}))
                    if act == "media_key": return self._send(200, settings_api.media_key_save(str(body.get("provider") or ""), str(body.get("token") or "")))
                    if act == "yt_oauth_start": return self._send(200, settings_api.yt_oauth_start(ct, str(body.get("which") or "publish")))
                    if act == "yt_oauth_finish": return self._send(200, settings_api.yt_oauth_finish(ct, str(body.get("which") or "publish"), str(body.get("url") or "")))
                    if act == "yt_save": return self._send(200, settings_api.yt_save(ct, str(body.get("which") or "publish"), str(body.get("content") or "")))
                    if act == "yt_secret": return self._send(200, settings_api.save_secret(str(body.get("content") or "")))
                    if act == "account": return self._send(200, settings_api.add_account(ct, body.get("handle"), body.get("channel")))
                    return self._send(404, {"error": "unknown settings action"})
                except ValueError as e: return self._send(400, {"error": str(e)})
                except Exception as e: return self._send(500, {"error": str(e)[:300]})
            if p == "/api/cloud/link":
                key = str(body.get("key", "")); pre = (C.cfg("storage.cloud_prefix", "").strip("/") + "/") if C.cfg("storage.cloud_prefix", "") else ""
                if not key.startswith(pre) or ".." in key: return self._send(400, {"error": "not a song object"})
                try: return self._send(200, {"url": storage.signed_url(C.cfg("storage.cloud_provider"), C.cfg("storage.cloud_bucket"), C.cfg("storage.cloud_region", ""), key)})
                except RuntimeError as e: return self._send(500, {"error": str(e)})
            if p == "/api/album":
                name = str(body.get("name", "")).strip()[:80]; sl = [x for x in body.get("slugs", []) if isinstance(x, str) and SLUG.match(x)]
                for x in sl:
                    navaan.edit_meta(x, lambda m: m.__setitem__("album", name) if name else m.pop("album", None))
                    catalog_store.sync_item(x)   # the label puts the song into the catalog album of that name; the catalog's album is the one listeners see
                return self._send(200, {"ok": True, "count": len(sl)})
            if p == "/api/site/feedback/handle":
                fid = str(body.get("id") or "")
                if not re.match(r"^[0-9a-f-]{36}$", fid): return self._send(400, {"error": "bad id"})
                return self._send(200, {"ok": catalog_store.feedback_handled(fid, bool(body.get("handled", True)))})
            if p == "/api/catalog/license":   # the owner decides what may be offered behind a plan; an editor cannot
                if not auth.can(sess, "studio.settings"): return self._send(403, {"error": "only the owner decides licences"})
                try: ok = catalog_store.set_license(str(body.get("slug") or ""), body.get("status"), sess.get("user") or "owner", body.get("note"), body.get("plan"))
                except ValueError as e: return self._send(400, {"error": str(e)})
                if not ok: return self._send(404, {"error": "no such track"})
                auth._audit("track_license", user=sess.get("user"), ip=self._ip(), slug=body.get("slug"), status=body.get("status"), plan=body.get("plan"))
                return self._send(200, {"ok": True})
            if p == "/api/albums/suggest":   # five names for an album from the chosen songs (a few cents of OpenAI chat)
                try: return self._send(200, {"names": ALB.suggest_names([str(x) for x in body.get("tracks") or [] if isinstance(x, str) and SLUG.match(x)])})
                except ValueError as e: return self._send(400, {"error": str(e)})
                except (RuntimeError, SystemExit) as e: return self._send(502, {"error": str(e)[:300]})
            if p == "/api/albums/cover":
                al = str(body.get("album") or "")
                if ALBUM_COVER.get(al, {}).get("running"): return self._send(409, {"error": "A cover is already being made."})
                try:
                    ALB._album(al)
                    if body.get("picture"):   # your own picture as the art: free
                        ALB.use_picture(al, base64.b64decode(str(body["picture"]), validate=True)); return self._send(200, {"ok": True})
                    if body.get("only_text"):   # redraw the title over the art already made: free
                        if body.get("style") in POST.STYLES:
                            with open(os.path.join(ALB.album_dir(al), "cover_style.txt"), "w") as f: f.write(body["style"])
                        ALB.typeset(al); return self._send(200, {"ok": True})
                    prompt = str(body.get("prompt") or ""); style = body.get("style"); ALB.IO.check_cap(ALB.media_cfg.load()["image_quality"], None, ALB.SIZE)
                except LookupError as e: return self._send(404, {"error": str(e)})
                except (ValueError, OSError) as e: L.ignored(LOG, "album cover refused (shown to the owner)", e); return self._send(400, {"error": str(e)[:200]})
                ALBUM_COVER[al] = {"running": True, "error": ""}
                def aw():
                    err = ""
                    try: ALB.generate_cover(al, prompt, style)
                    except (ValueError, RuntimeError) as e: L.ignored(LOG, "aw: refused or failed (shown to the owner)", e); err = str(e)[:300]
                    except Exception as e: L.soft(LOG, "aw_error"); err = str(e)[:300]
                    ALBUM_COVER[al] = {"running": False, "error": err}
                threading.Thread(target=aw, daemon=True).start()
                return self._send(200, {"ok": True})
            if p in ("/api/albums/save", "/api/albums/reorder", "/api/albums/delete"):   # the owner's album editor API (the screens come in NAV-16)
                try:
                    if p.endswith("/save"): return self._send(200, {"slug": catalog_store.save_album(str(body.get("slug") or ""), body.get("title"), body.get("kind") or "album", body.get("status") or "draft", body.get("release_date"), body.get("description") or "")})
                    if p.endswith("/reorder"): return self._send(200, {"tracks": catalog_store.reorder(str(body.get("album") or ""), [str(x) for x in body.get("tracks") or []])})
                    return self._send(200, {"deleted": catalog_store.delete_album(str(body.get("slug") or ""))})
                except ValueError as e: return self._send(400, {"error": str(e)})
                except LookupError as e: return self._send(404, {"error": str(e)})
            if p == "/api/new":
                if slug and not SLUG.match(slug): return self._send(400, {"error": "slug: letters, digits, dash, underscore"})
                import new_song
                sl = new_song.create(slug or None, body.get("type") or "music", str(body.get("idea") or ""))
                return self._send(200, {"rc": 0, "slug": sl})
            if p == "/api/import":
                import suno_import
                if slug and not SLUG.match(slug): return self._send(400, {"error": "bad slug"})
                au = body.get("audio") if isinstance(body.get("audio"), dict) else None
                try:
                    if au: suno_import.check_upload(au.get("name"), str(au.get("data") or ""))
                    sl = suno_import.init(body.get("url", ""), slug or None, allow_blank=bool(au))
                    if au: suno_import.save_upload(sl, au.get("name"), str(au.get("data") or ""))
                except ValueError as e: return self._send(400, {"error": str(e)})
                except SystemExit as e: return self._send(400, {"error": str(e).replace("navaan: ", "")})
                return self._send(200, {"slug": sl, "started": start_job(sl, True)})
            if p == "/api/suno/audio":
                import suno_import
                if not SLUG.match(slug) or not os.path.isdir(C.song_dir(slug)): return self._send(404, {"error": "no such song"})
                if jobs.active(slug): return self._send(409, {"error": "a run is in progress for this song"})
                try: suno_import.save_upload(slug, body.get("name"), str(body.get("data") or ""))
                except ValueError as e: return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True, "started": start_job(slug, True)})
            if not SLUG.match(slug): return self._send(400, {"error": "bad slug"})
            if p == "/api/approve":
                navaan.set_gate(slug, body["gate"], True, f"ui:{sess.get('user') or 'owner'}"); started = False
                m = navaan.meta(slug); sid = m.get("redo_pending")
                if sid and body["gate"] == "credits":
                    navaan.edit_meta(slug, lambda d: d.pop("redo_pending", None)); started = start_job(slug, False, sid)
                return self._send(200, {"ok": True, "started": started})
            if p == "/api/answer":
                qid = navaan.set_answer(slug, body.get("choice"), body.get("text"), "ui")
                return self._send(200, {"ok": True, "id": qid, "started": start_job(slug, True)})
            if p == "/api/request-changes":
                try: navaan.request_changes(slug, body.get("gate"), body.get("note"), f"ui:{sess.get('user') or 'owner'}")
                except SystemExit as e: return self._send(400, {"error": str(e)})
                return self._send(200, {"ok": True})
            if p == "/api/revoke": navaan.set_gate(slug, body["gate"], False, f"ui:{sess.get('user') or 'owner'}"); return self._send(200, {"ok": True})   # the history says who took the approval back
            if p == "/api/redo":
                if jobs.active(slug): return self._send(409, {"error": "a run is in progress for this song"})
                return self._send(200, {"started": start_job(slug, False, body.get("step"), redo=True)})
            if p == "/api/restart":   # redo this step and every step after it through the render, then run until the credits gate
                if jobs.active(slug): return self._send(409, {"error": "a run is in progress for this song. Press Stop first."})
                try: navaan.redo_from(slug, body.get("step"))
                except SystemExit as e: return self._send(400, {"error": str(e)})
                return self._send(200, {"started": start_job(slug, True)})
            if p == "/api/run": return self._send(200, {"started": start_job(slug, bool(body.get("all")))})
            if p == "/api/stop": return self._send(200, {"stopped": jobs.request_cancel(slug)})
            if p == "/api/mood":   # the song's mood picks the background of the full screen player; empty clears it
                mood = str(body.get("mood") or "").strip().lower()
                if mood and mood not in catalog_store.MOODS: return self._send(400, {"error": "mood must be one of: " + ", ".join(catalog_store.MOODS)})
                def setm(m):
                    if mood: m["mood"] = mood
                    else: m.pop("mood", None)
                    navaan.log_hist(m, f"mood {mood or 'cleared'} (via ui)")
                navaan.edit_meta(slug, setm)
                try: catalog_store.sync_item(slug)   # a published song shows it at once; an unpublished one takes it when it is published
                except Exception: L.exc(LOG, "mood_sync_failed", item=slug)
                return self._send(200, {"ok": True, "mood": mood})
            if p == "/api/narration/eleven":   # narrate the quote with ElevenLabs as a step of this item: on or off, and which voice (the spend is approved at the credits gate)
                import narration, narrate_eleven, media_cfg
                if navaan.meta(slug).get("type") != "inspiration": return self._send(400, {"error": "narration is for inspiration shorts"})
                D = C.song_dir(slug); on = bool(body.get("on")); voice = str(body.get("voice") or "")
                if on and voice not in media_cfg.VOICES: return self._send(400, {"error": "voice must be one of: " + ", ".join(media_cfg.VOICES)})
                narration.set_options(D, {"narrate": "eleven", "voice": voice} if on else {"narrate": "none"})
                note = f"narration by ElevenLabs {'on, voice ' + voice if on else 'off'} (via ui)"
                navaan.edit_meta(slug, lambda m: navaan.log_hist(m, note))
                return self._send(200, {"ok": True, **narrate_eleven.info(D)})
            if p in ("/api/narration/upload", "/api/narration/remove"):  # a ready made narration (audio plus its timed .srt) for an inspiration short
                import narration
                if navaan.meta(slug).get("type") != "inspiration": return self._send(400, {"error": "narration is for inspiration shorts"})
                D = C.song_dir(slug)
                try:
                    if p.endswith("remove"): narration.remove(D); r = {}
                    else: r = narration.save(D, body.get("audio_name"), str(body.get("audio") or ""), str(body.get("srt") or ""), str(body.get("text") or ""))
                    note = "narration " + ("removed" if p.endswith("remove") else f"attached via ui: {r.get('audio')}, {r.get('cues')} lines" + (", timing pending" if r.get("timing") else ""))
                    navaan.edit_meta(slug, lambda m: navaan.log_hist(m, note))
                    return self._send(200, {"ok": True, **r})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/poster/generate":
                if POSTER.get(slug, {}).get("running"): return self._send(409, {"error": "A poster is already being made."})
                if body.get("picture"):   # your own picture as the art: free
                    try: POST.use_picture(slug, base64.b64decode(str(body["picture"]), validate=True)); return self._send(200, {"ok": True})
                    except ValueError as e: return self._send(400, {"error": str(e)})
                if body.get("only_text"):   # redraw title and artist over the art already made: free
                    try:
                        if body.get("style") in POST.STYLES:
                            with open(os.path.join(C.song_dir(slug), "poster_style.txt"), "w") as f: f.write(body["style"])
                        POST.typeset(slug); return self._send(200, {"ok": True})
                    except (OSError, ValueError) as e: L.ignored(LOG, "poster_typeset: no art yet (optional or expected)", e); return self._send(400, {"error": "Make the art first."})
                prompt = str(body.get("prompt") or ""); style = body.get("style")
                try: POST.IO.check_cap(POST.media_cfg.load()["image_quality"], None, POST.SIZE)
                except ValueError as e: return self._send(400, {"error": str(e)})
                POSTER[slug] = {"running": True, "error": ""}
                def pw():
                    err = ""
                    try: POST.generate(slug, prompt, style); navaan.edit_meta(slug, lambda m: navaan.log_hist(m, "poster made via ui"))
                    except (ValueError, RuntimeError) as e: L.ignored(LOG, "pw: refused or failed (shown to the owner)", e); err = str(e)[:300]
                    except Exception as e: L.soft(LOG, "pw_error"); err = str(e)[:300]
                    POSTER[slug] = {"running": False, "error": err}
                threading.Thread(target=pw, daemon=True).start()
                return self._send(200, {"ok": True})
            if p.startswith("/api/visuals/"):
                act = p.rsplit("/", 1)[1]; D = C.song_dir(slug)
                try:
                    if act == "upload": return self._send(200, {"path": V.add_image(D, body.get("name"), str(body.get("data") or ""))})
                    if act == "remove": V.remove_image(D, body.get("path")); return self._send(200, {"ok": True})
                    if act == "prompts":
                        try: return self._send(200, {"ok": True, "pack": prompt_pack.make(slug, body.get("count") or None)})
                        except (RuntimeError, SystemExit) as e: return self._send(400, {"error": str(e)})
                    if act == "try":
                        import media_cfg, song_images_openai as SIO
                        if media_cfg.load()["image_provider"] != "openai": return self._send(400, {"error": "Set Background pictures to OpenAI in Settings first."})
                        if not prompt_pack.load(D): return self._send(400, {"error": "Write the prompts first."})
                        if TRY.get(slug, {}).get("running"): return self._send(409, {"error": "The test is already running."})
                        TRY[slug] = {"running": True, "error": ""}
                        def tw():
                            err = ""
                            try: SIO.main([slug, "--try"])
                            except SystemExit as e: L.ignored(LOG, "tw: SystemExit (optional or expected)", e); err = "" if e.code in (0, None) else str(e.code)[:300]
                            except Exception as e: L.soft(LOG, "tw_error"); err = str(e)[:300]
                            TRY[slug] = {"running": False, "error": err}
                        threading.Thread(target=tw, daemon=True).start()
                        return self._send(200, {"ok": True})
                    if act == "vertical":
                        import media_cfg, song_images_openai as SIO
                        if media_cfg.load()["image_provider"] != "openai": return self._send(400, {"error": "Set Background pictures to OpenAI in Settings first."})
                        pics = [int(x) for x in (body.get("pics") or []) if str(x).isdigit()]
                        if not pics: return self._send(400, {"error": "Pick a picture."})
                        if VERT.get(slug, {}).get("running"): return self._send(409, {"error": "A vertical picture is already being made."})
                        VERT[slug] = {"running": True, "error": ""}
                        def vw():
                            err = ""
                            try: SIO.main([slug, "--vertical", ",".join(str(x) for x in pics)])
                            except SystemExit as e: L.ignored(LOG, "vw: SystemExit (optional or expected)", e); err = "" if e.code in (0, None) else str(e.code)[:300]
                            except Exception as e: L.soft(LOG, "vw_error"); err = str(e)[:300]
                            VERT[slug] = {"running": False, "error": err}
                        threading.Thread(target=vw, daemon=True).start()
                        return self._send(200, {"ok": True})
                    if act == "save":
                        import media_cfg; v = V.save(D, str(body.get("mode") or ""), body.get("layout"), body.get("camera", ""), body.get("scene", ""), pictures_later=media_cfg.load()["image_provider"] == "openai")
                        note = f"visuals chosen via ui: {v['mode']}{' ' + v.get('layout', '') if v['mode'] == 'own' else ''}"
                        navaan.edit_meta(slug, lambda m: navaan.log_hist(m, note))
                        return self._send(200, {"ok": True, "visuals": v})
                    return self._send(404, {"error": "unknown visuals action"})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/shots/save":
                D = C.song_dir(slug); imgs = set(V.own_images(D)); out = []
                try:
                    dur = float((C.load_json(os.path.join(D, "shots.json"), default={}) or {}).get("duration") or 0)
                    for i, s in enumerate(body.get("shots") or []):
                        st, en = float(s["start"]), float(s["end"])
                        if s.get("image") not in imgs: raise ValueError(f"shot {i + 1}: pick one of your pictures")
                        if s.get("camera") not in shots_prep.CAMERAS: raise ValueError(f"shot {i + 1}: unknown camera move")
                        if not (0 <= st < en): raise ValueError(f"shot {i + 1}: end must be after start")
                        f = s.get("focus") or [0.5, 0.5]
                        out.append({"id": i + 1, "label": str(s.get("label", ""))[:60], "start": round(st, 2), "end": round(en, 2), "image": s["image"], "camera": s["camera"],
                                    "focus": [min(1, max(0, float(f[0]))), min(1, max(0, float(f[1])))], "scene": str(s.get("scene", ""))[:300], "lyric": str(s.get("lyric", ""))[:200]})
                except (KeyError, TypeError, IndexError) as e: raise ValueError("shot list is malformed: " + str(e))
                if not out or len(out) > 80: raise ValueError("between 1 and 80 shots")
                out.sort(key=lambda s: s["start"])
                for a, b in zip(out, out[1:]):
                    if b["start"] < a["end"] - 0.05: raise ValueError(f"shots {a['id']} and {b['id']} overlap")
                for k, s in enumerate(out): s["id"] = k + 1
                json.dump({"duration": dur or out[-1]["end"], "shots": out, "notes": str(body.get("notes", ""))[:600]}, open(os.path.join(D, "shots.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
                open(os.path.join(D, "shots.json"), "a").write("\n")
                navaan.edit_meta(slug, lambda m: navaan.log_hist(m, f"shot list edited via ui:{sess.get('user') or 'owner'}"))
                return self._send(200, {"ok": True})
            if p == "/api/save":
                n = body.get("file")
                if n not in EDITABLE: return self._send(400, {"error": "file not editable"})
                if n.endswith(".json"): json.loads(body["content"])
                open(os.path.join(C.song_dir(slug), n), "w", encoding="utf-8").write(body["content"])
                navaan.edit_meta(slug, lambda m: navaan.log_hist(m, f"{n} edited via ui:{sess.get('user') or 'owner'}"))   # the history says who and when
                return self._send(200, {"ok": True})
        except (SystemExit, KeyError, ValueError) as e: return self._send(400, {"error": str(e)})
        self._send(404, {"error": "not found"})


def serve(port=8765):
    L.setup(stdout=True)
    L.event(LOG, "info", "server_starting", port=port, bind=os.environ.get("NAVAAN_BIND", "127.0.0.1"), scheduler=scheduler_on())
    threading.Thread(target=analytics_auto.loop, daemon=True).start()  # refreshes the analytics on the schedule set on the Analytics page
    if worker.external():
        print("Jobs and the schedule run in the separate worker process (NAVAAN_WORKER=external).", flush=True)
    else:
        worker.start_background()   # development: one process runs the web server and a worker in threads
        if not scheduler_on(): print("Scheduler is off (NAVAAN_SCHEDULER=off): this portal will not publish on schedule.", flush=True)
    cf = auth.ensure_setup_code()
    if auth.disabled(): print("WARNING: NAVAAN_AUTH=off, the portal has no login", flush=True)
    elif cf: print(f"First run: open the portal and create your login. Setup code is in {cf}", flush=True)
    bind = os.environ.get("NAVAAN_BIND", "127.0.0.1")
    srv = ThreadingHTTPServer((bind, port), H)
    print(f"NAVAAN Studio UI: http://{bind}:{port}  (project {C.find_root()})  Ctrl+C to stop", flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: print("stopped")
    return 0
