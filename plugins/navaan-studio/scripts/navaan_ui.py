"""Local web UI for NAVAAN Studio. Bound to 127.0.0.1 unless NAVAAN_BIND says otherwise. Standard library only.
Create songs, edit and review text, play media, approve gates (human clicks only), and start the next step."""
import os, re, json, glob, hmac, mimetypes, threading, secrets, subprocess, sys, html, logging
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import time
import navaan, navaan_common as C, storage, analytics_api, settings_api
import visuals_cfg as V, prompt_pack, shots_prep, publish_schedule as PS, besttime, analytics_auto
import auth
import jobs, worker
import navaan_log as L
LOG = L.get("web")

TOKEN = secrets.token_urlsafe(24)
PUBLIC_HOST = lambda: os.environ.get("NAVAAN_PUBLIC_HOST", "").strip().lower()  # extra allowed Host, e.g. navaan.njlabs.dev
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
VERT = {}  # slug -> {"running": bool, "error": str}, the native 9:16 recompose of chosen pictures
EDITABLE = {"brief.md", "lyrics.txt", "style.txt", "title.txt", "tags.json", "instagram.txt", "quote.json"}
READABLE = EDITABLE | {"originality.json", "timing.json", "render_report.json", "youtube.json", "shots.json", "visuals.json"}
MEDIA_EXT = {".mp3", ".mp4", ".png", ".jpg", ".jpeg", ".webp", ".json", ".txt", ".md", ".log"}
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
    return {"slug": slug, "meta": m, "steps": rows, "next": nxt, "files": fl, "text": txt, "log": lg, "job": {"running": jv["running"], "rc": jv["rc"], "queued": jv["queued"]}, "status_text": jv["status_text"],
            "gates": C.type_gates(C.item_type(m)), "account": C.account(C.item_type(m)) if C.item_type(m) != "music" else None, "approvals": {g: a for g, a in m.get("approvals", {}).items() if navaan.gate_ok(D, m.get("approvals", {}), g)}, "logs": logs, "run": rn,
            "visuals": V.load(D), "images": [os.path.basename(x) for x in V.own_images(D)], "visuals_problems": V.problems(D), "openai_pictures": __import__("media_cfg").load()["image_provider"] == "openai", "prompt_pack": prompt_pack.load(D),
            "try": {**TRY.get(slug, {}), "files": [n for n in ("try_01.png", "try_02.png") if os.path.isfile(os.path.join(D, n))], "v": int(os.path.getmtime(os.path.join(D, "try_01.png"))) if os.path.isfile(os.path.join(D, "try_01.png")) else 0},
            "vertical": {**VERT.get(slug, {}), "done": sorted(int(m.group(1)) for f in (os.listdir(os.path.join(D, "images", "vert")) if os.path.isdir(os.path.join(D, "images", "vert")) else []) for m in [re.match(r"pic_(\d+)\.png$", f)] if m)},
            "profile": bool(C.profile()), "question": navaan.question_open(slug),
            "thumb_pending": (navaan.meta(slug).get("published", {}).get("thumbnail_pending") or []),
            "needs_you": (open(os.path.join(D, "needs_you.txt"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(D, "needs_you.txt")) else "")}


def start_job(slug, all_steps=False, step=None, redo=False):
    """Queue the run for a worker (jobs.py). False when the item already has a queued or running job."""
    kind = "pipeline" if all_steps else ("redo" if redo else "step")
    return bool(jobs.enqueue(slug, kind, {"all": all_steps, "step": step, "redo": redo}))


CLIENT_LOG = {}  # client address -> times of recent browser error reports
CLIENT_LOG_LOCK = threading.Lock()
def client_log_ok(ip, n=30, per=60):
    """At most n browser reports per minute per address, so a broken page cannot flood the log."""
    t = time.time()
    with CLIENT_LOG_LOCK:
        q = [x for x in CLIENT_LOG.get(ip, []) if t - x < per]
        if len(q) >= n: CLIENT_LOG[ip] = q; return False
        q.append(t); CLIENT_LOG[ip] = q; return True


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
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
        if code >= 400 and ctype.startswith("application/json") and not getattr(self, "_err_logged", False):
            err = body.get("error") if isinstance(body, dict) else None
            ei = sys.exc_info() if code >= 500 and sys.exc_info()[0] else None  # inside an except block this is the error that caused the reply
            LOG.log(logging.ERROR if code >= 500 else (logging.DEBUG if code == 401 else logging.INFO), "http_error", exc_info=ei, extra={"fields": {"status": code, "error": str(err)[:300]}})
            if code >= 500: self._err_logged = True
    def _host_ok(self):
        h = (self.headers.get("Host") or "").split(":")[0]
        return h in ("127.0.0.1", "localhost") or (bool(PUBLIC_HOST()) and h == PUBLIC_HOST())
    def _ip(self):  # real client address; X-Real-IP only when a trusted proxy sits in front (NAVAAN_TRUST_PROXY=1)
        return (self.headers.get("X-Real-IP") or "").strip() if TRUST_PROXY() and self.headers.get("X-Real-IP") else self.client_address[0]
    def _https(self): return TRUST_PROXY() and (self.headers.get("X-Forwarded-Proto") or "").lower() == "https"
    def _do_GET(self):
        if not self._host_ok(): return self._send(403, {"error": "bad host"})
        p = self.path.split("?")[0]
        if p in ("/privacy", "/terms"):  # public on purpose: Google asks for these links on the OAuth consent screen
            return self._send(200, open(os.path.join(navaan.HERE, p[1:] + ".html"), encoding="utf-8").read(), "text/html")
        ck = self.headers.get("Cookie")
        if p == "/auth/state":
            st = auth.state(ck, self.headers.get("Host"), ip=self._ip(), https=self._https()); sec = secrets_status()
            if sec: st["secrets"] = sec if st.get("state") == "authed" else {"status": sec["status"]}  # detail only after sign in
            if st.get("state") == "authed": st["scheduler"] = scheduler_state(); st["worker"] = worker_state(); st["version"] = app_version(); st["headless"] = os.environ.get("NAVAAN_HEADLESS", "0") == "1"
            return self._send(200, st)
        sess = auth.session(ck)
        if not sess:  # not signed in: only the sign in page is served
            if p in ("/", "/legacy") or p == "/app" or p.startswith("/app/"): return self._send(200, open(os.path.join(navaan.HERE, "auth.html"), encoding="utf-8").read(), "text/html")
            return self._send(401, {"error": "sign in", "login": True})
        if p == "/api/me": return self._send(200, {"user": sess.get("user"), "roles": sess.get("roles", []), "permissions": sess.get("permissions", [])})   # any signed-in person
        if not auth.can(sess, "studio.access"): return self._send(403, {"error": "this account cannot use the studio"})   # constitution V: no studio route for a listener
        csrf = sess.get("csrf") or TOKEN   # one token per session; the process-wide one only when the login is off (development)
        try:
            if p in ("/", "/legacy"):   # the classic view, kept until the new app has every screen
                page = open(os.path.join(navaan.HERE, "ui.html"), encoding="utf-8").read().replace("__TOKEN__", csrf)
                return self._send(200, page, "text/html")
            if p == "/app": return self._send(308, b"", "text/plain", {"Location": "/app/"})
            if p.startswith("/app/"):   # the new app (NAV-8): a built single page app, any route that is not a file gets index.html
                rel = p[5:]
                f = web_file(rel) if rel and "." in os.path.basename(rel) else None
                if f: return self._send(200, f[0], f[1], {"Cache-Control": f[2]})
                if rel and "." in os.path.basename(rel): return self._send(404, {"error": "not found"})
                idx = web_file("index.html")
                if not idx: return self._send(503, "The new app is not built. In plugins/navaan-studio/web run: npm ci && npm run build", "text/plain")
                return self._send(200, idx[0].replace(b"__TOKEN__", csrf.encode()), "text/html", {"Cache-Control": "no-store"})
            if p == "/api/cloud": return self._send(200, cloud_view("refresh=1" in self.path))
            if p == "/api/alerts":
                try: return self._send(200, {"alerts": settings_api.alerts()})
                except Exception as e: return self._send(500, {"error": str(e)[:300]})
            if p == "/api/settings":
                try: return self._send(200, settings_api.status("refresh=1" in self.path))
                except Exception as e: return self._send(500, {"error": str(e)[:300]})
            if p == "/api/replies":
                import comment_reply as CR
                from urllib.parse import parse_qs, urlparse
                pf = (parse_qs(urlparse(self.path).query).get("platform") or [""])[0]
                if pf not in CR.PLATFORMS: return self._send(400, {"error": "bad platform"})
                conn = CR.connect()
                try: return self._send(200, {"items": CR.waiting(conn, pf)})
                finally: conn.close()
            if p == "/api/analytics":
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query); acc = (q.get("account") or ["all"])[0]
                if not analytics_api.ACCOUNT_OK.match(acc): return self._send(400, {"error": "bad account"})
                return self._send(200, analytics_api.overview(acc, (q.get("days") or ["30"])[0]))
            if p == "/api/analytics/youtube":
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query); acc = (q.get("account") or ["all"])[0]
                if not analytics_api.ACCOUNT_OK.match(acc): return self._send(400, {"error": "bad account"})
                return self._send(200, analytics_api.yt_overview(acc, (q.get("days") or ["30"])[0]))
            if p == "/api/analytics/auto": return self._send(200, analytics_auto.settings())
            if p == "/api/besttime":
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query); lab = (q.get("type") or ["music"])[0]
                if not analytics_api.ACCOUNT_OK.match(lab): return self._send(400, {"error": "bad type"})
                if (q.get("platform") or ["instagram"])[0] == "youtube": return self._send(200, besttime.for_label_youtube(lab))
                return self._send(200, besttime.for_label(lab))
            if p == "/api/schedule/suggest":
                from urllib.parse import parse_qs, urlparse
                sl = (parse_qs(urlparse(self.path).query).get("slug") or [""])[0]
                if not SLUG.match(sl): return self._send(400, {"error": "bad slug"})
                try: return self._send(200, {"suggestion": PS.suggest(sl)})
                except Exception as e: L.soft(LOG, "schedule_suggest_failed", item=sl); return self._send(200, {"suggestion": None, "error": str(e)[:200]})
            if p == "/api/schedule/options":
                from urllib.parse import parse_qs, urlparse
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
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query); sl = (q.get("slug") or [""])[0]
                if not SLUG.match(sl): return self._send(400, {"error": "bad slug"})
                return self._send(200, analytics_api.song_view(sl))
            if p == "/api/analytics/by-song": return self._send(200, analytics_api.by_song())
            if p == "/api/songs": return self._send(200, [song_row(s) for s in songs()])
            m = re.match(r"^/api/song/([^/]+)$", p)
            if m and SLUG.match(m.group(1)): return self._send(200, detail(m.group(1)))
            m = re.match(r"^/media/([^/]+)/([^/]+)$", p)
            if m and SLUG.match(m.group(1)): return self._media(m.group(1), m.group(2))
        except SystemExit as e: return self._send(404, {"error": str(e)})
        self._send(404, {"error": "not found"})
    def _client_log(self, body):
        """Errors the browser caught or could not catch (spec FR-035). Capped, rate limited and scrubbed by navaan_log."""
        if not client_log_ok(self._ip()): return self._send(429, {"error": "too many reports"})
        f = {k: str(body.get(k, ""))[:n] for k, n in (("message", 500), ("stack", 3000), ("page", 200), ("src", 200), ("line", 10), ("where", 80), ("path", 200), ("status", 10), ("ui_request_id", 40), ("what", 80))}
        sess = auth.session(self.headers.get("Cookie")); f["user"] = (sess or {}).get("user", "") if isinstance(sess, dict) else ""
        f["kind"] = str(body.get("kind", "error"))[:20]
        L.event(L.get("client"), "error" if f["kind"] in ("error", "rejection", "api_network", "api_json") else "warning", "client_" + f["kind"], **{k: v for k, v in f.items() if v})
        return self._send(200, {"ok": True})
    def _media(self, slug, name):
        D = C.song_dir(slug); f = os.path.join(D, "clips", os.path.basename(name[6:])) if name.startswith("clips~") else (os.path.join(D, "images", os.path.basename(name[7:])) if name.startswith("images~") else os.path.join(D, os.path.basename(name)))
        if os.path.splitext(f)[1].lower() in MEDIA_EXT and not os.path.isfile(f) and os.path.splitext(f)[1].lower() not in storage.VIDEO_EXT: storage.fetch_missing(f)  # cleaned after archiving: bring the picture or audio back from the bucket
        if os.path.splitext(f)[1].lower() not in MEDIA_EXT or not os.path.isfile(f): return self._send(404, {"error": "no file"})
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
        if self.path.startswith("/auth/"):
            sec = secrets_status()
            if self.path.startswith("/auth/setup") and sec and sec["status"] != "ok": return self._send(503, {"error": "Secrets are waiting for Vault. The login is restored from Vault once it is unsealed; try again then."})
            try: b = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            except Exception: return self._send(400, {"error": "bad json"})
            code, obj, cookies = auth.handle_post(self.path.split("?")[0], b, ck, self.headers.get("Host"), ip=self._ip(), https=self._https())
            return self._send(code, obj, extra={"Set-Cookie": cookies[0]} if cookies else None)
        sess = auth.session(ck)
        if not sess: return self._send(401, {"error": "sign in", "login": True})
        if not auth.can(sess, "studio.access"): return self._send(403, {"error": "this account cannot use the studio"})
        if not hmac.compare_digest((self.headers.get("X-Navaan-Token") or "").encode(), (sess.get("csrf") or TOKEN).encode()): return self._send(403, {"error": "forbidden"})   # this session's token
        try: body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except Exception: return self._send(400, {"error": "bad json"})
        slug = body.get("slug", ""); p = self.path
        try:
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
                return self._send(200, {"ok": True, "count": len(sl)})
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
                navaan.set_gate(slug, body["gate"], True, "ui"); started = False
                m = navaan.meta(slug); sid = m.get("redo_pending")
                if sid and body["gate"] == "credits":
                    navaan.edit_meta(slug, lambda d: d.pop("redo_pending", None)); started = start_job(slug, False, sid)
                return self._send(200, {"ok": True, "started": started})
            if p == "/api/answer":
                qid = navaan.set_answer(slug, body.get("choice"), body.get("text"), "ui")
                return self._send(200, {"ok": True, "id": qid, "started": start_job(slug, True)})
            if p == "/api/revoke": navaan.set_gate(slug, body["gate"], False, "ui"); return self._send(200, {"ok": True})
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
                return self._send(200, {"ok": True})
            if p == "/api/save":
                n = body.get("file")
                if n not in EDITABLE: return self._send(400, {"error": "file not editable"})
                if n.endswith(".json"): json.loads(body["content"])
                open(os.path.join(C.song_dir(slug), n), "w", encoding="utf-8").write(body["content"]); return self._send(200, {"ok": True})
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
