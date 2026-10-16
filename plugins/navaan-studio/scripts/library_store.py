"""library_store.py  what a listener keeps: playlists, saved songs and albums, follows, and their plays.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: NAV-7 (FR-012, FR-019). Every function takes the person's user id and scopes by it, so one person can never read or change another's data (SC-005): a playlist that is not yours is
"not found", never "forbidden". The playlist limit comes from entitlements.can(), never from a number here.

Rules
  a playlist's order is a fractional text key (positions.between): inserting or moving rewrites one row; two people saving at once collide on the unique key, and the loser recomputes from what is there now
  a track can be in a playlist once; only published tracks can be added
  plays are rows in monthly partitions, so removing old detail is dropping a partition
"""
import datetime
import navaan_common as C
import pgconn, positions, entitlements, catalog_store as K
import navaan_log as L
LOG = L.get("library")
_conn, _tx = pgconn.make("library")
MAX_KEY = 24   # an appended key longer than this renumbers the list


class LimitError(Exception):
    """The plan's limit is reached; .decision says which and what to show."""
    def __init__(self, decision): super().__init__(decision.message()); self.decision = decision


def _owned(c, uid, pid, lock=False):
    r = c.execute("SELECT id, name, description, visibility FROM playlists WHERE id = ?::uuid AND user_id = ?::uuid" + (" FOR UPDATE" if lock else ""), (pid, uid)).fetchone()
    if not r: raise LookupError("no such playlist")
    return r


def playlists(uid):
    return _tx(lambda c: [{**r, "id": str(r["id"]), "updated_at": r["updated_at"].isoformat()} for r in c.execute(
        "SELECT p.id, p.name, p.description, p.visibility, p.updated_at, (SELECT count(*) FROM playlist_tracks t WHERE t.playlist_id = p.id) AS tracks FROM playlists p WHERE p.user_id = ?::uuid ORDER BY p.updated_at DESC", (uid,)).fetchall()])


def create_playlist(user, name, description="", visibility="private"):
    """user is a session ({user_id, roles}). Raises LimitError when the plan's playlist limit is reached."""
    name = " ".join(str(name or "").split())
    if not 1 <= len(name) <= 100: raise ValueError("a playlist needs a name of up to 100 characters")
    if visibility not in ("private", "unlisted", "public"): raise ValueError("visibility is private, unlisted or public")
    uid = user["user_id"]
    def go(c):
        have = c.execute("SELECT count(*) AS n FROM playlists WHERE user_id = ?::uuid", (uid,)).fetchone()["n"]
        d = entitlements.can(user, "playlists.max", used=have)
        if not d: raise LimitError(d)
        return str(c.execute("INSERT INTO playlists (user_id, name, description, visibility) VALUES (?::uuid, ?, ?, ?) RETURNING id", (uid, name, str(description or "")[:500], visibility)).fetchone()["id"])
    return _tx(go)


def get_playlist(uid, pid):
    def go(c):
        p = _owned(c, uid, pid)
        rows = c.execute("SELECT track_id::text AS track_id, position, added_at FROM playlist_tracks WHERE playlist_id = ?::uuid ORDER BY position", (pid,)).fetchall()
        return p, rows
    p, rows = _tx(go)
    info = K.tracks_by_ids([r["track_id"] for r in rows]) if rows else {}
    return {"id": str(p["id"]), "name": p["name"], "description": p["description"], "visibility": p["visibility"],
            "tracks": [{"slug": info[r["track_id"]]["slug"], "title": info[r["track_id"]]["title"], "position": r["position"]} for r in rows if r["track_id"] in info]}


def shared_playlist(pid):
    """A playlist anyone with its link may open: unlisted or public only (a private one is None), with only published songs. Read only."""
    import re
    if not re.match(r"^[0-9a-f-]{36}$", str(pid or "")): return None
    def go(c):
        p = c.execute("SELECT id, name, description, visibility FROM playlists WHERE id = ?::uuid AND visibility IN ('unlisted', 'public')", (pid,)).fetchone()
        return (p, _keys(c, pid)) if p else (None, [])
    p, rows = _tx(go)
    if not p: return None
    info = K.tracks_by_ids([r["track_id"] for r in rows]) if rows else {}
    return {"id": str(p["id"]), "name": p["name"], "description": p["description"], "visibility": p["visibility"],
            "tracks": [{"slug": info[r["track_id"]]["slug"], "title": info[r["track_id"]]["title"], "position": r["position"]} for r in rows if r["track_id"] in info]}


def update_playlist(uid, pid, name=None, description=None, visibility=None):
    def go(c):
        p = _owned(c, uid, pid)
        n = " ".join(str(name).split()) if name is not None else p["name"]
        if not 1 <= len(n) <= 100: raise ValueError("a playlist needs a name of up to 100 characters")
        v = visibility if visibility is not None else p["visibility"]
        if v not in ("private", "unlisted", "public"): raise ValueError("visibility is private, unlisted or public")
        c.execute("UPDATE playlists SET name = ?, description = ?, visibility = ?, updated_at = now() WHERE id = ?::uuid", (n, str(description if description is not None else p["description"])[:500], v, pid))
    _tx(go)


def delete_playlist(uid, pid):
    def go(c): _owned(c, uid, pid); c.execute("DELETE FROM playlists WHERE id = ?::uuid", (pid,))
    _tx(go)


def _keys(c, pid):
    return c.execute("SELECT t.track_id::text AS track_id, t.position FROM playlist_tracks t WHERE t.playlist_id = ?::uuid ORDER BY t.position", (pid,)).fetchall()


def _place(rows, slug_of, after):
    """The key for a new place: after the item `after` (a slug), at the top when after is the empty string, at the end when None."""
    if after is None: return positions.between(rows[-1]["position"] if rows else None, None)
    if after == "": return positions.between(None, rows[0]["position"] if rows else None)
    idx = next((i for i, r in enumerate(rows) if slug_of.get(r["track_id"]) == after), None)
    if idx is None: raise ValueError("no such track in this playlist to put it after")
    return positions.between(rows[idx]["position"], rows[idx + 1]["position"] if idx + 1 < len(rows) else None)


def _write(uid, pid, fn, tries=6):
    """Run fn(c, rows) -> None inside one transaction with the playlist row locked. The retry on a key collision is a second line of defence (the lock should make it unreachable)."""
    import psycopg
    for i in range(tries):
        try:
            def go(c):
                _owned(c, uid, pid, lock=True); rows = _keys(c, pid); fn(c, rows)   # the row lock makes writers to one playlist take turns, so each sees the others' keys
                c.execute("UPDATE playlists SET updated_at = now() WHERE id = ?::uuid", (pid,))
                long = c.execute("SELECT 1 FROM playlist_tracks WHERE playlist_id = ?::uuid AND length(position) > ? LIMIT 1", (pid, MAX_KEY)).fetchone()
                if long:   # appending always lengthens the key; renumber the whole list with short keys, in the same transaction
                    ids = [r["track_id"] for r in _keys(c, pid)]
                    c.execute("UPDATE playlist_tracks SET position = '~' || position WHERE playlist_id = ?::uuid", (pid,))   # out of the way of the unique key
                    for tid, pos in zip(ids, positions.spread(len(ids))): c.execute("UPDATE playlist_tracks SET position = ? WHERE playlist_id = ?::uuid AND track_id = ?::uuid", (pos, pid, tid))
            return _tx(go)
        except psycopg.errors.UniqueViolation:
            if i == tries - 1: raise
    return None


def add_track(uid, pid, slug, after=None):
    ids = K.track_ids([slug])
    if slug not in ids: raise ValueError("no such published track")
    tid = ids[slug]
    def fn(c, rows):
        if any(r["track_id"] == tid for r in rows): raise ValueError("this track is already in the playlist")
        slugs = {k: v["slug"] for k, v in K.tracks_by_ids([r["track_id"] for r in rows]).items()} if after else {}
        c.execute("INSERT INTO playlist_tracks (playlist_id, track_id, position, added_by) VALUES (?::uuid, ?::uuid, ?, ?::uuid)", (pid, tid, _place(rows, slugs, after), uid))
    _write(uid, pid, fn)


def remove_track(uid, pid, slug):
    tid = next(iter(K.track_ids([slug]).values()), None)
    def fn(c, rows):
        if not tid or not c.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?::uuid AND track_id = ?::uuid RETURNING 1", (pid, tid)).fetchone(): raise LookupError("that track is not in the playlist")
    _write(uid, pid, fn)


def move_track(uid, pid, slug, after):
    """Put the track after another one (a slug), at the top (""), or at the end (None)."""
    tid = next(iter(K.track_ids([slug]).values()), None)
    def fn(c, rows):
        if not any(r["track_id"] == tid for r in rows): raise LookupError("that track is not in the playlist")
        rest = [r for r in rows if r["track_id"] != tid]
        slugs = K.tracks_by_ids([r["track_id"] for r in rest]) if after else {}
        key = _place(rest, {k: v["slug"] for k, v in slugs.items()}, after)
        c.execute("UPDATE playlist_tracks SET position = ? WHERE playlist_id = ?::uuid AND track_id = ?::uuid", (key, pid, tid))
    _write(uid, pid, fn)


# ---- saved songs and albums, follows ----------------------------------------------------------------------------------------------

def save(uid, kind, slug, on=True):
    if kind not in ("track", "album"): raise ValueError("kind is track or album")
    ids = (K.track_ids if kind == "track" else K.album_ids)([slug])
    if slug not in ids: raise ValueError(f"no such published {kind}")
    t, col = ("saved_tracks", "track_id") if kind == "track" else ("saved_albums", "album_id")
    if on: _tx(lambda c: c.execute(f"INSERT INTO {t} (user_id, {col}) VALUES (?::uuid, ?::uuid) ON CONFLICT DO NOTHING", (uid, ids[slug])))
    else: _tx(lambda c: c.execute(f"DELETE FROM {t} WHERE user_id = ?::uuid AND {col} = ?::uuid", (uid, ids[slug])))


def follow(uid, on=True):
    """Follow (or stop following) the artist: NAVAAN is the only one for now."""
    a = K.artist_id()
    if on: _tx(lambda c: c.execute("INSERT INTO follows (user_id, artist_id) VALUES (?::uuid, ?::uuid) ON CONFLICT DO NOTHING", (uid, a)))
    else: _tx(lambda c: c.execute("DELETE FROM follows WHERE user_id = ?::uuid AND artist_id = ?::uuid", (uid, a)))


def library(uid):
    def go(c):
        return ([r["track_id"] for r in c.execute("SELECT track_id::text AS track_id FROM saved_tracks WHERE user_id = ?::uuid ORDER BY saved_at DESC", (uid,)).fetchall()],
                [r["album_id"] for r in c.execute("SELECT album_id::text AS album_id FROM saved_albums WHERE user_id = ?::uuid ORDER BY saved_at DESC", (uid,)).fetchall()],
                c.execute("SELECT count(*) AS n FROM follows WHERE user_id = ?::uuid", (uid,)).fetchone()["n"] > 0)
    t, a, f = _tx(go); ti = K.tracks_by_ids(t) if t else {}; ai = K.albums_by_ids(a) if a else {}
    return {"tracks": [ti[x] for x in t if x in ti], "albums": [ai[x] for x in a if x in ai], "following": f}


# ---- plays (FR-019) ---------------------------------------------------------------------------------------------------------------

def _month(d): return d.replace(day=1)


_PARTS = set()   # (schema-bearing connection root, month) already ensured in this process, so a play does not run DDL every time


def ensure_partition(day):
    """The monthly partition holding `day` (a date), created if it does not exist yet. Only the first call per month and process touches the database."""
    m = _month(day); key = (C.songs_root(), m)
    if key in _PARTS: return
    n = datetime.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    _tx(lambda c: c.execute(f"CREATE TABLE IF NOT EXISTS play_events_{m.year}_{m.month:02d} PARTITION OF play_events FOR VALUES FROM ('{m}') TO ('{n}')"))
    _PARTS.add(key)


def record_play(uid, slug, source_kind=None, source_id=None, device=None, country=None):
    """A play started (the link was asked for). Returns False when the track is unknown."""
    tid = next(iter(K.track_ids([slug]).values()), None)
    if not tid: return False
    today = datetime.date.today(); ensure_partition(today); ensure_partition(_month(today) + datetime.timedelta(days=32))
    _tx(lambda c: c.execute("INSERT INTO play_events (user_id, track_id, source_kind, source_id, device, country) VALUES (?::uuid, ?::uuid, ?, ?, ?, ?)", (uid, tid, source_kind, source_id, device, country)))
    return True


def drop_old_partitions(keep_months=13, today=None):
    """Remove play detail older than keep_months by dropping whole monthly partitions. Returns the dropped names."""
    today = today or datetime.date.today(); cut = _month(today)
    for _ in range(keep_months): cut = _month(cut - datetime.timedelta(days=1))
    def go(c):
        names = [r["relname"] for r in c.execute("SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid JOIN pg_class p ON p.oid = i.inhparent WHERE p.relname = 'play_events' AND c.relname ~ '^play_events_[0-9]{4}_[0-9]{2}$'").fetchall()]
        dropped = []
        for n in names:
            y, m = int(n[-7:-3]), int(n[-2:])
            if datetime.date(y, m, 1) < cut: c.execute(f"DROP TABLE {n}"); dropped.append(n); _PARTS.discard((C.songs_root(), datetime.date(y, m, 1)))
        return dropped
    return _tx(go)


def rebuild_daily_stats(since):
    """Recompute play_stats_daily from the events for the days from `since` (a date)."""
    a = K.artist_id()
    def go(c):
        c.execute("DELETE FROM play_stats_daily WHERE day >= ?", (since,))
        c.execute("INSERT INTO play_stats_daily (artist_id, track_id, day, plays, listeners, ms_played) SELECT ?::uuid, track_id, (started_at AT TIME ZONE 'UTC')::date, count(*), count(DISTINCT user_id), COALESCE(sum(ms_played), 0) "
                  "FROM play_events WHERE started_at >= ? GROUP BY 2, 3", (a, since))
    _tx(go)


# ---- account data (FR-013) --------------------------------------------------------------------------------------------------------

def export(uid):
    pls = [get_playlist(uid, p["id"]) for p in playlists(uid)]
    lib = library(uid)
    plays = _tx(lambda c: c.execute("SELECT track_id::text AS track_id, started_at FROM play_events WHERE user_id = ?::uuid ORDER BY started_at DESC LIMIT 5000", (uid,)).fetchall())
    ti = K.tracks_by_ids({p["track_id"] for p in plays}) if plays else {}
    return {"playlists": pls, "saved_tracks": lib["tracks"], "saved_albums": lib["albums"], "following": lib["following"],
            "plays": [{"slug": ti.get(p["track_id"], {}).get("slug"), "at": p["started_at"].isoformat()} for p in plays]}


def erase(uid):
    """Delete everything the library holds about a person."""
    def go(c):
        for t in ("playlists", "saved_tracks", "saved_albums", "follows", "play_events"): c.execute(f"DELETE FROM {t} WHERE user_id = ?::uuid", (uid,))   # playlist tracks go with their playlist
    _tx(go)
