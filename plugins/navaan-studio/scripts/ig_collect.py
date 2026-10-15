#!/usr/bin/env python3
"""ig_collect.py  collect Instagram data for NAVAAN accounts into the analytics database (SQLite now, Postgres later).

  collect [--account music|inspiration|all] [--only account,media,comments,audience,mentions] [--days 7] [--force]
  status  [--account ...]          row counts, last run, comments waiting for a reply
  link                             tie Instagram posts to song folders (matches published.instagram in meta.json) and refresh the songs table
  peers add|remove|list [@name ...] [--note TEXT]   creators to benchmark against
  mention --media-id ID [--comment-id ID] [--account ...]   fetch one @mention reported by a webhook and store it
  dbpath                           print the database file

Read only. This script never posts, replies, hides or deletes anything on Instagram.

Login: the same file the publisher uses, ~/.config/navaan/instagram.env (music) or accounts.<name>.instagram_env in navaan.config.json.
Keys: NAVAAN_IG_USER_ID, NAVAAN_IG_TOKEN, optional NAVAAN_IG_HOST (default https://graph.instagram.com, the Instagram Login host),
optional NAVAAN_IG_API_VERSION. The token needs instagram_business_basic and instagram_business_manage_insights; comments need
instagram_business_manage_comments. The token is never printed or stored in the database.

What is collected, per run, as dated rows so growth over time is kept:
  media            posts and Reels (metadata), media_snapshots (likes, comments, reach, views, saves, shares, watch time)
  comments         comment text, author, replies, hidden state, and whether the account has replied (tag columns stay for Claude)
  account          follower counts, daily reach, follower_count, views, accounts_engaged, total_interactions
  audience         follower demographics (city, country, age, gender) and online hours; Instagram needs 100+ followers for these
  peers, hashtags  market data. Needs Business Discovery and Hashtag Search, which Meta documents for the Facebook Login API. With an
                   Instagram Login token the run records 'unavailable' and goes on. Optional second login: NAVAAN_IG_MARKET_USER_ID,
                   NAVAAN_IG_MARKET_TOKEN, NAVAAN_IG_MARKET_HOST in the login file. Hashtags are rationed to 28 new per 7 days.
  mentions         media the account is tagged in (/tags). Instagram does not list @mentions by polling: they arrive by webhook as
                   ids, then `mention` fetches them.
Rate limits and errors: transient failures retry with backoff. A metric Instagram rejects for one post is skipped and noted in
raw_json, it does not stop the run.
"""
import os, sys, json, time, re, uuid, argparse, datetime, urllib.request, urllib.parse, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analytics_db as db
import navaan_log as L
LOG = L.get("ig_collect")

DEFAULT_HOST = "https://graph.instagram.com"
DEFAULT_VERSION = "v23.0"
RETRY_CODES = {1, 2, 4, 17, 32, 613}
REEL_METRICS = ["reach", "views", "saved", "shares", "reposts", "total_interactions",
                "ig_reels_avg_watch_time", "ig_reels_video_view_total_time", "reels_skip_rate"]
POST_METRICS = ["reach", "views", "saved", "shares", "total_interactions", "follows", "profile_visits"]
METRIC_COLS = {"reach": "reach", "views": "views", "saved": "saved", "shares": "shares", "reposts": "reposts",
               "total_interactions": "total_interactions", "ig_reels_avg_watch_time": "avg_watch_time_ms",
               "ig_reels_video_view_total_time": "total_watch_time_ms", "reels_skip_rate": "skip_rate",
               "follows": "follows", "profile_visits": "profile_visits"}
ALL_COLLECTORS = ("account", "media", "comments", "audience", "mentions", "peers", "hashtags")
UTC = datetime.timezone.utc


class ApiError(Exception):
    def __init__(self, status, code, message, subcode=None, retriable=False):
        super().__init__(f"Instagram API error {status} code={code}: {message}")
        self.status, self.code, self.subcode, self.retriable = status, code, subcode, retriable

    @property
    def auth(self):
        return self.code == 190 or self.status == 401


class Client:
    def __init__(self, uid, token, host=DEFAULT_HOST, version=DEFAULT_VERSION, opener=None, sleep=time.sleep):
        self.uid, self.token, self.host, self.version = uid, token, host.rstrip("/"), version
        self.opener, self.sleep = opener or urllib.request.urlopen, sleep
        self.calls = 0

    def _url(self, path, params):
        if path.startswith("http"):
            return path
        q = dict(params or {})
        q["access_token"] = self.token
        return f"{self.host}/{self.version}/{path.lstrip('/')}?" + urllib.parse.urlencode(q)

    def _err(self, e):
        raw = ""
        try:
            raw = e.read().decode("utf-8", "replace")
            body = json.loads(raw).get("error", {})
        except Exception as _e:
            L.soft(LOG, "err_error")
            body = {}
        msg = (body.get("message") or raw[:200] or str(e)).replace(self.token, "***")
        code = body.get("code")
        return ApiError(e.code, code, msg, body.get("error_subcode"), retriable=e.code in (429, 500, 502, 503, 504) or code in RETRY_CODES)

    def get(self, path, params=None):
        url = self._url(path, params)
        for attempt in range(5):
            self.calls += 1
            try:
                with self.opener(urllib.request.Request(url), timeout=60) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                L.ignored(LOG, "get: HTTPError (optional or expected)", e)
                err = self._err(e)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                L.ignored(LOG, "get: URLError/TimeoutError/ConnectionError (optional or expected)", e)
                err = ApiError(0, None, str(getattr(e, "reason", e)).replace(self.token, "***"), retriable=True)
            if not err.retriable or attempt == 4:
                raise err
            self.sleep(min(5 * 2 ** attempt, 120))

    def pages(self, path, params=None, max_pages=20):
        """All items of a paged edge. Returns (items, complete). complete is False when max_pages cut the list short."""
        out, d = [], self.get(path, params)
        for page in range(max_pages):
            out.extend(d.get("data", []))
            nxt = (d.get("paging") or {}).get("next")
            if not nxt:
                return out, True
            if page == max_pages - 1:
                return out, False
            d = self.get(nxt)
        return out, False


def norm_ts(s):
    """Instagram timestamps look like 2026-10-12T14:05:00+0000. Return UTC 'YYYY-MM-DDTHH:MM:SSZ', or None."""
    if not s:
        return None
    s2 = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", s.replace("Z", "+00:00"))
    try:
        dt = datetime.datetime.fromisoformat(s2)
    except ValueError as _e:
        L.ignored(LOG, "norm_ts: ValueError (optional or expected)", _e)
        return s
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) if s else None
    except ValueError as _e:
        L.ignored(LOG, "parse_ts: ValueError (optional or expected)", _e)
        return None


def age_days(ts, now):
    dt = parse_ts(ts)
    return (now - dt).total_seconds() / 86400 if dt else 9999


def read_env_file(path):
    out = {}
    if path and os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def account_labels():
    from navaan_common import cfg
    return ["music"] + [k for k in (cfg("accounts") or {}) if k != "music"]


def load_account(label):
    """Return (uid, token, host, version, handle) for an account label. Exits with a clear message when the login file is not ready."""
    from navaan_common import cfg, account
    if label == "music":
        path = os.environ.get("NAVAAN_IG_ENV", os.path.expanduser("~/.config/navaan/instagram.env"))
        handle = cfg("publish.instagram_handle", "")
        vals = {**read_env_file(path), **{k: v for k, v in os.environ.items() if k.startswith("NAVAAN_IG_")}}
    else:
        a = account(label)
        if not a["configured"] or not a["ig_ready"]:
            sys.exit(f"navaan: account '{label}' is not ready. Needs accounts.{label}.instagram_env in navaan.config.json and that file present.")
        path, handle = a["ig_env"], a["handle"]
        vals = read_env_file(path)
    uid, tok = vals.get("NAVAAN_IG_USER_ID"), vals.get("NAVAAN_IG_TOKEN")
    if not uid or not tok:
        sys.exit(f"navaan: NAVAAN_IG_USER_ID and NAVAAN_IG_TOKEN are missing for '{label}' (login file: {path}).")
    host = vals.get("NAVAAN_IG_HOST") or DEFAULT_HOST
    return uid, tok, host, vals.get("NAVAAN_IG_API_VERSION") or DEFAULT_VERSION, (handle or "").lstrip("@")


class Ctx:
    def __init__(self, client, conn, uid, label, opts):
        self.client, self.conn, self.uid, self.label, self.opts = client, conn, uid, label, opts
        self.started = db.utcnow()
        self.now = parse_ts(self.started)
        self.username = ""
        self.market = None         # optional second Client (Facebook Login) for peers and hashtags
        self.media = None          # media_id -> listing dict, filled by ensure_media
        self.prev_comments = {}    # media_id -> comments_count of the latest snapshot before this run
        self.stats, self.errors = {}, []

    def bump(self, key, n=1):
        self.stats[key] = self.stats.get(key, 0) + n

    def soft(self, where, fn):
        """Run fn. A non-auth API error is recorded and skipped, an auth error stops the run."""
        try:
            return fn()
        except ApiError as e:
            if e.auth:
                raise
            self.errors.append({"where": where, "error": str(e)[:300]})
            return None


def unix_day(d):
    return int(datetime.datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp())


def insight_values(resp):
    """{metric: value} from an insights response, for lifetime values and total_value metrics."""
    out = {}
    for it in resp.get("data", []):
        if it.get("values"):
            out[it["name"]] = it["values"][0].get("value")
        elif it.get("total_value") is not None:
            out[it["name"]] = it["total_value"].get("value")
    return out


def fetch_media_insights(client, media_id, metrics):
    """One call for all metrics. If Instagram rejects the set, ask per metric so one unsupported metric costs only itself."""
    try:
        return insight_values(client.get(f"{media_id}/insights", {"metric": ",".join(metrics)})), {}
    except ApiError as e:
        if e.auth:
            raise
    got, errs = {}, {}
    for m in metrics:
        try:
            got.update(insight_values(client.get(f"{media_id}/insights", {"metric": m})))
        except ApiError as e:
            if e.auth:
                raise
            errs[m] = str(e)[:160]
    return got, errs


def ensure_profile(ctx):
    p = ctx.client.get(ctx.uid, {"fields": "username,name,followers_count,follows_count,media_count"})
    ctx.username = p.get("username", "") or ""
    row = {"ig_user_id": ctx.uid, "label": ctx.label, "username": ctx.username, "name": p.get("name"), "created_at": ctx.started}
    db.upsert(ctx.conn, "accounts", row, ("ig_user_id",), keep=("created_at",))
    return p


def ensure_media(ctx):
    if ctx.media is not None:
        return
    fields = "id,caption,media_type,media_product_type,permalink,shortcode,timestamp,thumbnail_url,like_count,comments_count"
    items, complete = ctx.client.pages(f"{ctx.uid}/media", {"fields": fields, "limit": 50}, ctx.opts["max_pages"])
    ctx.media = {m["id"]: m for m in items}
    for m in items:
        last = db.one(ctx.conn, f"SELECT comments_count FROM media_snapshots WHERE media_id = {db.PH} ORDER BY captured_at DESC LIMIT 1", (m["id"],))
        ctx.prev_comments[m["id"]] = last["comments_count"] if last else None
        db.upsert(ctx.conn, "media", {
            "media_id": m["id"], "ig_user_id": ctx.uid, "media_type": m.get("media_type"), "product_type": m.get("media_product_type"),
            "permalink": m.get("permalink"), "shortcode": m.get("shortcode"), "caption": m.get("caption"), "posted_at": norm_ts(m.get("timestamp")),
            "thumbnail_url": m.get("thumbnail_url"), "first_seen_at": ctx.started, "last_seen_at": ctx.started, "deleted_at": None,
        }, ("media_id",), keep=("first_seen_at",))
    if complete:
        cur = ctx.conn.execute(f"UPDATE media SET deleted_at = {db.PH} WHERE ig_user_id = {db.PH} AND deleted_at IS NULL AND last_seen_at < {db.PH}",
                               (ctx.started, ctx.uid, ctx.started))
        ctx.bump("media_marked_deleted", cur.rowcount)
    else:
        ctx.errors.append({"where": "media", "error": f"listing stopped at {ctx.opts['max_pages']} pages, deletions not checked"})
    ctx.bump("media_seen", len(items))
    ctx.conn.commit()
    link_songs(ctx.conn)


def collect_media(ctx):
    ensure_media(ctx)
    o = ctx.opts
    for mid, m in ctx.media.items():
        ptype = m.get("media_product_type")
        metrics = REEL_METRICS if ptype == "REELS" else [] if ptype == "STORY" else POST_METRICS
        last = db.one(ctx.conn, f"SELECT MAX(captured_at) AS t FROM media_snapshots WHERE media_id = {db.PH}", (mid,))["t"]
        posted = norm_ts(m.get("timestamp"))
        due = o["force"] or last is None or age_days(posted, ctx.now) <= o["recent_days"] or age_days(last, ctx.now) >= o["old_days"]
        if not due:
            continue
        vals, errs = (fetch_media_insights(ctx.client, mid, metrics) if metrics else ({}, {}))
        row = {"media_id": mid, "captured_at": ctx.started, "like_count": m.get("like_count"), "comments_count": m.get("comments_count"),
               "raw_json": json.dumps({"insights": vals, "errors": errs}, ensure_ascii=False)}
        for k, col in METRIC_COLS.items():
            row[col] = vals.get(k)
        db.upsert(ctx.conn, "media_snapshots", row, ("media_id", "captured_at"))
        ctx.bump("snapshots")
        if errs:
            ctx.bump("snapshot_metric_errors", len(errs))
    ctx.conn.commit()


def collect_comments(ctx):
    ensure_media(ctx)
    o = ctx.opts
    fields = ("id,text,username,timestamp,like_count,hidden,parent_id,"
              "replies{id,text,username,timestamp,like_count,hidden,parent_id}")
    for mid, m in ctx.media.items():
        n = m.get("comments_count") or 0
        if not n:
            continue
        have = db.one(ctx.conn, f"SELECT COUNT(*) AS n FROM comments WHERE media_id = {db.PH}", (mid,))["n"]
        prev = ctx.prev_comments.get(mid)
        due = o["force"] or have == 0 or prev is None or prev != n or age_days(norm_ts(m.get("timestamp")), ctx.now) <= o["comment_days"]
        if not due:
            continue
        items = ctx.soft(f"comments {mid}", lambda: ctx.client.pages(f"{mid}/comments", {"fields": fields, "limit": 50}, o["max_pages"])[0])
        for c in items or []:
            store_comment(ctx, mid, c, None)
            for r in ((c.get("replies") or {}).get("data") or []):
                store_comment(ctx, mid, r, c["id"])
    ctx.conn.commit()


def store_comment(ctx, media_id, c, parent):
    uname = c.get("username") or ""
    db.upsert(ctx.conn, "comments", {
        "comment_id": c["id"], "media_id": media_id, "parent_id": c.get("parent_id") or parent, "username": uname, "text": c.get("text"),
        "posted_at": norm_ts(c.get("timestamp")), "like_count": c.get("like_count"), "hidden": 1 if c.get("hidden") else 0,
        "is_own": 1 if ctx.username and uname.lower() == ctx.username.lower() else 0,
        "first_seen_at": ctx.started, "last_seen_at": ctx.started,
    }, ("comment_id",), keep=("first_seen_at",))
    ctx.bump("comments")


def collect_account(ctx, profile):
    day = db.today()
    for k in ("followers_count", "follows_count", "media_count"):
        if profile.get(k) is not None:
            db.upsert(ctx.conn, "account_daily", {"ig_user_id": ctx.uid, "period_end": day, "metric": k, "value": profile[k], "collected_at": ctx.started},
                      ("ig_user_id", "period_end", "metric"))
    days = ctx.opts["days"]
    since = unix_day(ctx.now - datetime.timedelta(days=days))
    until = unix_day(ctx.now + datetime.timedelta(days=1))
    for metric, extra in (("reach", {"metric_type": "time_series"}), ("follower_count", {})):
        resp = ctx.soft(f"account {metric}", lambda: ctx.client.get(f"{ctx.uid}/insights", {"metric": metric, "period": "day", "since": since, "until": until, **extra}))
        for it in (resp or {}).get("data", []):
            for v in it.get("values", []):
                if v.get("end_time") and v.get("value") is not None:
                    db.upsert(ctx.conn, "account_daily", {"ig_user_id": ctx.uid, "period_end": norm_ts(v["end_time"])[:10], "metric": metric,
                                                         "value": v["value"], "collected_at": ctx.started}, ("ig_user_id", "period_end", "metric"))
                    ctx.bump("account_points")
    metrics = ["views", "accounts_engaged", "total_interactions"]
    for back in range(1, days + 1):
        d = (ctx.now - datetime.timedelta(days=back)).date()
        period_end = (d + datetime.timedelta(days=1)).isoformat()
        known = db.one(ctx.conn, f"SELECT COUNT(*) AS n FROM account_daily WHERE ig_user_id = {db.PH} AND period_end = {db.PH} AND metric IN ('views','accounts_engaged','total_interactions')",
                       (ctx.uid, period_end))["n"]
        if known == 3 and back > 3 and not ctx.opts["force"]:
            continue  # older than the 48 hour reporting lag and already stored
        win = {"period": "day", "metric_type": "total_value", "since": unix_day(d), "until": unix_day(d) + 86400}
        got = ctx.soft(f"account totals {d}", lambda: insight_values(ctx.client.get(f"{ctx.uid}/insights", {"metric": ",".join(metrics), **win})))
        if got is None:
            got = {}
            for m in metrics:
                got.update(ctx.soft(f"account {m} {d}", lambda: insight_values(ctx.client.get(f"{ctx.uid}/insights", {"metric": m, **win}))) or {})
        for k, v in got.items():
            if v is not None:
                db.upsert(ctx.conn, "account_daily", {"ig_user_id": ctx.uid, "period_end": period_end, "metric": k, "value": v, "collected_at": ctx.started},
                          ("ig_user_id", "period_end", "metric"))
                ctx.bump("account_points")
    ctx.conn.commit()


def collect_audience(ctx):
    day = db.today()
    for b in ("city", "country", "age", "gender"):
        resp = ctx.soft(f"audience {b}", lambda: ctx.client.get(f"{ctx.uid}/insights", {"metric": "follower_demographics", "period": "lifetime",
                                                                                       "metric_type": "total_value", "breakdown": b, "timeframe": "last_30_days"}))
        for it in (resp or {}).get("data", []):
            for bd in ((it.get("total_value") or {}).get("breakdowns") or []):
                for r in bd.get("results", []):
                    db.upsert(ctx.conn, "audience", {"ig_user_id": ctx.uid, "captured_on": day, "breakdown": b,
                                                     "bucket": "|".join(str(x) for x in r.get("dimension_values", [])), "value": r.get("value")},
                              ("ig_user_id", "captured_on", "breakdown", "bucket"))
                    ctx.bump("audience_rows")
    resp = ctx.soft("online_followers", lambda: ctx.client.get(f"{ctx.uid}/insights", {"metric": "online_followers", "period": "lifetime"}))
    for it in (resp or {}).get("data", []):
        for v in it.get("values", [])[:1]:
            if isinstance(v.get("value"), dict):
                for h, n in v["value"].items():
                    db.upsert(ctx.conn, "online_hours", {"ig_user_id": ctx.uid, "captured_on": day, "hour": int(h), "followers": n},
                              ("ig_user_id", "captured_on", "hour"))
                    ctx.bump("online_rows")
    ctx.conn.commit()


def store_mention(ctx, mention_id, kind, row):
    db.upsert(ctx.conn, "mentions", {"mention_id": mention_id, "ig_user_id": ctx.uid, "kind": kind, "first_seen_at": ctx.started,
                                     "last_seen_at": ctx.started, **row}, ("mention_id",), keep=("first_seen_at",))
    ctx.bump("mentions")


def collect_mentions(ctx):
    items = ctx.soft("tags", lambda: ctx.client.pages(f"{ctx.uid}/tags", {"fields": "id,caption,media_type,permalink,timestamp,username,like_count,comments_count",
                                                                          "limit": 50}, ctx.opts["max_pages"])[0])
    for m in items or []:
        store_mention(ctx, f"tag:{m['id']}", "tag", {"media_id": m["id"], "username": m.get("username"), "permalink": m.get("permalink"),
                                                    "text": m.get("caption"), "posted_at": norm_ts(m.get("timestamp")),
                                                    "like_count": m.get("like_count"), "comments_count": m.get("comments_count")})
    ctx.conn.commit()


def ingest_mention(ctx, media_id=None, comment_id=None):
    """Fetch one @mention that a webhook reported. media_id: the mentioning post. comment_id: the mentioning comment."""
    if media_id and not comment_id:
        f = "caption,media_type,permalink,timestamp,username,like_count,comments_count,id"
        d = ctx.client.get(ctx.uid, {"fields": f"mentioned_media.media_id({media_id}){{{f}}}"}).get("mentioned_media") or {}
        if d:
            store_mention(ctx, f"media:{d.get('id', media_id)}", "mention_media", {"media_id": d.get("id", media_id), "username": d.get("username"),
                          "permalink": d.get("permalink"), "text": d.get("caption"), "posted_at": norm_ts(d.get("timestamp")),
                          "like_count": d.get("like_count"), "comments_count": d.get("comments_count")})
    if comment_id:
        f = "id,text,timestamp,username,like_count,media{id,permalink}"
        d = ctx.client.get(ctx.uid, {"fields": f"mentioned_comment.comment_id({comment_id}){{{f}}}"}).get("mentioned_comment") or {}
        if d:
            store_mention(ctx, f"comment:{d.get('id', comment_id)}", "mention_comment", {"comment_id": d.get("id", comment_id),
                          "media_id": (d.get("media") or {}).get("id") or media_id, "username": d.get("username"), "permalink": (d.get("media") or {}).get("permalink"),
                          "text": d.get("text"), "posted_at": norm_ts(d.get("timestamp")), "like_count": d.get("like_count")})
    ctx.conn.commit()


def ig_ref(value):
    """(media_id, shortcode) from a published.instagram value: a numeric media id or a permalink."""
    v = (value or "").strip()
    if v.isdigit():
        return v, None
    m = re.search(r"instagram\.com/(?:[\w.]+/)?(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)", v)
    return None, (m.group(1) if m else None)


def link_songs(conn):
    """Refresh the songs table from the song folders and tie posts to songs through published.instagram in meta.json."""
    from navaan_common import songs_root, load_json
    root = songs_root()
    if not os.path.isdir(root):
        return 0
    linked = 0
    for slug in sorted(os.listdir(root)):
        d = os.path.join(root, slug)
        if slug.startswith("_") or not os.path.isdir(d):
            continue
        meta = load_json(os.path.join(d, "meta.json"), default={})
        tags = load_json(os.path.join(d, "tags.json"), default={})
        title = tags.get("title")
        if not title and os.path.exists(os.path.join(d, "title.txt")):
            title = open(os.path.join(d, "title.txt"), encoding="utf-8").read().strip().splitlines()[0:1]
            title = title[0] if title else None
        db.upsert(conn, "songs", {"slug": slug, "item_type": meta.get("type") or "music", "title": title, "album": tags.get("album"),
                                  "genre": tags.get("genre"), "language": tags.get("language"), "state": meta.get("state"),
                                  "tags_json": json.dumps(tags, ensure_ascii=False), "updated_at": db.utcnow()}, ("slug",))
        mid, sc = ig_ref((meta.get("published") or {}).get("instagram"))
        if mid:
            linked += conn.execute(f"UPDATE media SET slug = {db.PH} WHERE media_id = {db.PH}", (slug, mid)).rowcount
        elif sc:
            linked += conn.execute(f"UPDATE media SET slug = {db.PH} WHERE shortcode = {db.PH}", (slug, sc)).rowcount
    conn.commit()
    return linked



HASHTAG_WINDOW_DAYS = 7
HASHTAG_QUOTA = 28           # Instagram allows 30 unique hashtags per rolling 7 days, keep a margin of 2
HASHTAG_NEW_PER_RUN = 5


def market_unavailable(ctx, what, err):
    """Peers and hashtags need Instagram Business Discovery and Hashtag Search. Meta documents both for the Facebook Login API
    (graph.facebook.com), hashtags also need Instagram Public Content Access from app review. With an Instagram Login token they
    can simply be refused. That is a state, not a failure of the run."""
    ctx.stats[what] = "unavailable: " + str(err)[:160]


def collect_peers(ctx):
    peers = db.rows(ctx.conn, "SELECT username FROM peers ORDER BY username")
    if not peers:
        return
    mc = ctx.market or ctx.client
    media_fields = "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count"
    fails, ok = 0, 0
    for p in peers:
        u = p["username"]
        fields = f"business_discovery.username({u}){{username,followers_count,media_count,media.limit(25){{{media_fields}}}}}"
        try:
            d = mc.get(mc.uid, {"fields": fields}).get("business_discovery") or {}
        except ApiError as e:
            if e.auth:
                raise
            db.upsert(ctx.conn, "peers", {"username": u, "added_at": ctx.started, "last_error": str(e)[:200]}, ("username",), keep=("added_at",))
            fails += 1
            if fails >= 2 and not ok:
                market_unavailable(ctx, "peers", e)
                break
            continue
        ok += 1
        db.upsert(ctx.conn, "peers", {"username": u, "added_at": ctx.started, "last_fetched_at": ctx.started, "followers_count": d.get("followers_count"),
                                      "media_count": d.get("media_count"), "last_error": None}, ("username",), keep=("added_at",))
        for m in ((d.get("media") or {}).get("data") or []):
            db.upsert(ctx.conn, "peer_media", {"username": u, "media_id": m["id"], "media_type": m.get("media_type"), "product_type": m.get("media_product_type"),
                                               "permalink": m.get("permalink"), "caption": m.get("caption"), "posted_at": norm_ts(m.get("timestamp")),
                                               "like_count": m.get("like_count"), "comments_count": m.get("comments_count"), "captured_at": ctx.started},
                      ("username", "media_id"))
            ctx.bump("peer_posts")
    ctx.conn.commit()


def own_hashtags(conn, uid, limit=5):
    counts = {}
    for r in db.rows(conn, f"SELECT caption FROM media WHERE ig_user_id = {db.PH} AND deleted_at IS NULL AND caption IS NOT NULL", (uid,)):
        for t in set(re.findall(r"#(\w+)", r["caption"].lower())):
            counts[t] = counts.get(t, 0) + 1
    return [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:limit]]


def collect_hashtags(ctx):
    try:
        from navaan_common import cfg
        configured = [str(t).lstrip("#").lower() for t in (cfg("analytics.hashtags", []) or [])]
    except SystemExit as _e:
        L.ignored(LOG, "collect_hashtags: SystemExit (optional or expected)", _e)
        configured = []
    tags = list(dict.fromkeys(configured + own_hashtags(ctx.conn, ctx.uid)))
    if not tags:
        return
    mc = ctx.market or ctx.client
    cutoff = (ctx.now - datetime.timedelta(days=HASHTAG_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    used = db.one(ctx.conn, f"SELECT COUNT(*) AS n FROM hashtag_queries WHERE queried_at >= {db.PH}", (cutoff,))["n"]
    new_now = 0
    for tag in tags:
        known = db.one(ctx.conn, f"SELECT hashtag_id, queried_at FROM hashtag_queries WHERE hashtag = {db.PH}", (tag,))
        free = bool(known and known["queried_at"] >= cutoff)  # repeat queries inside the window do not count against the limit
        if not free:
            if used + new_now >= HASHTAG_QUOTA or new_now >= HASHTAG_NEW_PER_RUN:
                ctx.bump("hashtags_deferred")
                continue
        try:
            hid = (known or {}).get("hashtag_id") if free else None
            if not hid:
                r = mc.get("ig_hashtag_search", {"user_id": mc.uid, "q": tag}).get("data") or []
                hid = r[0]["id"] if r else None
            if not hid:
                continue
            for kind in ("top_media", "recent_media"):
                items = mc.get(f"{hid}/{kind}", {"user_id": mc.uid, "limit": 25, "fields": "id,caption,media_type,like_count,comments_count,permalink,timestamp"}).get("data") or []
                for m in items:
                    db.upsert(ctx.conn, "hashtag_media", {"hashtag": tag, "media_id": m["id"], "kind": kind, "media_type": m.get("media_type"), "permalink": m.get("permalink"),
                                                          "caption": m.get("caption"), "posted_at": norm_ts(m.get("timestamp")), "like_count": m.get("like_count"),
                                                          "comments_count": m.get("comments_count"), "captured_at": ctx.started}, ("hashtag", "media_id", "kind"))
                    ctx.bump("hashtag_posts")
            db.upsert(ctx.conn, "hashtag_queries", {"hashtag": tag, "hashtag_id": hid, "queried_at": known["queried_at"] if free else ctx.started}, ("hashtag",))
            if not free:
                new_now += 1
        except ApiError as e:
            if e.auth:
                raise
            market_unavailable(ctx, "hashtags", e)
            break
    ctx.conn.commit()


def collect(conn, client, uid, label, only=ALL_COLLECTORS, opts=None, market=None):
    """Run the chosen collectors for one account. Returns the run summary that is also stored in collector_runs."""
    o = {"days": 7, "recent_days": 30, "old_days": 7, "comment_days": 60, "max_pages": 20, "force": False}
    o.update(opts or {})
    ctx = Ctx(client, conn, uid, label, o)
    ctx.market = market
    run_id = uuid.uuid4().hex[:12]
    db.upsert(conn, "collector_runs", {"run_id": run_id, "ig_user_id": uid, "started_at": ctx.started, "collectors": ",".join(only), "status": "running"}, ("run_id",))
    conn.commit()
    status = "ok"
    try:
        profile = ensure_profile(ctx)
        steps = {"account": lambda: collect_account(ctx, profile), "media": lambda: collect_media(ctx), "comments": lambda: collect_comments(ctx),
                 "audience": lambda: collect_audience(ctx), "mentions": lambda: collect_mentions(ctx),
                 "peers": lambda: collect_peers(ctx), "hashtags": lambda: collect_hashtags(ctx)}
        for name in ALL_COLLECTORS:
            if name in only:
                try:
                    steps[name]()
                except ApiError as e:
                    if e.auth:
                        raise
                    ctx.errors.append({"where": name, "error": str(e)[:300]})
        status = "ok" if not ctx.errors else "partial"
    except ApiError as e:
        L.ignored(LOG, "collect: ApiError (optional or expected)", e)
        status = "failed"
        ctx.errors.append({"where": "auth" if e.auth else "run", "error": str(e)[:300] + (" Token expired or invalid: refresh the long-lived token." if e.auth else "")})
    conn.execute(f"UPDATE accounts SET last_collected_at = {db.PH} WHERE ig_user_id = {db.PH}", (db.utcnow(), uid)) if status != "failed" else None
    ctx.stats["api_calls"] = client.calls
    db.upsert(conn, "collector_runs", {"run_id": run_id, "ig_user_id": uid, "started_at": ctx.started, "finished_at": db.utcnow(), "collectors": ",".join(only),
                                       "status": status, "stats_json": json.dumps(ctx.stats), "errors_json": json.dumps(ctx.errors, ensure_ascii=False)}, ("run_id",))
    conn.commit()
    return {"run_id": run_id, "account": label, "status": status, "stats": ctx.stats, "errors": ctx.errors}


def load_market(label):
    """Optional second login for peers and hashtags: NAVAAN_IG_MARKET_USER_ID, NAVAAN_IG_MARKET_TOKEN, NAVAAN_IG_MARKET_HOST (default graph.facebook.com)
    in the same login file. Needs the Instagram API with Facebook Login. Returns a Client or None."""
    from navaan_common import cfg, account
    if label == "music":
        path = os.environ.get("NAVAAN_IG_ENV", os.path.expanduser("~/.config/navaan/instagram.env"))
        vals = {**read_env_file(path), **{k: v for k, v in os.environ.items() if k.startswith("NAVAAN_IG_")}}
    else:
        a = account(label)
        vals = read_env_file(a["ig_env"]) if a.get("ig_env") else {}
    uid, tok = vals.get("NAVAAN_IG_MARKET_USER_ID"), vals.get("NAVAAN_IG_MARKET_TOKEN")
    if not (uid and tok):
        return None
    return Client(uid, tok, vals.get("NAVAAN_IG_MARKET_HOST") or "https://graph.facebook.com", vals.get("NAVAAN_IG_API_VERSION") or DEFAULT_VERSION)


def make_client(label):
    uid, tok, host, ver, _ = load_account(label)
    return uid, Client(uid, tok, host, ver), load_market(label)


def cmd_collect(a):
    only = tuple(x.strip() for x in a.only.split(",")) if a.only else ALL_COLLECTORS
    bad = [x for x in only if x not in ALL_COLLECTORS]
    if bad:
        sys.exit(f"navaan: unknown collector {bad}. Choose from {', '.join(ALL_COLLECTORS)}.")
    labels = account_labels() if a.account == "all" else [a.account]
    conn = db.connect(a.db)
    worst = 0
    for label in labels:
        try:
            uid, client, market = make_client(label)
        except SystemExit as e:
            if a.account == "all":
                print(f"{label}: skipped ({e})")
                continue
            raise
        res = collect(conn, client, uid, label, only, {"days": a.days, "force": a.force, "max_pages": a.max_pages}, market)
        print(f"{label}: {res['status']}  {json.dumps(res['stats'])}")
        for e in res["errors"]:
            print(f"  note: {e['where']}: {e['error']}")
        worst = max(worst, 2 if res["status"] == "failed" else 1 if res["status"] == "partial" else 0)
    sys.exit(0 if worst < 2 else 2)


def cmd_status(a):
    conn = db.connect(a.db)
    print("database:", db.db_path(a.db))
    for acc in db.rows(conn, "SELECT * FROM accounts ORDER BY label"):
        if a.account not in ("all", acc["label"]):
            continue
        u = acc["ig_user_id"]
        run = db.one(conn, f"SELECT status, finished_at FROM collector_runs WHERE ig_user_id = {db.PH} ORDER BY started_at DESC LIMIT 1", (u,)) or {}
        n = lambda sql: db.one(conn, sql, (u,))["n"]
        print(f"{acc['label']} (@{acc['username']}): last run {run.get('status')} at {run.get('finished_at')}")
        print("  media", n(f"SELECT COUNT(*) AS n FROM media WHERE ig_user_id = {db.PH} AND deleted_at IS NULL"),
              " snapshots", n(f"SELECT COUNT(*) AS n FROM media_snapshots WHERE media_id IN (SELECT media_id FROM media WHERE ig_user_id = {db.PH})"),
              " comments", n(f"SELECT COUNT(*) AS n FROM comments WHERE media_id IN (SELECT media_id FROM media WHERE ig_user_id = {db.PH})"),
              " waiting for a reply", n(db.UNREPLIED_COUNT_SQL))


def cmd_link(a):
    conn = db.connect(a.db)
    print("posts linked to songs:", link_songs(conn))


def cmd_peers(a):
    conn = db.connect(a.db)
    if a.action == "add":
        for name in a.names:
            u = name.lstrip("@").strip().lower()
            if not re.match(r"^[a-z0-9._]{1,30}$", u):
                sys.exit(f"navaan: not an Instagram username: {name}")
            db.upsert(conn, "peers", {"username": u, "label": a.label, "note": a.note, "added_at": db.utcnow()}, ("username",), keep=("added_at",), coalesce=("label", "note"))
        conn.commit()
    elif a.action == "remove":
        for name in a.names:
            conn.execute(f"DELETE FROM peers WHERE username = {db.PH}", (name.lstrip("@").lower(),))
            conn.execute(f"DELETE FROM peer_media WHERE username = {db.PH}", (name.lstrip("@").lower(),))
        conn.commit()
    for p in db.rows(conn, "SELECT username, label, followers_count, last_fetched_at, last_error FROM peers ORDER BY username"):
        print(f"@{p['username']}  followers={p['followers_count']}  last fetched={p['last_fetched_at']}  {('error: ' + p['last_error']) if p['last_error'] else ''}")


def cmd_mention(a):
    if not (a.media_id or a.comment_id):
        sys.exit("navaan: give --media-id or --comment-id")
    uid, client, _ = make_client(a.account)
    conn = db.connect(a.db)
    ctx = Ctx(client, conn, uid, a.account, {})
    ingest_mention(ctx, a.media_id, a.comment_id)
    print("stored:", ctx.stats.get("mentions", 0))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", help="database file (default: NAVAAN_DB, analytics.db_path, or ~/.local/share/navaan/analytics.db)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("collect"); c.add_argument("--account", default="music"); c.add_argument("--only"); c.add_argument("--days", type=int, default=7)
    c.add_argument("--max-pages", type=int, default=20); c.add_argument("--force", action="store_true"); c.set_defaults(fn=cmd_collect)
    s = sp.add_parser("status"); s.add_argument("--account", default="all"); s.set_defaults(fn=cmd_status)
    sp.add_parser("link").set_defaults(fn=cmd_link)
    pe = sp.add_parser("peers", help="creators to benchmark against (public numbers via Business Discovery)"); pe.add_argument("action", choices=["add", "remove", "list"])
    pe.add_argument("names", nargs="*"); pe.add_argument("--label"); pe.add_argument("--note"); pe.set_defaults(fn=cmd_peers)
    m = sp.add_parser("mention"); m.add_argument("--media-id"); m.add_argument("--comment-id"); m.add_argument("--account", default="music"); m.set_defaults(fn=cmd_mention)
    sp.add_parser("dbpath").set_defaults(fn=lambda a: print(db.db_path(a.db)))
    a = ap.parse_args()
    a.fn(a)
