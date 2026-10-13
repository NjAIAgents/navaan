#!/usr/bin/env python3
"""yt_hashtags.py  collect public Shorts that use your hashtags, so the best-time card has a signal before your own videos have history.

  python3 yt_hashtags.py collect [--account music|inspiration] [--tags healing,lettinggo] [--days 30] [--force]
  python3 yt_hashtags.py tags    [--account ...]      show which hashtags would be searched

Read only. It runs a public search for each hashtag (Shorts length, published in the last 30 days), reads the publish time, length and view
count of each result, and stores them in the table yt_hashtag_posts. Your own channel is left out.

Which hashtags: --tags, else navaan.config.json analytics.yt_hashtags.<account> (a list), else the hashtags that appear most often in the
descriptions of your own videos (youtube.json), leaving out generic ones like #Shorts and your own channel name. Up to 4 picked
automatically, up to 6 from a list you set.
Quota: a search costs 100 units and reading details about 1, so each hashtag costs about 102 of the 10,000 free units a day (4 about 410, 6 about 610).
It runs at most once every 6 days per account unless --force.
"""
import os, sys, re, json, glob, argparse, datetime, collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analytics_db as db

UTC = datetime.timezone.utc
SCHEMA = """CREATE TABLE IF NOT EXISTS yt_hashtag_posts (
  video_id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  tag TEXT NOT NULL,
  channel_id TEXT,
  published_at TEXT,
  duration_s INTEGER,
  views INTEGER,
  likes INTEGER,
  comments INTEGER,
  captured_at TEXT NOT NULL
)"""
GENERIC = {"shorts", "short", "youtubeshorts", "viral", "fyp", "trending", "subscribe", "reels", "video", "new"}
MAX_TAGS, AUTO_TAGS, WINDOW_DAYS, SHORT_MAX_S, MIN_GAP_DAYS = 6, 4, 30, 180, 6
HASHTAG = re.compile(r"#([A-Za-z][A-Za-z0-9_]{2,40})")


def ensure(conn):
    conn.execute(SCHEMA)
    conn.commit()


def parse_duration(s):
    """ISO 8601 duration such as PT45S or PT1M5S to seconds. Anything else gives 0."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, sec = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + sec


def brand_words(conn, label):
    """Your own channel name and handle without punctuation. A hashtag equal to one finds your own content, so it is not searched."""
    r = db.one(conn, "SELECT title, handle FROM yt_channels WHERE label = " + db.PH, (label,)) or {}
    return {re.sub(r"[^a-z0-9]", "", str(x or "").lower()) for x in (r.get("title"), (r.get("handle") or "").lstrip("@"), label)} - {""}


def own_tags(conn, label, limit=AUTO_TAGS):
    """Most used hashtags in the descriptions of this account's videos, leaving out the channel's own brand name."""
    brand = brand_words(conn, label)
    rows = db.rows(conn, "SELECT v.slug FROM yt_videos v JOIN yt_channels c ON c.channel_id = v.channel_id WHERE c.label = " + db.PH + " AND v.slug IS NOT NULL", (label,))
    count = collections.Counter()
    try:
        import navaan_common as C
        root = C.songs_root()
    except (SystemExit, Exception):
        return []
    for r in rows:
        p = os.path.join(root, r["slug"], "youtube.json")
        try:
            desc = json.load(open(p, encoding="utf-8")).get("description") or ""
        except (OSError, ValueError):
            continue
        for t in {x.lower() for x in HASHTAG.findall(desc)}:
            if t not in GENERIC and re.sub(r"[^a-z0-9]", "", t) not in brand:
                count[t] += 1
    return [t for t, _ in count.most_common(limit)]


def pick_tags(conn, label, override=None):
    if override:
        tags = [t.strip().lstrip("#").lower() for t in override if t.strip()]
    else:
        try:
            from navaan_common import cfg
            tags = [str(t).strip().lstrip("#").lower() for t in (cfg("analytics.yt_hashtags." + label) or [])]
        except (SystemExit, Exception):
            tags = []
        tags = tags or own_tags(conn, label)
    return [t for t in dict.fromkeys(tags) if re.fullmatch(r"[a-z0-9_]{2,40}", t)][:MAX_TAGS]


def recently_collected(conn, label, now, gap_days=MIN_GAP_DAYS):
    r = db.one(conn, "SELECT MAX(captured_at) AS t FROM yt_hashtag_posts WHERE label = " + db.PH, (label,))
    if not r or not r["t"]:
        return False
    try:
        t = datetime.datetime.strptime(r["t"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return False
    return (now - t).total_seconds() < gap_days * 86400


def collect(conn, client, label, own_channel_id, tags, now=None, days=WINDOW_DAYS):
    """Search each hashtag and store Shorts-length results. Returns {"tags": n, "posts": n}. Lets ApiError through."""
    ensure(conn)
    now = now or datetime.datetime.now(UTC)
    after = (now - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    stored = 0
    for tag in tags:
        res = client.data("search", {"part": "snippet", "type": "video", "videoDuration": "short", "q": "#" + tag, "publishedAfter": after,
                                      "order": "viewCount", "maxResults": 50})
        ids = [i["id"]["videoId"] for i in res.get("items", []) if (i.get("id") or {}).get("videoId")]
        if not ids:
            continue
        det = client.data("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids), "maxResults": 50})
        for v in det.get("items", []):
            sn, st = v.get("snippet") or {}, v.get("statistics") or {}
            dur = parse_duration((v.get("contentDetails") or {}).get("duration"))
            if not dur or dur > SHORT_MAX_S or sn.get("channelId") == own_channel_id or not sn.get("publishedAt") or "viewCount" not in st:
                continue
            row = {"video_id": v["id"], "label": label, "tag": tag, "channel_id": sn.get("channelId"), "published_at": sn["publishedAt"][:19] + "Z",
                   "duration_s": dur, "views": int(st.get("viewCount") or 0), "likes": int(st.get("likeCount") or 0), "comments": int(st.get("commentCount") or 0),
                   "captured_at": db.utcnow()}
            db.upsert(conn, "yt_hashtag_posts", row, ("video_id",))
            stored += 1
        conn.commit()
    return {"tags": len(tags), "posts": stored}


def collect_step(ctx):
    """Collector step for yt_collect: weekly, soft on every error (quota included), never fails the run."""
    ensure(ctx.conn)
    if not ctx.opts.get("force") and recently_collected(ctx.conn, ctx.label, ctx.now):
        return
    tags = pick_tags(ctx.conn, ctx.label)
    if not tags:
        ctx.errors.append({"where": "hashtags", "error": "no hashtags found in your video descriptions; set analytics.yt_hashtags." + ctx.label + " in navaan.config.json"})
        return
    try:
        r = collect(ctx.conn, ctx.client, ctx.label, ctx.channel_id, tags, ctx.now)
    except Exception as e:
        ctx.errors.append({"where": "hashtags", "error": str(e)[:300]})
        return
    ctx.bump("hashtag_posts", r["posts"])


# ------------------------------------------------------------------ cli

def main(argv):
    import yt_collect as Y
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db")
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("collect"); c.add_argument("--account", default="music"); c.add_argument("--tags"); c.add_argument("--days", type=int, default=WINDOW_DAYS); c.add_argument("--force", action="store_true")
    t = sp.add_parser("tags"); t.add_argument("--account", default="music")
    a = ap.parse_args(argv)
    conn = db.connect(a.db)
    ensure(conn)
    override = [x for x in (a.tags or "").split(",")] if getattr(a, "tags", None) else None
    tags = pick_tags(conn, a.account, override)
    if a.cmd == "tags":
        print(", ".join("#" + x for x in tags) or "none found")
        return 0
    now = datetime.datetime.now(UTC)
    if not a.force and recently_collected(conn, a.account, now):
        print(f"{a.account}: collected in the last {MIN_GAP_DAYS} days, use --force to run again")
        return 0
    if not tags:
        sys.exit("navaan: no hashtags to search. Pass --tags or set analytics.yt_hashtags." + a.account)
    ch = db.one(conn, "SELECT channel_id FROM yt_channels WHERE label = " + db.PH, (a.account,))
    client = Y.Client(Y.load_auth(a.account))
    r = collect(conn, client, a.account, (ch or {}).get("channel_id"), tags, now, a.days)
    print(f"{a.account}: {r['posts']} Shorts from {', '.join('#' + x for x in tags)} ({client.calls} API calls)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
