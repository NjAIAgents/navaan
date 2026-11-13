#!/usr/bin/env python3
"""album_release.py  only an album is released, and every song in it with it (spec 003).

Author: Navjyot Nishant
Created: 2026-11-13
Last updated: 2026-11-13
Description: readiness, the owner's confirm (now or at a time), the release itself and a retry per song.

Release = the full version of each song goes public: the album and its tracks are listed on navaan.online in one transaction, and each song's
full YouTube video is handed to the publishing scheduler (publish_schedule) at that moment, which brings its retries (3, 10 minutes apart), the 12 h grace and "missed".
The owner's confirm is the approval of each song's go_public (via "album release <album> by <who>"): one press for the album, never one per song (FR-003, FR-013).

  status(album)                          readiness and, per song, where it is public (no change)
  confirm(album, songs, by, at=None)     the owner's Release: refused unless `songs` is the album's list as it is now and every song is ready; at in the future schedules it
  release(album)                         the release itself (called by confirm now, and by tick for a scheduled album); idempotent
  retry(album, song)                     another 3 tries for a song whose full video failed to go public
  cancel(album, by) / disarm(album)      a scheduled release back to a draft (by the owner, or because its song list changed)
  tick(at)                               the scheduler's minute: release the scheduled albums that are due (publish_schedule.loop calls it)
Songs public before this rule stay public: the migration marks their tracks (public_before_albums), and a public full video counts as released (navaan_common.released).
"""
import datetime, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
import catalog_store as K
LOG = L.get("album_release")

UTC = datetime.timezone.utc
NOT_IN_RELEASE = ("youtube_short", "short_public", "instagram_caption", "publish_instagram", "cleanup")   # teasers and housekeeping: a release does not wait for them


class NotReady(ValueError):
    def __init__(self, state): super().__init__("not every song is ready to release"); self.state = state


def now(): return datetime.datetime.now(UTC)
def iso(t): return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _album(slug):
    a = K._tx(lambda c: c.execute("SELECT id::text AS id, slug, title, status, release_at, announced, release FROM albums WHERE slug = ?", (slug,)).fetchone())
    if not a: raise LookupError("no such album")
    a["release_at"] = iso(a["release_at"]) if a["release_at"] else None
    a["songs"] = [r["slug"] for r in K._tx(lambda c: c.execute("SELECT t.slug FROM album_tracks at JOIN tracks t ON t.id = at.track_id WHERE at.album_id = ?::uuid ORDER BY at.position", (a["id"],)).fetchall())]
    return a


def _why_not(slug):
    """Why one song cannot be released yet, or None. Everything before going public must be done and approved (the teasers excepted)."""
    import navaan as N
    m = N.meta(slug)
    if C.released(m): return None
    rows, _ = N.plan(slug)
    for r in rows:
        if r["id"] == "go_public": return None
        if r["id"] in NOT_IN_RELEASE or r.get("notused"): continue
        if r.get("needs_gate"): return f"gate {r['needs_gate']} not approved"
        if r["status"] != "done": return f"{r['label']}: not done yet"
    return "no step to make it public"


def _song_state(slug, site):
    m = C.item_load(slug, {}); full, _ = C.youtube_split(m); sc = m.get("schedule") or {}
    att = (sc.get("attempts") or {}).get("go_public") or {}
    if full and all(i.get("privacy") == "public" for i in full): yt = "public"
    elif (sc.get("missed") or {}).get("go_public") or att.get("n", 0) >= 3: yt = "failed"
    elif att.get("n"): yt = "retrying"
    else: yt = "private"
    return {"youtube": yt, "site": "listed" if site == "published" else "unlisted", "attempts": att.get("n", 0), "error": att.get("error", "")}


def status(album_slug):
    a = _album(album_slug)
    site = {r["slug"]: r["status"] for r in K._tx(lambda c: c.execute("SELECT slug, status FROM tracks WHERE slug = ANY(?)", (a["songs"],)).fetchall())}
    titles = {r["slug"]: r["title"] for r in K._tx(lambda c: c.execute("SELECT slug, title FROM tracks WHERE slug = ANY(?)", (a["songs"],)).fetchall())}
    songs = []
    for s in a["songs"]:
        why = None if a["status"] == "published" else _why_not(s)
        songs.append({"slug": s, "title": titles.get(s, s), "ready": why is None, "reason": why, **_song_state(s, site.get(s))})
    blocked = "Add at least one song" if not songs else None
    return {"album": a["slug"], "title": a["title"], "status": a["status"], "announced": a["announced"], "release_at": a["release_at"], "release": a["release"],
            "ready": bool(songs) and all(x["ready"] for x in songs) and a["status"] != "published", "songs": songs, "blocked": blocked or (a["release"] or {}).get("blocked")}


def confirm(album_slug, songs, by, at=None):
    """The owner's Release. songs must be the album's list as shown to them (a list that changed since is refused). at: ISO UTC; None or past = now."""
    a = _album(album_slug)
    if a["status"] == "published": raise ValueError("this album is already released")
    if list(songs) != a["songs"]: raise ValueError("the song list changed; review it again")
    st = status(album_slug)
    if not st["ready"]: raise NotReady(st)
    t = datetime.datetime.fromisoformat(str(at).replace("Z", "+00:00")).astimezone(UTC) if at else None
    later = bool(t and t > now() + datetime.timedelta(minutes=2))
    if t and not later and t > now(): raise ValueError("pick a time at least 2 minutes ahead, or release now")
    rec = {"confirmed_by": str(by), "confirmed_at": iso(now()), "songs": a["songs"], "via": "schedule" if later else "now"}
    K._tx(lambda c: c.execute("UPDATE albums SET status = ?, release_at = ?, release = ?, updated_at = now() WHERE id = ?::uuid",
                              ("scheduled" if later else a["status"], t if later else None, K.db_json(rec), a["id"])))
    for s in a["songs"]:
        def ok(m, s=s):
            if C.released(m): return
            m.setdefault("approvals", {})["go_public"] = {"at": iso(now()), "via": f"album release {album_slug} by {by}"}
            m.setdefault("history", []).append(f"{iso(now())} gate go_public approved with the release of album {album_slug} by {by}" + (f", for {iso(t)}" if later else ""))
        C.item_update(s, ok)
    L.event(LOG, "info", "album_release_confirmed", album=album_slug, by=str(by), songs=len(a["songs"]), at=iso(t) if later else "now")
    return release(album_slug) if not later else status(album_slug)


def release(album_slug):
    """List the album and its songs in one transaction, then mark each song released and hand its full video to the scheduler. Safe to run again."""
    a = _album(album_slug)
    def go(c):
        c.execute("UPDATE albums SET status = 'published', release_at = COALESCE(release_at, now()), release = release || ?, updated_at = now() WHERE id = ?::uuid",
                  (K.db_json({"released_at": iso(now())}), a["id"]))
        c.execute("UPDATE tracks SET status = 'published', published_at = COALESCE(published_at, now()), updated_at = now() WHERE id IN (SELECT track_id FROM album_tracks WHERE album_id = ?::uuid)", (a["id"],))
        K._reindex_album(c, a["id"])
    if a["status"] != "published": K._tx(go)
    _finish(album_slug, a["songs"])
    L.event(LOG, "info", "album_released", album=album_slug, songs=len(a["songs"]))
    return status(album_slug)


def _finish(album_slug, songs):
    """After the album is listed: each song is released and its full video goes public through the scheduler, now."""
    t = iso(now())
    for s in songs:
        def mark(m, s=s):
            if C.released(m): return
            m["release"] = {"album": album_slug, "at": t, "by": "album release"}
            sc = m.setdefault("schedule", {}); sc["youtube_at"] = t; sc["done"] = False; sc.setdefault("created_at", t)
            for k in ("attempts", "missed", "blocked"): (sc.get(k) or {}).pop("go_public", None)
            m.setdefault("history", []).append(f"{t} released with album {album_slug}")
        C.item_update(s, mark)
        try: K.sync_item(s)   # its search entry; the listing itself is already in the album's transaction
        except Exception: L.exc(LOG, "album_release_sync_failed", album=album_slug, item=s)   # listed already; the next sync adds the search entry


def retry(album_slug, song):
    a = _album(album_slug)
    if a["status"] != "published" or song not in a["songs"]: raise ValueError("only a song of a released album can be retried")
    def go(m):
        sc = m.setdefault("schedule", {}); sc["done"] = False; sc["youtube_at"] = iso(now())
        for k in ("attempts", "missed", "blocked"): (sc.get(k) or {}).pop("go_public", None)
        m.setdefault("history", []).append(f"{iso(now())} going public tried again (album {album_slug})")
    C.item_update(song, go)
    return status(album_slug)


GRACE_H = 12   # as publish_schedule: a release more than this late is missed, and the owner picks again


def _revoke(album_slug, songs, why):
    """Take back the go_public approvals a confirm gave (only those, and only for songs not yet released)."""
    for s in songs:
        def go(m, s=s):
            ap = m.get("approvals") or {}
            if C.released(m) or not str((ap.get("go_public") or {}).get("via", "")).startswith(f"album release {album_slug} "): return
            ap.pop("go_public", None); m.setdefault("history", []).append(f"{iso(now())} gate go_public revoked: {why}")
        try: C.item_update(s, go)
        except Exception: L.soft(LOG, "album_revoke_failed", album=album_slug, item=s)   # a song folder gone: nothing to revoke there


def cancel(album_slug, by, why=None):
    """A scheduled (or missed) release back to a draft; the approvals its confirm gave are taken back."""
    a = _album(album_slug)
    if a["status"] not in ("scheduled", "missed"): raise ValueError("only a scheduled or missed release can be cancelled")
    why = why or f"release of album {album_slug} cancelled by {by}"
    K._tx(lambda c: c.execute("UPDATE albums SET status = 'draft', release_at = NULL, release = release || ?, updated_at = now() WHERE id = ?::uuid",
                              (K.db_json({"cancelled_at": iso(now()), "cancelled_by": str(by), "why": why, "blocked": None}), a["id"])))
    _revoke(album_slug, (a["release"] or {}).get("songs") or a["songs"], why)
    L.event(LOG, "info", "album_release_cancelled", album=album_slug, by=str(by), why=why)
    return status(album_slug)


def disarm(album_slug):
    """The song list of a scheduled album changed since the owner confirmed it: back to a draft, to be confirmed again (FR-012). True when it did."""
    a = _album(album_slug)
    if a["status"] != "scheduled" or set(a["songs"]) == set((a["release"] or {}).get("songs") or []): return False   # a new order alone is not a new list
    cancel(album_slug, "studio", "the song list changed after the release was confirmed; confirm it again"); return True


def tick(at=None):
    """Release the scheduled albums that are due. Not ready yet: wait and say why, up to GRACE_H hours; later: missed. Returns [(album, what happened)]."""
    n = at or now(); out = []
    due = K._tx(lambda c: c.execute("SELECT slug, release_at FROM albums WHERE status = 'scheduled' AND release_at <= ?", (n,)).fetchall())
    for r in due:
        s = r["slug"]
        try:
            if disarm(s): out.append((s, "disarmed")); continue
            if n - r["release_at"] > datetime.timedelta(hours=GRACE_H):
                K._tx(lambda c: c.execute("UPDATE albums SET status = 'missed', release = release || ?, updated_at = now() WHERE slug = ?", (K.db_json({"missed_at": iso(n)}), s)))
                L.event(LOG, "warning", "album_release_missed", album=s); out.append((s, "missed")); continue
            st = status(s)
            if st["ready"]: release(s); out.append((s, "released")); continue
            why = st["blocked"] or next((f"{x['title']}: {x['reason']}" for x in st["songs"] if not x["ready"]), "not ready")
            if (st.get("release") or {}).get("blocked") != why:
                K._tx(lambda c: c.execute("UPDATE albums SET release = release || ? WHERE slug = ?", (K.db_json({"blocked": why}), s)))
            out.append((s, "waiting: " + why))
        except Exception: L.exc(LOG, "album_tick_failed", album=s); out.append((s, "error"))   # one album must not stop the others, nor the songs' own schedule
    return out


def missed():
    """Albums whose scheduled release was missed, for the alerts: [{slug, title}]."""
    return K._tx(lambda c: c.execute("SELECT slug, title FROM albums WHERE status = 'missed' ORDER BY title").fetchall())
