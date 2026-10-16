"""catalog_store.py  tracks, albums, assets and the search index, in Postgres (schema "catalog").

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: NAV-6 stage 1. What listeners will find and play, built from the studio's items; the studio stays the place a song is made, the catalog the place it is found.

Rules
  sync_item(slug) makes the catalog row of one studio item match the item (idempotent, safe to run at any time); sync_all() does every item, auto() runs at portal start
  a track is published when the studio says so (state published, or public on YouTube); drafts are stored but never indexed for search
  assets point at object storage (storage_key = cloud prefix + file name) and only for files the cloud record says were verified there: the bucket, not the local folder, is the source
  license_status is never changed by a sync: new tracks start 'unconfirmed' and only the owner confirms (NAV-11, FR-017); offerable() is the one question "may this be put behind a plan?"
  the item's album label becomes an album with the song in it (FR-008); after that the catalog's album is canonical (order, cover, date, kind), the label is only an input
"""
import os, re, glob, json, tempfile, threading, datetime
import navaan_log as L
import navaan_common as C
import analytics_db as db
import translit
LOG = L.get("catalog")

_LOCAL = threading.local()
ASSET_ROLES = {"final.mp3": ("audio", "audio/mpeg"), "cover_1x1.png": ("cover", "image/png"), "final_16x9.mp4": ("video", "video/mp4")}
ARTIST = "navaan"
EXCERPT = 240


def _conn():
    """One connection per thread; a songs folder under the system temp directory (tests) gets its own throwaway schema."""
    root = C.songs_root()
    c = getattr(_LOCAL, "conn", None)
    if c is not None and not c.closed and getattr(_LOCAL, "root", None) == root and c.info.transaction_status != 3: return c
    if c is not None and not c.closed: c.close()
    tmp = os.path.realpath(tempfile.gettempdir())
    _LOCAL.conn = db.connect(root, base="catalog", isolate=os.path.realpath(root).startswith(tmp + os.sep)); _LOCAL.root = root
    return _LOCAL.conn


def _tx(fn):
    c = _conn()
    try: r = fn(c); c.commit(); return r
    except Exception:
        c.rollback(); raise


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", translit.fold(translit.to_roman(s))).strip("-") or "album"


def _read(D, name):
    p = os.path.join(D, name)
    return open(p, encoding="utf-8").read().strip() if os.path.isfile(p) else ""


def _artist(c):
    return c.execute("SELECT id FROM artists WHERE slug = ?", (ARTIST,)).fetchone()["id"]


def _index(c, kind, subject_id, artist_id, title, titles=(), tags=(), excerpt=""):
    """The search document of a track or an album: the title as written, other titles (Hindi, Maithili...) and the tags, folded, plus the Roman form of each."""
    text = translit.search_text(" ".join([title, *titles]), tags)
    c.execute("INSERT INTO search_documents (kind, subject_id, artist_id, title_native, title_roman, tags, lyrics_excerpt, search_text) VALUES (?, ?::uuid, ?::uuid, ?, ?, ?, ?, ?) "
              "ON CONFLICT (kind, subject_id) DO UPDATE SET artist_id = excluded.artist_id, title_native = excluded.title_native, title_roman = excluded.title_roman, tags = excluded.tags, "
              "lyrics_excerpt = excluded.lyrics_excerpt, search_text = excluded.search_text, updated_at = now()",
              (kind, subject_id, artist_id, title, translit.to_roman(title), list(tags), translit.fold(excerpt)[:EXCERPT], text))


def _unindex(c, kind, subject_id):
    c.execute("DELETE FROM search_documents WHERE kind = ? AND subject_id = ?::uuid", (kind, subject_id))


def _ts(s):
    try: return datetime.datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    except ValueError: return None   # expected: not an ISO time, so there is no timestamp


def sync_item(slug):
    """Make the catalog match one studio item. Returns the track slug, or None when the item is not a song."""
    m = C.item_load(slug, None)
    if not m or C.item_type(m) != "music": return None
    D = C.song_dir(slug)
    title = _read(D, "title.txt") or slug
    others = [t for t in (_read(D, os.path.basename(p)) for p in sorted(glob.glob(os.path.join(D, "title_*.txt")))) if t]
    lyrics = _read(D, "lyrics.txt"); roman = _read(D, "lyrics_roman.txt")
    try: tags = [str(t).lstrip("#") for t in json.loads(_read(D, "tags.json") or "[]")][:20]
    except ValueError: tags = []   # expected: tags.json holds something else, e.g. an object; no tags then
    pub = m.get("published", {}); cloud = m.get("cloud", {})
    published = m.get("state") == "published" or bool(pub.get("youtube_items") and all(i.get("privacy") == "public" for i in pub["youtube_items"]))
    origin = "suno" if (m.get("suno_url") or m.get("suno_model")) else "unknown"
    detail = {k: m[k] for k in ("suno_model",) if m.get(k)}

    def go(c):
        aid = _artist(c)
        t = c.execute("INSERT INTO tracks (artist_id, slug, studio_slug, title, lyrics_text, status, published_at, origin, origin_detail) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                      "ON CONFLICT (slug) DO UPDATE SET title = excluded.title, lyrics_text = excluded.lyrics_text, status = excluded.status, "
                      "published_at = COALESCE(tracks.published_at, excluded.published_at), origin = excluded.origin, origin_detail = excluded.origin_detail, updated_at = now() "
                      "RETURNING id", (aid, slug, slug, title, lyrics, "published" if published else "draft",
                                       (_ts(cloud.get("uploaded_at")) or datetime.datetime.now(datetime.timezone.utc)) if published else None, origin, db_json(detail))).fetchone()
        tid = str(t["id"])
        if cloud.get("verified"):   # only what is really in the bucket
            for name, o in (cloud.get("objects") or {}).items():
                role = ASSET_ROLES.get(name)
                if role: c.execute("INSERT INTO assets (owner_kind, owner_id, role, storage_key, mime, bytes) VALUES ('track', ?::uuid, ?, ?, ?, ?) "
                                   "ON CONFLICT (owner_kind, owner_id, role, storage_key) DO UPDATE SET bytes = excluded.bytes",
                                   (tid, role[0], (cloud.get("prefix") or "") + name, role[1], (o or {}).get("size")))
        album = (m.get("album") or "").strip()
        if album:
            a = c.execute("INSERT INTO albums (artist_id, slug, title, status) VALUES (?, ?, ?, ?) ON CONFLICT (slug) DO UPDATE SET "
                          "status = CASE WHEN albums.status = 'draft' AND ? THEN 'published' ELSE albums.status END RETURNING id, title", (aid, slugify(album), album, "published" if published else "draft", published)).fetchone()
            c.execute("INSERT INTO album_tracks (album_id, track_id, position) SELECT ?::uuid, ?::uuid, COALESCE(MAX(position), 0) + 1 FROM album_tracks WHERE album_id = ?::uuid ON CONFLICT (album_id, track_id) DO NOTHING",
                      (str(a["id"]), tid, str(a["id"])))
            _reindex_album(c, str(a["id"]))
        if published: _index(c, "track", tid, str(aid), title, others, tags, roman or lyrics)
        else: _unindex(c, "track", tid)
        return slug
    return _tx(go)


def db_json(v):
    from psycopg.types.json import Jsonb
    return Jsonb(v)


def _reindex_album(c, album_id):
    a = c.execute("SELECT id, artist_id, title, status FROM albums WHERE id = ?::uuid", (album_id,)).fetchone()
    if a and a["status"] == "published": _index(c, "album", str(a["id"]), str(a["artist_id"]), a["title"])
    elif a: _unindex(c, "album", str(a["id"]))


def sync_all():
    out = []
    for p in sorted(glob.glob(os.path.join(C.songs_root(), "*", "meta.json"))):
        slug = os.path.basename(os.path.dirname(p))
        try:
            if sync_item(slug): out.append(slug)
        except Exception: L.exc(LOG, "catalog_sync_failed", item=slug)   # one bad song must not hide the rest
    return out


def auto():
    """At portal start: bring the catalog up to date with the studio. Never stops the portal (the catalog can be rebuilt any time)."""
    try: n = sync_all(); L.event(LOG, "info", "catalog_synced", tracks=len(n)); return n
    except Exception: L.exc(LOG, "catalog_auto_failed"); return []


def offerable(track_slug):
    """May this track be put behind a plan? Only with a confirmed licence (FR-017)."""
    r = _tx(lambda c: c.execute("SELECT license_status FROM tracks WHERE slug = ?", (track_slug,)).fetchone())
    return bool(r) and r["license_status"] == "confirmed"


# ---- albums (the owner's API; the screens come in NAV-16) ---------------------------------------------------------------------------

def _album_rows(c, where="", params=()):
    rows = c.execute(f"SELECT id, slug, title, kind, status, release_date, description FROM albums {where} ORDER BY release_date DESC NULLS LAST, title", params).fetchall()
    for r in rows:
        r["id"] = str(r["id"]); r["release_date"] = r["release_date"].isoformat() if r["release_date"] else None
        r["tracks"] = [{"slug": x["slug"], "title": x["title"], "position": x["position"]} for x in c.execute(
            "SELECT t.slug, t.title, at.position FROM album_tracks at JOIN tracks t ON t.id = at.track_id WHERE at.album_id = ?::uuid ORDER BY at.position", (r["id"],)).fetchall()]
    return rows


def albums():
    return _tx(lambda c: _album_rows(c))


def save_album(slug, title, kind="album", status="draft", release_date=None, description=""):
    """Create (slug empty) or update an album. Returns its slug."""
    title = (title or "").strip()
    if not title: raise ValueError("an album needs a title")
    if kind not in ("album", "ep", "single"): raise ValueError("kind is album, ep or single")
    if status not in ("draft", "scheduled", "published"): raise ValueError("status is draft, scheduled or published")
    try: rd = datetime.date.fromisoformat(release_date) if release_date else None
    except ValueError: raise ValueError("release date is YYYY-MM-DD") from None
    def go(c):
        out = slug
        if out:
            r = c.execute("UPDATE albums SET title = ?, kind = ?, status = ?, release_date = ?, description = ?, updated_at = now() WHERE slug = ? RETURNING id", (title, kind, status, rd, description or "", out)).fetchone()
            if not r: raise LookupError("no such album")
        else:
            s = base = slugify(title); n = 2
            while c.execute("SELECT 1 FROM albums WHERE slug = ?", (s,)).fetchone(): s = f"{base}-{n}"; n += 1
            r = c.execute("INSERT INTO albums (artist_id, slug, title, kind, status, release_date, description) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id, slug", (_artist(c), s, title, kind, status, rd, description or "")).fetchone()
            out = r["slug"]
        _reindex_album(c, str(r["id"])); return out
    return _tx(go)


def reorder(album_slug, track_slugs):
    """Set the tracklist: the tracks in the order given (tracks not named leave the album, unknown ones are refused). One transaction; positions pass through duplicates."""
    if len(set(track_slugs)) != len(track_slugs): raise ValueError("a track is listed twice")
    def go(c):
        a = c.execute("SELECT id FROM albums WHERE slug = ?", (album_slug,)).fetchone()
        if not a: raise LookupError("no such album")
        ids = {}
        for s in track_slugs:
            t = c.execute("SELECT id FROM tracks WHERE slug = ?", (s,)).fetchone()
            if not t: raise ValueError(f"no such track: {s}")
            ids[s] = str(t["id"])
        aid = str(a["id"])
        c.execute("DELETE FROM album_tracks WHERE album_id = ?::uuid AND NOT (track_id = ANY(?::uuid[]))", (aid, list(ids.values())))
        for pos, s in enumerate(track_slugs, 1):
            c.execute("INSERT INTO album_tracks (album_id, track_id, position) VALUES (?::uuid, ?::uuid, ?) ON CONFLICT (album_id, track_id) DO UPDATE SET position = excluded.position", (aid, ids[s], pos))
        return track_slugs
    return _tx(go)


def delete_album(slug):
    """Remove the album; its tracks stay. True when it existed."""
    def go(c):
        r = c.execute("DELETE FROM albums WHERE slug = ? RETURNING id", (slug,)).fetchone()
        if r: _unindex(c, "album", str(r["id"]))
        return bool(r)
    return _tx(go)
