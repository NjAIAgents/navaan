#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-18
Last updated: 2026-10-18
Description: first-party visitor analytics of the public site (NAV-33): page views, plays with seconds listened and account-pitch clicks, cookieless and anonymous.

  record(kind, slug, src, referrer, ua, ip, seconds, own_host)   one event from the public site (bots are skipped); returns True when kept
  summary(days)                                                 what the Visitors tab shows: today, 7 and 30 days, then songs, sources and devices over `days`

Unique visitors are counted per day with a one-way hash of address and browser. Its salt is random, lives only in this process's memory and is
replaced every day, so a visitor cannot be followed across days or traced back; the address and the browser string are never stored.
"""
import os, re, hmac, hashlib, datetime, threading
from urllib.parse import urlparse
import catalog_store as K

KINDS = ("view", "play", "pitch")
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
# A tag on links we place ourselves (?src=yt) wins over the referrer: apps such as WhatsApp and Instagram send no referrer at all.
TAGS = {"yt": "youtube", "youtube": "youtube", "ig": "instagram", "insta": "instagram", "instagram": "instagram", "wa": "whatsapp", "whatsapp": "whatsapp",
        "fb": "facebook", "facebook": "facebook", "x": "x", "tw": "x", "twitter": "x", "email": "email", "mail": "email"}
HOSTS = (("whatsapp", "whatsapp"), ("instagram", "instagram"), ("youtube", "youtube"), ("youtu.be", "youtube"), ("facebook", "facebook"), ("fb.", "facebook"),
         ("t.co", "x"), ("twitter", "x"), ("x.com", "x"), ("google.", "search"), ("bing.", "search"), ("duckduckgo", "search"), ("yahoo.", "search"), ("ecosia", "search"))
BOTS = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp/|headless|lighthouse", re.I)
_SALT = {"day": None, "key": b""}; _LOCK = threading.Lock()   # ponytail: per process; a restart mid-day starts a new salt, so that day's uniques may count someone twice


def today(): return datetime.datetime.now(datetime.timezone.utc).date()


def source(src, referrer, own_host=""):
    """Where the visit came from: our own ?src= tag, else the referring site, else direct."""
    t = TAGS.get(str(src or "").strip().lower()[:20])
    if t: return t
    host = (urlparse(str(referrer or "")).hostname or "").lower()
    if not host or (own_host and host == own_host.split(":")[0].lower()): return "direct"
    return next((name for frag, name in HOSTS if frag in host), "other")


def device(ua):
    """mobile, tablet or desktop from the browser string; None for a bot or a link preview (not counted)."""
    ua = str(ua or "")
    if not ua or BOTS.search(ua): return None
    if re.search(r"ipad|tablet", ua, re.I): return "tablet"
    return "mobile" if re.search(r"mobi|iphone|android", ua, re.I) else "desktop"


def visitor(ip, ua, day=None):
    """16 hex characters that stay the same for one address and browser on one day only."""
    day = day or today()
    with _LOCK:
        if _SALT["day"] != day: _SALT.update(day=day, key=os.urandom(32))
        key = _SALT["key"]
    return hmac.new(key, f"{ip}|{ua}".encode(), hashlib.sha256).hexdigest()[:16]


def record(kind, slug=None, src=None, referrer=None, ua=None, ip="", seconds=0, own_host=""):
    if kind not in KINDS: raise ValueError("kind is view, play or pitch")
    dev = device(ua)
    if dev is None: return False
    slug = str(slug or "").strip().lower() or None
    if slug and not SLUG.match(slug): raise ValueError("bad slug")
    if kind == "play" and not slug: raise ValueError("a play needs the song")
    try: secs = max(0, min(3600, round(float(seconds or 0))))
    except (TypeError, ValueError): secs = 0   # expected: a browser sent no number, count the event without seconds
    d = today()
    K._tx(lambda c: c.execute("INSERT INTO site_events (day, kind, slug, source, device, visitor, seconds) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (d, kind, slug, source(src, referrer, own_host), dev, visitor(ip, ua, d), secs)))
    return True


def summary(days=30):
    """Totals for today, 7 and 30 days; per song, source and device and per day over `days` (1 to 90)."""
    days = max(1, min(90, int(days or 30))); d0 = today()
    since = lambda n: d0 - datetime.timedelta(days=n - 1)
    TOT = ("SELECT count(*) FILTER (WHERE kind = 'view') AS views, count(*) FILTER (WHERE kind = 'play') AS plays, coalesce(sum(seconds) FILTER (WHERE kind = 'play'), 0) AS seconds, "
           "count(*) FILTER (WHERE kind = 'pitch') AS pitch, count(DISTINCT (day, visitor)) AS visitors FROM site_events WHERE day >= ?")

    def go(c):
        tot = {k: dict(c.execute(TOT, (since(n),)).fetchone()) for k, n in (("today", 1), ("d7", 7), ("d30", 30))}
        s = since(days)
        songs = [dict(r) for r in c.execute(
            "SELECT e.slug, max(t.title) AS title, count(*) FILTER (WHERE e.kind = 'view') AS views, count(*) FILTER (WHERE e.kind = 'play') AS plays, "
            "coalesce(sum(e.seconds) FILTER (WHERE e.kind = 'play'), 0) AS seconds, count(DISTINCT (e.day, e.visitor)) AS visitors "
            "FROM site_events e LEFT JOIN tracks t ON t.slug = e.slug WHERE e.day >= ? AND e.slug IS NOT NULL GROUP BY e.slug ORDER BY plays DESC, views DESC LIMIT 50", (s,)).fetchall()]
        by = lambda col: [dict(r) for r in c.execute(f"SELECT {col} AS name, count(*) FILTER (WHERE kind = 'view') AS views, count(*) FILTER (WHERE kind = 'play') AS plays, "
                                                     f"count(DISTINCT (day, visitor)) AS visitors FROM site_events WHERE day >= ? GROUP BY {col} ORDER BY visitors DESC, views DESC", (s,)).fetchall()]
        daily = [{**dict(r), "day": r["day"].isoformat()} for r in c.execute(
            "SELECT day, count(*) FILTER (WHERE kind = 'view') AS views, count(*) FILTER (WHERE kind = 'play') AS plays, count(DISTINCT visitor) AS visitors "
            "FROM site_events WHERE day >= ? GROUP BY day ORDER BY day", (s,)).fetchall()]
        return {"days": days, "totals": tot, "songs": songs, "sources": by("source"), "devices": by("device"), "daily": daily}
    return K._tx(go)
