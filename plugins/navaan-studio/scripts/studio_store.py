"""studio_store.py  the state of every song and inspiration, in Postgres (schema "studio"). Replaces reading and writing songs/<slug>/meta.json.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: load, save and locked update of an item's document, projections for SQL, and a write-through meta.json export.

Source of truth (constitution III): studio.items.doc. meta.json stays in each song folder as a write-through export after every commit, for one release, so
tools that still read the file, the bucket upload and a rollback to the previous image keep working. Reads never use the file, except one case: an item that is not in
Postgres yet and has a meta.json is imported on first use (verified by reading it back), so a machine that never ran the batch import still works.

  load(slug, default)        the document (a copy), or default when there is none
  save(slug, doc)            replace the document (last write wins, like the old file; use update when you read first)
  update(slug, fn)           lock the row, run fn(doc) on the current document, store the result: no lost update between the web server, the scheduler and a step
  exists(slug), delete(slug), slugs()
  import_all(dry_run)        copy every songs/*/meta.json in, report the differences; auto() does that at start when Postgres has no items yet

A document is a plain dict. Projections (history, approvals, publications, schedules) are derived from it by project() in the same transaction as every save.
"""
import os, re, copy, json, hashlib, datetime, threading, tempfile
import navaan_log as L
import navaan_common as C
import analytics_db as db
LOG = L.get("studio_store")

_LOCAL = threading.local()
import pgconn; pgconn.register(_LOCAL)
SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def _conn():
    """One connection per thread, reused (opening one costs more than the query), replaced if it died or the songs folder changed (tests).
    A songs folder under the system temp directory is a throwaway one: it gets its own throwaway schema, so tests never touch real state."""
    root = C.songs_root()
    c = getattr(_LOCAL, "conn", None)
    if c is not None and not c.closed and getattr(_LOCAL, "root", None) == root and c.info.transaction_status != 3:   # 3 = INERROR: a failed transaction left open
        return c   # a dead connection raises at its first use; the caller's rollback and the next call open a new one
    if c is not None and not c.closed: c.close()
    tmp = os.path.realpath(tempfile.gettempdir())
    _LOCAL.conn = db.connect(root, base="studio", isolate=os.path.realpath(root).startswith(tmp + os.sep))
    _LOCAL.root = root
    return _LOCAL.conn


def _jsonb(v):
    from psycopg.types.json import Jsonb
    return Jsonb(v)


def _ts(s):
    if not s or not isinstance(s, str): return None
    try: return datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    except ValueError: return None   # expected: a history stamp or approval time that is not an ISO time simply has no timestamp


# ---- projections -------------------------------------------------------------------------------------------------------------
def project(doc):
    """The SQL-facing rows derived from a document. Pure: the same document always gives the same rows."""
    hist = []
    for i, h in enumerate(doc.get("history") or []):
        h = h if isinstance(h, str) else json.dumps(h, ensure_ascii=False)
        m = re.match(r"^(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) (.*)$", h, re.S)
        hist.append((i, _ts(m.group(1)) if m else None, m.group(2) if m else h))
    appr = []
    for gate, v in sorted((doc.get("approvals") or {}).items()):
        v = v if isinstance(v, dict) else {"value": v}
        appr.append((gate, _ts(v.get("at")), v.get("via"), v.get("sha"), v))
    pubs = []
    p = doc.get("published") or {}
    for it in p.get("youtube_items") or []:
        if isinstance(it, dict):
            kind = "short" if str(it.get("file", "")).startswith("short") or it.get("kind") == "short" else "video"
            pubs.append(("youtube", kind, str(it.get("id", "")), it.get("url"), it.get("privacy"), it))
    ig = p.get("instagram")
    if ig and isinstance(ig, str): pubs.append(("instagram", "reel" if "/reel/" in ig else "feed", "", ig, None, {}))
    sched = []
    s = doc.get("schedule") or {}
    if isinstance(s, dict) and s:
        att = s.get("attempts") or {}
        for platform, key, steps in (("youtube", "youtube_at", ("publish_youtube", "go_public", "publish_short")), ("instagram", "instagram_at", ("publish_instagram",))):
            if not s.get(key): continue
            blocked = {k: v for k, v in (s.get("blocked") or {}).items() if k in steps}
            missed = any((s.get("missed") or {}).get(k) for k in steps)
            status = "done" if s.get("done") else "missed" if missed else "blocked" if blocked else "waiting"
            n = sum(int((att.get(k) or {}).get("n", 0)) for k in steps)
            sched.append((platform, _ts(s.get(key)), status, n, {"steps": list(steps), "blocked": blocked}))
    return hist, appr, pubs, sched


def _text(doc):
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write(c, slug, doc, sha):
    """Store doc for slug inside the caller's transaction and rebuild its projections. `sha` is the hash of the meta.json text that goes with it."""
    t = C.item_type(doc)
    row = c.execute("INSERT INTO items (slug, type, state, doc, export_sha) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT (slug) DO UPDATE SET type = excluded.type, state = excluded.state, doc = excluded.doc, export_sha = excluded.export_sha, "
                    "version = items.version + 1, updated_at = now() RETURNING id, version",
                    (slug, t if t in ("music", "inspiration", "aha", "explainer", "podcast") else "music", doc.get("state"), _jsonb(doc), sha)).fetchone()
    iid = row["id"]
    hist, appr, pubs, sched = project(doc)
    for tbl in ("item_history", "approvals", "publications", "schedules"): c.execute(f"DELETE FROM {tbl} WHERE item_id = ?", (iid,))
    for seq, at, text in hist: c.execute("INSERT INTO item_history (item_id, seq, at, text) VALUES (?, ?, ?, ?)", (iid, seq, at, text))
    for gate, at, via, sha_, detail in appr:
        c.execute("INSERT INTO approvals (item_id, gate, approved_at, via, content_hash, detail) VALUES (?, ?, ?, ?, ?, ?)", (iid, gate, at, via, sha_, _jsonb(detail)))
    for platform, kind, ext, url, privacy, detail in pubs:
        c.execute("INSERT INTO publications (item_id, platform, kind, external_id, url, privacy, detail) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING", (iid, platform, kind, ext, url, privacy, _jsonb(detail)))
    for platform, run_at, status, n, detail in sched:
        c.execute("INSERT INTO schedules (item_id, platform, run_at, status, attempts, detail) VALUES (?, ?, ?, ?, ?, ?)", (iid, platform, run_at, status, n, _jsonb(detail)))
    return row["version"]


# ---- the write-through export ------------------------------------------------------------------------------------------------
def _dir(slug):
    return os.path.join(C.songs_root(), slug)   # not C.song_dir: that exits when the folder is missing, and a new item has no folder yet


def _export(slug, text):
    """meta.json from the document, before the commit: temp file and rename, so a reader never sees half a file. A failure raises, which rolls the save back:
    a file that silently lags Postgres would later look like somebody else's edit."""
    d = _dir(slug)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".meta.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f: f.write(text)
        os.replace(tmp, os.path.join(d, "meta.json"))
    except BaseException:
        try: os.remove(tmp)
        except FileNotFoundError: pass   # expected: the rename already moved it, or the write never created it
        raise


def _file_text(slug):
    try:
        with open(os.path.join(_dir(slug), "meta.json"), encoding="utf-8") as f: return f.read()
    except FileNotFoundError: return None   # expected: no export yet (new item) or the folder was removed


def _reconcile(c, slug, doc, sha):
    """Postgres is the truth, with one exception: meta.json on disk that is not the file we last wrote was changed by someone else (a Claude step that follows a skill
    saying 'record it in meta.json', the previous release after a rollback, a person). Its content is then the newer state. Returns (document, changed_by_file)."""
    ft = _file_text(slug)
    if ft is None or _sha(ft) == sha: return doc, False
    try: ext = json.loads(ft)
    except ValueError:
        L.event(LOG, "error", "meta_json_invalid", item=slug, note="kept the stored state; fix or remove the file"); return doc, False
    if not isinstance(ext, dict):
        L.event(LOG, "error", "meta_json_invalid", item=slug, note="not an object; kept the stored state"); return doc, False
    if ext == json.loads(json.dumps(doc)):   # same content, different formatting or key order: just remember the file's hash
        c.execute("UPDATE items SET export_sha = ? WHERE slug = ?", (_sha(ft), slug)); return doc, False
    L.event(LOG, "info", "meta_json_edited_outside", item=slug)
    return ext, True


# ---- the API -----------------------------------------------------------------------------------------------------------------
def _check(slug):
    if not isinstance(slug, str) or not SLUG.match(slug): raise ValueError(f"bad item slug {slug!r}")


def _get(c, slug, lock=False):
    r = c.run("SELECT doc, export_sha FROM items WHERE slug = ?" + (" FOR UPDATE" if lock else ""), (slug,)).fetchone()
    return (r["doc"], r["export_sha"]) if r else (None, None)


def _adopt(c, slug, ext, text):
    """Store a document that came from the file as it is (its text is already on disk, so no export)."""
    _write(c, slug, ext, _sha(text))


def load(slug, default=None):
    _check(slug)
    c = _conn()
    try:
        doc, sha = _get(c, slug)    # the common case is a plain read: the file is the one we wrote
        if doc is not None:
            ft = _file_text(slug)
            if ft is None or _sha(ft) == sha: c.commit(); return copy.deepcopy(doc)
        doc, sha = _get(c, slug, lock=True)    # an outside edit or a first import: lock so that taking it in cannot race with a save
        if doc is None:
            ft = _file_text(slug)
            if ft is None: c.commit(); return default
            ext = json.loads(ft)
            L.event(LOG, "info", "item_imported_on_first_use", item=slug)
            _adopt(c, slug, ext, ft); c.commit(); return copy.deepcopy(ext)
        doc, changed = _reconcile(c, slug, doc, sha)
        if changed: _adopt(c, slug, doc, _file_text(slug))
        c.commit()
        return copy.deepcopy(doc)
    except Exception:
        c.rollback(); raise


def save(slug, doc):
    _check(slug)
    c = _conn()
    try:
        text = _text(doc)
        _write(c, slug, doc, _sha(text)); _export(slug, text); c.commit()
    except Exception:
        c.rollback(); L.exc(LOG, "item_save_failed", item=slug); raise


def update(slug, fn):
    """Lock the item, call fn(doc) with its current document (an empty one for a new item), store what fn leaves in doc, return it. fn changes doc in place."""
    _check(slug)
    c = _conn()
    try:
        doc, sha = _get(c, slug, lock=True)
        if doc is None:
            ft = _file_text(slug)
            doc = json.loads(ft) if ft is not None else {}
        else:
            doc, _ = _reconcile(c, slug, doc, sha)
        doc = copy.deepcopy(doc)
        fn(doc)   # in place; the return value is ignored on purpose, so a lambda like `lambda d: d.pop("x", None)` cannot replace the document with the popped value
        text = _text(doc)
        _write(c, slug, doc, _sha(text)); _export(slug, text); c.commit()
    except Exception:
        c.rollback(); raise
    return doc


def exists(slug):
    _check(slug)
    c = _conn()
    try: ok = c.execute("SELECT 1 AS x FROM items WHERE slug = ?", (slug,)).fetchone() is not None; c.commit(); return ok or _file_text(slug) is not None
    except Exception: c.rollback(); raise


def delete(slug):
    _check(slug)
    c = _conn()
    try: c.execute("DELETE FROM items WHERE slug = ?", (slug,)); c.commit()
    except Exception: c.rollback(); raise
    try: os.remove(os.path.join(_dir(slug), "meta.json"))   # the export too, or the next load would import it back
    except FileNotFoundError: pass   # expected: there was no export file to remove


def slugs():
    c = _conn()
    try: r = [x["slug"] for x in c.execute("SELECT slug FROM items ORDER BY slug").fetchall()]; c.commit(); return r
    except Exception: c.rollback(); raise


# ---- batch import, used at start -----------------------------------------------------------------------------------------------
def import_all(dry_run=False):
    """Every songs/*/meta.json into Postgres. Returns a report: per item imported/unchanged/updated/FAILED. Idempotent."""
    rep = []
    root = C.songs_root()
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if name.startswith("_") or not os.path.isfile(os.path.join(root, name, "meta.json")): continue
        ft = _file_text(name)
        try: fd = json.loads(ft)
        except ValueError as e:
            rep.append((name, "unreadable", str(e)[:120])); L.event(LOG, "error", "meta_json_unreadable", item=name, error=str(e)[:120]); continue
        c = _conn()
        try:
            have, _ = _get(c, name); c.commit()
            if have == json.loads(json.dumps(fd)): rep.append((name, "unchanged", "")); continue
            if dry_run: rep.append((name, "would import" if have is None else "would update", "")); continue
            _write(c, name, fd, _sha(ft)); c.commit()
            back, _ = _get(c, name); c.commit()
            if back != json.loads(json.dumps(fd)): raise RuntimeError("stored document differs from meta.json after import")
            rep.append((name, "imported" if have is None else "updated", ""))
        except Exception as e:
            c.rollback(); rep.append((name, "FAILED", f"{type(e).__name__}: {e}"[:160])); L.exc(LOG, "item_import_failed", item=name)
    return rep


def auto():
    """Called when the portal starts: when Postgres has no items and song folders have meta.json, import them all, verified. Raises SystemExit if any fails, so a
    release that cannot carry the state over never becomes healthy (the pipeline rolls back; the files were never changed)."""
    if slugs(): return "already in postgres"
    rep = import_all()
    bad = [r for r in rep if r[1] in ("FAILED", "unreadable")]
    L.event(LOG, "error" if bad else "info", "studio_import_done", items=len(rep), failed=len(bad))
    if bad:
        raise SystemExit("studio: could not import " + ", ".join(f"{n} ({why}: {d})" for n, why, d in bad) + ". Nothing was changed in the song folders.")
    return f"imported {len(rep)}"
