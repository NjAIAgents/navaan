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
import os, re, glob, json, secrets, tempfile, threading, datetime
import navaan_log as L
import navaan_common as C
import analytics_db as db
import translit
LOG = L.get("catalog")

_LOCAL = threading.local()
import pgconn; pgconn.register(_LOCAL)
ASSET_ROLES = {"final.mp3": ("audio", "audio/mpeg"), "cover_1x1.png": ("cover", "image/png"), "final_16x9.mp4": ("video", "video/mp4"), "caption_timing.json": ("lyrics_timed", "application/json"), "caption_cues.json": ("lyrics_timed", "application/json")}
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
    # tags.json is either a list of hashtags or, as the studio writes it, the song's ID3-style metadata (genre, language, composer...): only genre and language are used from the object
    try: raw = json.loads(_read(D, "tags.json") or "[]")
    except ValueError: raw = []   # expected: unreadable tags.json means no tags
    info = raw if isinstance(raw, dict) else {}
    language = (str(info.get("language") or "").strip() or None); genre = (str(info.get("genre") or "").strip()[:120] or None)
    tags = [str(t).lstrip("#") for t in raw][:20] if isinstance(raw, list) else ([genre] if genre else [])
    pub = m.get("published", {}); cloud = m.get("cloud", {})
    published = m.get("state") == "published" or bool(pub.get("youtube_items") and all(i.get("privacy") == "public" for i in pub["youtube_items"]))
    origin = "suno" if (m.get("suno_url") or m.get("suno_model")) else "unknown"
    detail = {k: m[k] for k in ("suno_model", "suno_plan") if m.get(k)}

    def go(c):
        aid = _artist(c)
        t = c.execute("INSERT INTO tracks (artist_id, slug, studio_slug, title, lyrics_text, status, published_at, origin, origin_detail, language) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                      "ON CONFLICT (slug) DO UPDATE SET title = excluded.title, lyrics_text = excluded.lyrics_text, status = excluded.status, language = COALESCE(excluded.language, tracks.language), "
                      "published_at = COALESCE(tracks.published_at, excluded.published_at), origin = excluded.origin, origin_detail = tracks.origin_detail || excluded.origin_detail, updated_at = now() "
                      "RETURNING id", (aid, slug, slug, title, lyrics, "published" if published else "draft",
                                       (_ts(cloud.get("uploaded_at")) or datetime.datetime.now(datetime.timezone.utc)) if published else None, origin, db_json(detail), language)).fetchone()
        tid = str(t["id"])
        if genre:
            g = c.execute("INSERT INTO genres (name) VALUES (?) ON CONFLICT (name) DO UPDATE SET name = excluded.name RETURNING id", (genre,)).fetchone()
            c.execute("DELETE FROM track_genres WHERE track_id = ?::uuid AND genre_id <> ?::uuid", (tid, str(g["id"])))
            c.execute("INSERT INTO track_genres (track_id, genre_id) VALUES (?::uuid, ?::uuid) ON CONFLICT DO NOTHING", (tid, str(g["id"])))
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
        if slug.startswith("_"): continue   # _template and the like are not items
        try:
            if sync_item(slug): out.append(slug)
        except Exception: L.exc(LOG, "catalog_sync_failed", item=slug)   # one bad song must not hide the rest
    return out


def auto():
    """At portal start: bring the catalog up to date with the studio. Never stops the portal (the catalog can be rebuilt any time)."""
    try: n = sync_all(); L.event(LOG, "info", "catalog_synced", tracks=len(n)); return n
    except Exception: L.exc(LOG, "catalog_auto_failed"); return []


LICENSES = ("unconfirmed", "confirmed", "not_allowed")


def set_license(slug, status, by, note, plan=None):
    """The owner's decision on one track (FR-017, constitution XI): confirmed, unconfirmed or not_allowed, with who decided and why. plan is the Suno plan tier at generation time.
    Nothing but this changes license_status. Returns True when the track exists."""
    if status not in LICENSES: raise ValueError("status is " + ", ".join(LICENSES))
    note = " ".join(str(note or "").split())[:500]
    if not note: raise ValueError("say what the decision rests on")
    d = {"license_note": note, "license_set_by": str(by), "license_set_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), **({"suno_plan": str(plan)} if plan else {})}
    return _tx(lambda c: c.execute("UPDATE tracks SET license_status = ?, origin_detail = origin_detail || ?, updated_at = now() WHERE slug = ? RETURNING id", (status, db_json(d), slug)).fetchone()) is not None


def tracks():
    """Every track with its origin and licence, for the owner's audit table."""
    rows = _tx(lambda c: c.execute("SELECT slug, title, status, origin, origin_detail, license_status FROM tracks ORDER BY slug").fetchall())
    return [{**r, "plan": r["origin_detail"].get("suno_plan", ""), "model": r["origin_detail"].get("suno_model", ""), "decided_by": r["origin_detail"].get("license_set_by", ""), "note": r["origin_detail"].get("license_note", "")} for r in rows]


def offerable(track_slug):
    """May this track be put behind a plan? Only with a confirmed licence (FR-017)."""
    r = _tx(lambda c: c.execute("SELECT license_status FROM tracks WHERE slug = ?", (track_slug,)).fetchone())
    return bool(r) and r["license_status"] == "confirmed"


# ---- albums (the owner's API; the screens come in NAV-16) ---------------------------------------------------------------------------

def _album_rows(c, where="", params=()):
    rows = c.execute(f"SELECT id, slug, title, kind, status, release_date, description FROM albums {where} ORDER BY release_date DESC NULLS LAST, title", params).fetchall()
    for r in rows:
        r["id"] = str(r["id"]); r["release_date"] = r["release_date"].isoformat() if r["release_date"] else None
        r["tracks"] = [{"slug": x["slug"], "title": x["title"], "position": x["position"], "status": x["status"], "licence": x["licence"], "art": {"colour": x["colour"]} if x["has_cover"] else None} for x in c.execute(
            "SELECT t.slug, t.title, t.status, t.license_status AS licence, at.position, "
            "EXISTS (SELECT 1 FROM assets a WHERE a.owner_id = t.id AND a.owner_kind = 'track' AND a.role = 'cover') AS has_cover, "
            "(SELECT a.dominant_colour FROM assets a WHERE a.owner_id = t.id AND a.owner_kind = 'track' AND a.role = 'cover' LIMIT 1) AS colour "
            "FROM album_tracks at JOIN tracks t ON t.id = at.track_id WHERE at.album_id = ?::uuid ORDER BY at.position", (r["id"],)).fetchall()]
    return rows


def albums():
    return _tx(lambda c: _album_rows(c))


def public_albums(all_licences=False):
    """Published albums for the people who listen: only songs they may hear (published, and with a confirmed licence unless the studio asks), and no album left empty."""
    out = []
    for a in albums():
        if a["status"] != "published": continue
        a["tracks"] = [t for t in a["tracks"] if t["status"] == "published" and (all_licences or t["licence"] == "confirmed")]
        if a["tracks"]: out.append(a)
    return out


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
        if status == "published":   # a published album follows the song rules: nothing unpublished in it (the cover is its first song's cover)
            bad = c.execute("SELECT t.slug FROM album_tracks at JOIN tracks t ON t.id = at.track_id WHERE at.album_id = ?::uuid AND t.status <> 'published'", (str(r["id"]),)).fetchall()
            n = c.execute("SELECT count(*) AS n FROM album_tracks WHERE album_id = ?::uuid", (str(r["id"]),)).fetchone()["n"]
            if bad: raise ValueError("every song in a published album must be published; not yet: " + ", ".join(b["slug"] for b in bad))
            if not n: raise ValueError("a published album needs at least one song")
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


if __name__ == "__main__":
    # python3 catalog_store.py license <confirmed|unconfirmed|not_allowed> "<why>" [--plan paid] [slug ...]   (no slug = every track): the owner's decision, from a shell
    import sys
    a = sys.argv[1:]
    if len(a) < 3 or a[0] != "license": sys.exit(__doc__.split("Rules")[0] + "\nusage: catalog_store.py license <status> \"<why>\" [--plan paid] [slug ...]")
    status, why, rest = a[1], a[2], a[3:]
    plan = None
    if "--plan" in rest: i = rest.index("--plan"); plan = rest[i + 1]; rest = rest[:i] + rest[i + 2:]
    for sl in rest or [t["slug"] for t in tracks()]:
        print(sl, "ok" if set_license(sl, status, "owner (shell)", why, plan) else "no such track")


# ---- files a listener may reach: only for published tracks (NAV-6 stage 2) ---------------------------------------------------------

def _asset(slug, role):
    return _tx(lambda c: c.execute(
        "SELECT a.id::text AS id, a.owner_id::text AS owner_id, a.storage_key, a.bytes, a.dominant_colour, t.slug FROM assets a JOIN tracks t ON t.id = a.owner_id "
        "WHERE a.owner_kind = 'track' AND t.slug = ? AND t.status = 'published' AND a.role = ? ORDER BY (strpos(a.storage_key, 'caption_timing') > 0) DESC, a.created_at LIMIT 1", (slug, role)).fetchone())   # caption_timing.json before caption_cues.json


def cover_asset(slug): return _asset(slug, "cover")
def audio_asset(slug): return _asset(slug, "audio")
def preview_asset(slug): return _asset(slug, "audio_preview")


def set_cover_facts(asset_id, width, height, colour):
    _tx(lambda c: c.execute("UPDATE assets SET width = ?, height = ?, dominant_colour = ? WHERE id = ?::uuid", (width, height, colour, asset_id)))


def add_preview_asset(audio_asset_id, track_id, key, size):
    _tx(lambda c: c.execute("INSERT INTO assets (owner_kind, owner_id, role, storage_key, mime, bytes, derived_from) VALUES ('track', ?::uuid, 'audio_preview', ?, 'audio/mpeg', ?, ?::uuid) "
                            "ON CONFLICT (owner_kind, owner_id, role, storage_key) DO NOTHING", (track_id, key, size, audio_asset_id)))


def cover_art():
    """{slug: dominant colour or None} for every published track that has a cover in the bucket: what a list needs to paint a placeholder and ask for /img."""
    rows = _tx(lambda c: c.execute("SELECT DISTINCT ON (t.slug) t.slug, a.dominant_colour FROM tracks t JOIN assets a ON a.owner_id = t.id AND a.owner_kind = 'track' AND a.role = 'cover' "
                                   "WHERE t.status = 'published' ORDER BY t.slug, a.created_at").fetchall())
    return {r["slug"]: r["dominant_colour"] for r in rows}


def track_ids(slugs):
    """{slug: id} for the published tracks among these slugs."""
    return {r["slug"]: r["id"] for r in _tx(lambda c: c.execute("SELECT slug, id::text AS id FROM tracks WHERE status = 'published' AND slug = ANY(?)", (list(slugs),)).fetchall())}


def tracks_by_ids(ids):
    """{id: {"slug", "title"}} for these track ids."""
    return {r["id"]: {"slug": r["slug"], "title": r["title"]} for r in _tx(lambda c: c.execute("SELECT id::text AS id, slug, title FROM tracks WHERE id = ANY(?::uuid[])", (list(ids),)).fetchall())}


def album_ids(slugs):
    return {r["slug"]: r["id"] for r in _tx(lambda c: c.execute("SELECT slug, id::text AS id FROM albums WHERE status = 'published' AND slug = ANY(?)", (list(slugs),)).fetchall())}


def albums_by_ids(ids):
    return {r["id"]: {"slug": r["slug"], "title": r["title"]} for r in _tx(lambda c: c.execute("SELECT id::text AS id, slug, title FROM albums WHERE id = ANY(?::uuid[])", (list(ids),)).fetchall())}


def artist_id():
    return _tx(lambda c: str(_artist(c)))


def play_key(slug, confirmed_only=False):
    """The bucket key of the full audio of a track a person may play: published, and not marked not_allowed. A listener (confirmed_only) gets only licence-confirmed tracks; the owner hears everything
    published. The plan's say (entitlements.can) is asked by the caller."""
    r = _tx(lambda c: c.execute("SELECT license_status FROM tracks WHERE slug = ? AND status = 'published'", (slug,)).fetchone())
    ok = r and r["license_status"] != "not_allowed" and (not confirmed_only or r["license_status"] == "confirmed")
    a = audio_asset(slug) if ok else None
    return a["storage_key"] if a else None


def _visible(all_licences):
    """SQL for what a person may see: published tracks, and for a listener only those with a confirmed licence (FR-017)."""
    return "t.status = 'published'" + ("" if all_licences else " AND t.license_status = 'confirmed'")


def browse(all_licences=False, album=None, language=None, genre=None, limit=200, offset=0):
    """Published tracks for Browse and the Library, newest first, with album, language, genre and whether a cover exists. Filters narrow it; a listener never sees an unconfirmed track."""
    q = ("SELECT t.slug, t.title, t.language, t.license_status AS licence, t.published_at, "
         "COALESCE((SELECT g.name FROM track_genres tg JOIN genres g ON g.id = tg.genre_id WHERE tg.track_id = t.id LIMIT 1), '') AS genre, "
         "COALESCE((SELECT json_agg(json_build_object('slug', a.slug, 'title', a.title) ORDER BY a.title) FROM album_tracks at JOIN albums a ON a.id = at.album_id WHERE at.track_id = t.id AND a.status = 'published'), '[]'::json) AS albums, "
         "EXISTS (SELECT 1 FROM assets x WHERE x.owner_id = t.id AND x.owner_kind = 'track' AND x.role = 'cover') AS has_cover, "
         "(SELECT x.dominant_colour FROM assets x WHERE x.owner_id = t.id AND x.owner_kind = 'track' AND x.role = 'cover' LIMIT 1) AS colour "
         f"FROM tracks t WHERE {_visible(all_licences)} "
         "AND (?::text IS NULL OR t.language = ?::text) "
         "AND (?::text IS NULL OR EXISTS (SELECT 1 FROM track_genres tg JOIN genres g ON g.id = tg.genre_id WHERE tg.track_id = t.id AND g.name = ?::text)) "
         "AND (?::text IS NULL OR EXISTS (SELECT 1 FROM album_tracks at JOIN albums a ON a.id = at.album_id WHERE at.track_id = t.id AND a.slug = ?::text)) "
         "ORDER BY t.published_at DESC NULLS LAST, t.title, t.slug LIMIT ? OFFSET ?")
    rows = _tx(lambda c: c.execute(q, (language, language, genre, genre, album, album, max(1, min(int(limit), 500)), max(0, int(offset)))).fetchall())
    return [{"slug": r["slug"], "title": r["title"], "language": r["language"] or "", "genre": r["genre"], "albums": r["albums"], "licence": r["licence"],
             "art": {"colour": r["colour"]} if r["has_cover"] else None} for r in rows]


def filters(all_licences=False):
    """The values the Library can filter by: albums, languages and genres that at least one visible track has."""
    def go(c):
        v = _visible(all_licences)
        albums = c.execute(f"SELECT DISTINCT a.slug, a.title FROM albums a JOIN album_tracks at ON at.album_id = a.id JOIN tracks t ON t.id = at.track_id WHERE a.status = 'published' AND {v} ORDER BY a.title").fetchall()
        langs = c.execute(f"SELECT DISTINCT t.language FROM tracks t WHERE {v} AND t.language IS NOT NULL ORDER BY 1").fetchall()
        genres = c.execute(f"SELECT DISTINCT g.name FROM genres g JOIN track_genres tg ON tg.genre_id = g.id JOIN tracks t ON t.id = tg.track_id WHERE {v} ORDER BY 1").fetchall()
        return {"albums": [dict(a) for a in albums], "languages": [r["language"] for r in langs], "genres": [r["name"] for r in genres]}
    return _tx(go)


def track_view(slug, all_licences=False):
    """One track for its page: title, language, genre, albums, the plain lyrics, whether timed lyrics exist, and its cover. None when it is not visible to this person."""
    hit = [t for t in browse(all_licences, limit=500) if t["slug"] == slug]
    if not hit: return None
    lyrics = _tx(lambda c: c.execute("SELECT lyrics_text FROM tracks WHERE slug = ?", (slug,)).fetchone()["lyrics_text"])
    return {**hit[0], "lyrics": lyrics, "timed": timed_asset(slug) is not None}


def timed_asset(slug): return _asset(slug, "lyrics_timed")


# ---- share links (FR-025) ---------------------------------------------------------------------------------------------------------

def create_share(slug, by, start_ms=0):
    """A new link to a published track with a confirmed licence. Returns the token."""
    if int(start_ms) < 0: raise ValueError("start must be zero or more milliseconds")
    def go(c):
        t = c.execute("SELECT id::text AS id, status, license_status FROM tracks WHERE slug = ?", (slug,)).fetchone()
        if not t or t["status"] != "published": raise LookupError("no such published track")
        if t["license_status"] != "confirmed": raise ValueError("this track's licence is not confirmed, so it cannot be shared yet")
        tok = secrets.token_urlsafe(16)
        c.execute("INSERT INTO share_links (token, subject_kind, subject_id, created_by, start_ms) VALUES (?, 'track', ?::uuid, ?, ?)", (tok, t["id"], str(by), int(start_ms)))
        return tok
    return _tx(go)


def revoke_share(token, by, owner=False):
    """Stop a link working. A person may revoke their own links; the owner any. True when a live link was revoked."""
    return _tx(lambda c: c.execute("UPDATE share_links SET revoked_at = now() WHERE token = ? AND revoked_at IS NULL AND (created_by = ? OR ?) RETURNING token", (token, str(by), bool(owner))).fetchone()) is not None


def shares(by=None):
    rows = _tx(lambda c: c.execute("SELECT s.token, t.slug, t.title, s.start_ms, s.created_at, s.revoked_at, s.opens, s.created_by FROM share_links s JOIN tracks t ON t.id = s.subject_id "
                                   "WHERE (?::text IS NULL OR s.created_by = ?::text) ORDER BY s.created_at DESC", (by, by)).fetchall())
    return [{**r, "created_at": r["created_at"].isoformat(), "revoked_at": r["revoked_at"].isoformat() if r["revoked_at"] else None} for r in rows]


def open_share(token, count=False):
    """The track behind a live link, or None (unknown, revoked, expired, or the track no longer qualifies). count=True records an open."""
    def go(c):
        r = c.execute("SELECT s.start_ms, t.slug, t.title, t.license_status, t.status FROM share_links s JOIN tracks t ON t.id = s.subject_id "
                      "WHERE s.token = ? AND s.revoked_at IS NULL AND (s.expires_at IS NULL OR s.expires_at > now())", (token,)).fetchone()
        if not r or r["status"] != "published" or r["license_status"] != "confirmed": return None
        if count: c.execute("UPDATE share_links SET opens = opens + 1 WHERE token = ?", (token,))
        return {"slug": r["slug"], "title": r["title"], "start_ms": r["start_ms"]}
    return _tx(go)
