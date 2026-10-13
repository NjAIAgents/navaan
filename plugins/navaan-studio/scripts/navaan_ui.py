"""Local web UI for NAVAAN Studio. Bound to 127.0.0.1 only. Standard library only.
Create songs, edit and review text, play media, approve gates (human clicks only), and start the next step."""
import os, re, json, glob, mimetypes, threading, secrets, subprocess, sys, html
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import time
import navaan, navaan_common as C, storage, analytics_api, settings_api
import visuals_cfg as V, shots_prep

TOKEN = secrets.token_urlsafe(24)
JOBS = {}  # slug -> {"running": bool, "rc": int|None}
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
    except SystemExit: rows, n = [], {"type": "none"}
    pub = m.get("published", {}); its = list(pub.get("youtube_items", [])) + ([pub["youtube_short"]] if pub.get("youtube_short", {}).get("id") else [])
    cl = m.get("cloud", {}); public = navaan.public_done(m)
    ig_on = navaan.ig_enabled(m)
    if n.get("type") == "gate": status = "approval"
    elif n.get("type") == "done": status = "done"
    else: status = "production"
    tp = os.path.join(D, "title.txt")
    return {"slug": s, "type": C.item_type(m), "state": m.get("state"), "next": n, "title": open(tp, encoding="utf-8").read().strip() if os.path.exists(tp) else "",
            "album": m.get("album", ""), "status": status, "steps_done": sum(1 for r in rows if r.get("done")), "steps_total": len(rows),
            "public": public, "ig_enabled": ig_on, "published": public and (bool(pub.get("instagram")) or not ig_on), "private": bool(its) and not public, "instagram": bool(pub.get("instagram")), "instagram_url": (pub.get("instagram") or "") if str(pub.get("instagram") or "").startswith("http") else "", "archived": bool(cl.get("uploaded_at")),
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
    except RuntimeError as e: out["error"] = str(e); return out
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
    D = C.song_dir(slug); m = navaan.meta(slug); rows, nxt = navaan.plan(slug)
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
    rn = dict(navaan.RUN.get(slug) or {})
    if rn.get("started"): rn["elapsed"] = int(__import__("time").time() - rn["started"])
    rn.pop("started", None)
    return {"slug": slug, "meta": m, "steps": rows, "next": nxt, "files": fl, "text": txt, "log": lg, "job": JOBS.get(slug, {}), "status_text": navaan.STATUS.get(slug, ""),
            "gates": C.type_gates(C.item_type(m)), "account": C.account(C.item_type(m)) if C.item_type(m) != "music" else None, "approvals": {g: a for g, a in m.get("approvals", {}).items() if navaan.gate_ok(D, m.get("approvals", {}), g)}, "logs": logs, "run": rn,
            "visuals": V.load(D), "images": [os.path.basename(x) for x in V.own_images(D)], "visuals_problems": V.problems(D),
            "profile": bool(C.profile()), "question": navaan.question_open(slug),
            "thumb_pending": (navaan.meta(slug).get("published", {}).get("thumbnail_pending") or []),
            "needs_you": (open(os.path.join(D, "needs_you.txt"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(D, "needs_you.txt")) else "")}


def start_job(slug, all_steps=False, step=None, redo=False):
    if JOBS.get(slug, {}).get("running"): return False
    JOBS[slug] = {"running": True, "rc": None}; navaan.RUN.pop(slug, None)
    def w():
        try: rc = navaan.pipeline(slug, wait=True) if all_steps else (navaan.redo_run(slug, step) if redo else navaan.run(slug, step=step))
        except SystemExit as e: rc = 1
        except Exception: rc = 1
        JOBS[slug] = {"running": False, "rc": rc}
        navaan.STATUS.pop(slug, None) if rc == 0 else None
    threading.Thread(target=w, daemon=True).start(); return True


class H(BaseHTTPRequestHandler):
    server_version = "navaan"
    def log_message(self, *a): pass
    def _send(self, code, body, ctype="application/json", extra=None):
        b = body if isinstance(body, bytes) else (json.dumps(body, ensure_ascii=False) if not isinstance(body, str) else body).encode()
        self.send_response(code); self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text", "application/json")) else ""))
        self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items(): self.send_header(k, v)
        self.end_headers(); self.wfile.write(b)
    def _host_ok(self):
        h = (self.headers.get("Host") or "").split(":")[0]
        return h in ("127.0.0.1", "localhost")
    def do_GET(self):
        if not self._host_ok(): return self._send(403, {"error": "bad host"})
        p = self.path.split("?")[0]
        try:
            if p == "/":
                page = open(os.path.join(navaan.HERE, "ui.html"), encoding="utf-8").read().replace("__TOKEN__", TOKEN)
                return self._send(200, page, "text/html")
            if p == "/api/cloud": return self._send(200, cloud_view("refresh=1" in self.path))
            if p == "/api/settings":
                try: return self._send(200, settings_api.status("refresh=1" in self.path))
                except Exception as e: return self._send(500, {"error": str(e)[:300]})
            if p == "/api/analytics":
                from urllib.parse import parse_qs, urlparse
                q = parse_qs(urlparse(self.path).query); acc = (q.get("account") or ["all"])[0]
                if not analytics_api.ACCOUNT_OK.match(acc): return self._send(400, {"error": "bad account"})
                return self._send(200, analytics_api.overview(acc, (q.get("days") or ["30"])[0]))
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
    def _media(self, slug, name):
        D = C.song_dir(slug); f = os.path.join(D, "clips", os.path.basename(name[6:])) if name.startswith("clips~") else (os.path.join(D, "images", os.path.basename(name[7:])) if name.startswith("images~") else os.path.join(D, os.path.basename(name)))
        if os.path.splitext(f)[1].lower() not in MEDIA_EXT or not os.path.isfile(f): return self._send(404, {"error": "no file"})
        size = os.path.getsize(f); ct = mimetypes.guess_type(f)[0] or "application/octet-stream"
        rng = self.headers.get("Range"); start, end = 0, size - 1; code = 200
        if rng and (mm := re.match(r"bytes=(\d*)-(\d*)", rng)):
            if mm.group(1): start = int(mm.group(1))
            if mm.group(2): end = min(int(mm.group(2)), size - 1)
            if not mm.group(1) and mm.group(2): start = max(0, size - int(mm.group(2))); end = size - 1
            code = 206
        self.send_response(code); self.send_header("Content-Type", ct); self.send_header("Accept-Ranges", "bytes")
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
        except (BrokenPipeError, ConnectionResetError): pass
    def do_POST(self):
        if not self._host_ok() or self.headers.get("X-Navaan-Token") != TOKEN: return self._send(403, {"error": "forbidden"})
        try: body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except Exception: return self._send(400, {"error": "bad json"})
        slug = body.get("slug", ""); p = self.path
        try:
            if p == "/api/analytics/link":
                try: analytics_api.link_post(str(body.get("media_id") or ""), str(body.get("slug") or "")); return self._send(200, {"ok": True})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/analyze":
                try: return self._send(200, {"results": analytics_api.analyze_now(str(body.get("account") or "all"))})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/ask":
                try: return self._send(200, {"started": analytics_api.start_ask(str(body.get("account") or "all"))})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/rec":
                try: analytics_api.set_rec_status(str(body.get("id") or ""), str(body.get("status") or ""), body.get("reason")); return self._send(200, {"ok": True})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p == "/api/analytics/collect":
                try: return self._send(200, {"started": analytics_api.start_collect(str(body.get("account") or "all"))})
                except ValueError as e: return self._send(400, {"error": str(e)})
            if p.startswith("/api/settings/"):
                act = p.rsplit("/", 1)[1]; ct = str(body.get("type") or "music")
                try:
                    if act == "ig_refresh": return self._send(200, settings_api.ig_refresh(ct, str(body.get("kind") or "login")))
                    if act == "ig_save": return self._send(200, settings_api.ig_save(ct, str(body.get("kind") or "login"), str(body.get("token") or "")))
                    if act == "yt_signin": return self._send(200, {"started": settings_api.yt_signin(ct)})
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
                    m = navaan.meta(x); m["album"] = name
                    if not name: m.pop("album", None)
                    navaan.save_meta(x, m)
                return self._send(200, {"ok": True, "count": len(sl)})
            if p == "/api/new":
                if slug and not SLUG.match(slug): return self._send(400, {"error": "slug: letters, digits, dash, underscore"})
                import new_song
                sl = new_song.create(slug or None, body.get("type") or "music", str(body.get("idea") or ""))
                return self._send(200, {"rc": 0, "slug": sl})
            if p == "/api/import":
                import suno_import
                if slug and not SLUG.match(slug): return self._send(400, {"error": "bad slug"})
                sl = suno_import.init(body.get("url", ""), slug or None)
                return self._send(200, {"slug": sl, "started": start_job(sl, True)})
            if not SLUG.match(slug): return self._send(400, {"error": "bad slug"})
            if p == "/api/approve":
                navaan.set_gate(slug, body["gate"], True, "ui"); started = False
                m = navaan.meta(slug); sid = m.get("redo_pending")
                if sid and body["gate"] == "credits":
                    m.pop("redo_pending", None); navaan.save_meta(slug, m); started = start_job(slug, False, sid)
                return self._send(200, {"ok": True, "started": started})
            if p == "/api/answer":
                qid = navaan.set_answer(slug, body.get("choice"), body.get("text"), "ui")
                return self._send(200, {"ok": True, "id": qid, "started": start_job(slug, True)})
            if p == "/api/revoke": navaan.set_gate(slug, body["gate"], False, "ui"); return self._send(200, {"ok": True})
            if p == "/api/redo":
                if JOBS.get(slug, {}).get("running"): return self._send(409, {"error": "a run is in progress for this song"})
                return self._send(200, {"started": start_job(slug, False, body.get("step"), redo=True)})
            if p == "/api/run": return self._send(200, {"started": start_job(slug, bool(body.get("all")))})
            if p.startswith("/api/visuals/"):
                act = p.rsplit("/", 1)[1]; D = C.song_dir(slug)
                try:
                    if act == "upload": return self._send(200, {"path": V.add_image(D, body.get("name"), str(body.get("data") or ""))})
                    if act == "remove": V.remove_image(D, body.get("path")); return self._send(200, {"ok": True})
                    if act == "save":
                        v = V.save(D, str(body.get("mode") or ""), body.get("layout"), body.get("camera", ""), body.get("scene", ""))
                        m = navaan.meta(slug); navaan.log_hist(m, f"visuals chosen via ui: {v['mode']}{' ' + v.get('layout', '') if v['mode'] == 'own' else ''}"); navaan.save_meta(slug, m)
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
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"NAVAAN Studio UI: http://127.0.0.1:{port}  (project {C.find_root()})  Ctrl+C to stop", flush=True)
    try: srv.serve_forever()
    except KeyboardInterrupt: print("stopped")
    return 0
