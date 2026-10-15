#!/usr/bin/env python3
"""yt_collect.py  collect YouTube data for NAVAAN channels into the analytics database (same file as Instagram).

  collect [--account music|inspiration|all] [--only channel,videos,comments,analytics,retention] [--days 14] [--force]
  status  [--account ...]
  link                       tie videos to song folders (published.youtube_items and published.youtube_short in meta.json)
  auth    [--account music]  one time sign in for READ ONLY analytics (youtube.readonly + yt-analytics.readonly)
  dbpath

Read only. This script never uploads, edits, deletes, comments or changes privacy on YouTube.

Login, two levels:
  Full:  a token with youtube.readonly and yt-analytics.readonly. Create it with `yt_collect.py auth`. Gives watch time, average view
         duration and percentage, subscribers gained, retention curves, traffic sources, audience.
  Basic: if no analytics token exists, the publishing token (~/.config/navaan/youtube_token.json or accounts.<name>.yt_token) is used.
         That gives channel totals, per video views, likes, comments and comment threads. Analytics steps are noted as unavailable.
Files: ~/.config/navaan/youtube_analytics_token.json (music) or accounts.<name>.yt_analytics_token, else the publishing token path with
_analytics added before .json. NAVAAN_YT_ANALYTICS_TOKEN overrides for music. Tokens are never printed or stored in the database.
Not available through any YouTube API: thumbnail impressions and click through rate (Studio only).
Quota: the Data API allows 10,000 units a day. A run uses a few dozen. Transient errors retry with backoff.
"""
import os, sys, json, time, re, uuid, argparse, datetime, urllib.request, urllib.parse, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analytics_db as db
import navaan_log as L
LOG = L.get("yt_collect")

API = "https://www.googleapis.com/youtube/v3"
ANA = "https://youtubeanalytics.googleapis.com/v2/reports"
TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPE_ANALYTICS = "https://www.googleapis.com/auth/yt-analytics.readonly"
# youtube.force-ssl is what commentThreads.list needs (youtube.readonly gets a 403 insufficientPermissions). It can also write, but this collector only ever reads.
READ_SCOPES = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/youtube.force-ssl", SCOPE_ANALYTICS]
ALL_COLLECTORS = ("channel", "videos", "comments", "analytics", "retention")
UTC = datetime.timezone.utc
SHORT_MAX_S = 60            # without meta.json to say otherwise, a video this short or shorter is treated as a Short
SKIP_REASONS = {"commentsDisabled", "videoNotFound", "forbidden", "processingFailure"}


class ApiError(Exception):
    def __init__(self, status, reason, message, retriable=False):
        super().__init__(f"YouTube API error {status} {reason or ''}: {message}")
        self.status, self.reason, self.retriable = status, reason, retriable

    @property
    def auth(self):
        return self.status == 401 or self.reason in ("authError", "invalid_grant", "unauthorized_client")

    @property
    def quota(self):
        return self.reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded")


def norm_ts(s):
    """YouTube timestamps are RFC 3339 (2026-10-12T14:05:00Z or with fractions or an offset). Return UTC 'YYYY-MM-DDTHH:MM:SSZ', or None."""
    if not s:
        return None
    try:
        dt = datetime.datetime.fromisoformat(re.sub(r"\.\d+", "", s.replace("Z", "+00:00")))
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


def iso_duration_s(d):
    """PT1M30S -> 90. Live and unknown values give None."""
    m = re.match(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", d or "")
    if not m or not any(m.groups()):
        return None
    dd, h, mi, s = (int(x or 0) for x in m.groups())
    total = dd * 86400 + h * 3600 + mi * 60 + s
    return total or None   # P0D marks a live stream


def to_int(x):
    try:
        return int(x)
    except (TypeError, ValueError) as _e:
        L.ignored(LOG, "to_int: TypeError/ValueError (optional or expected)", _e)
        return None


# ---------------------------------------------------------------- auth and client

class Auth:
    """Reads a google-auth style token file and exchanges the refresh token for a short lived access token. Nothing is written back."""

    def __init__(self, path, opener=None):
        self.path, self.opener = path, opener or urllib.request.urlopen
        self.info = json.load(open(path, encoding="utf-8"))
        self.access, self.expires = None, 0
        self.secrets = [v for v in (self.info.get("refresh_token"), self.info.get("client_secret"), self.info.get("token")) if v]

    @property
    def scopes(self):
        s = self.info.get("scopes") or self.info.get("scope") or []
        return set(s.split() if isinstance(s, str) else s)

    @property
    def can_analytics(self):
        return SCOPE_ANALYTICS in self.scopes

    def token(self, force=False):
        if self.access and not force and time.time() < self.expires - 60:
            return self.access
        i = self.info
        if not (i.get("refresh_token") and i.get("client_id") and i.get("client_secret")):
            if i.get("token") and not force:
                return i["token"]
            raise ApiError(401, "invalid_grant", f"token file {self.path} has no refresh_token, client_id or client_secret: sign in again")
        body = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": i["refresh_token"], "client_id": i["client_id"], "client_secret": i["client_secret"]}).encode()
        try:
            with self.opener(urllib.request.Request(i.get("token_uri") or TOKEN_URI, data=body), timeout=60) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            try:
                d = json.loads(e.read().decode("utf-8", "replace"))
            except Exception as _e:
                L.soft(LOG, "token_error")
                d = {}
            raise ApiError(400 if e.code == 400 else e.code, d.get("error") or "invalid_grant", (d.get("error_description") or "token refresh failed")[:200])
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ApiError(0, None, "token refresh failed: " + str(getattr(e, "reason", e)), retriable=True)
        self.access, self.expires = d["access_token"], time.time() + int(d.get("expires_in", 3600))
        self.secrets.append(self.access)
        return self.access


class Client:
    def __init__(self, auth, opener=None, sleep=time.sleep):
        self.auth, self.opener, self.sleep, self.calls = auth, opener or urllib.request.urlopen, sleep, 0

    def _clean(self, s):
        for v in self.auth.secrets:
            s = s.replace(v, "***")
        return s

    def _err(self, e):
        raw = ""
        try:
            raw = e.read().decode("utf-8", "replace")
            body = json.loads(raw).get("error", {})
        except Exception as _e:
            L.soft(LOG, "err_error")
            body = {}
        if isinstance(body, str):
            return ApiError(e.code, body, self._clean(raw[:200]))
        errs = body.get("errors") or [{}]
        reason = errs[0].get("reason") or body.get("status")
        msg = self._clean(body.get("message") or raw[:200] or str(e))
        return ApiError(e.code, reason, msg, retriable=e.code in (429, 500, 502, 503, 504) and reason not in ("quotaExceeded", "dailyLimitExceeded"))

    def get(self, url, params=None):
        q = ("?" + urllib.parse.urlencode(params)) if params else ""
        refreshed = False
        for attempt in range(5):
            self.calls += 1
            req = urllib.request.Request(url + q, headers={"Authorization": "Bearer " + self.auth.token()})
            try:
                with self.opener(req, timeout=60) as r:
                    return json.load(r)
            except urllib.error.HTTPError as e:
                L.ignored(LOG, "get: HTTPError (optional or expected)", e)
                err = self._err(e)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                L.ignored(LOG, "get: URLError/TimeoutError/ConnectionError (optional or expected)", e)
                err = ApiError(0, None, self._clean(str(getattr(e, "reason", e))), retriable=True)
            if err.status == 401 and not refreshed:
                refreshed = True
                self.auth.token(force=True)
                continue
            if not err.retriable or attempt == 4:
                raise err
            self.sleep(min(5 * 2 ** attempt, 120))

    def data(self, path, params=None):
        return self.get(f"{API}/{path}", params)

    def report(self, params):
        return self.get(ANA, {"ids": "channel==MINE", **params})


# ---------------------------------------------------------------- accounts and tokens

def conf_dir():
    return os.path.expanduser("~/.config/navaan")


def token_paths(label):
    """(analytics_token, publishing_token) for an account label. Either may not exist."""
    from navaan_common import account
    if label == "music":
        pub = os.environ.get("NAVAAN_YT_TOKEN", f"{conf_dir()}/youtube_token.json")
        ana = os.environ.get("NAVAAN_YT_ANALYTICS_TOKEN", f"{conf_dir()}/youtube_analytics_token.json")
        return ana, pub
    a = account(label)
    pub = a.get("yt_token") or ""
    ana = None
    try:
        from navaan_common import cfg
        ana = (cfg("accounts") or {}).get(label, {}).get("yt_analytics_token")
    except SystemExit as _e:
        L.ignored(LOG, "token_paths: SystemExit (optional or expected)", _e)
        pass
    if not ana and pub:
        ana = re.sub(r"(\.json)?$", "_analytics.json", pub, count=1)
    return (os.path.expanduser(ana) if ana else None), (os.path.expanduser(pub) if pub else None)


def account_labels():
    from navaan_common import cfg
    return ["music"] + [k for k in (cfg("accounts") or {}) if k != "music"]


def load_auth(label, opener=None):
    ana, pub = token_paths(label)
    for p in (ana, pub):
        if p and os.path.exists(p):
            return Auth(p, opener)
    sys.exit(f"navaan: no YouTube login for '{label}'. Run: python3 {os.path.join(HERE, 'yt_collect.py')} auth --account {label}  (or sign in with publish_youtube.py auth).")


# ---------------------------------------------------------------- collectors

class Ctx:
    def __init__(self, client, conn, label, opts):
        self.client, self.conn, self.label, self.opts = client, conn, label, opts
        self.started = db.utcnow()
        self.now = parse_ts(self.started)
        self.today = self.started[:10]
        self.channel_id = None
        self.uploads = None
        self.videos = {}           # video_id -> dict from videos.list
        self.prev_comments = {}    # video_id -> comment count in the last snapshot before this run
        self.stats, self.errors = {}, []
        self.analytics = bool(client.auth.can_analytics)

    def bump(self, key, n=1):
        self.stats[key] = self.stats.get(key, 0) + n

    def soft(self, where, fn):
        try:
            return fn()
        except ApiError as e:
            if e.auth or e.quota:
                raise
            if e.reason in SKIP_REASONS:
                return None
            self.errors.append({"where": where, "error": str(e)[:300]})
            return None


def collect_channel(ctx):
    items = ctx.client.data("channels", {"part": "snippet,statistics,contentDetails", "mine": "true"}).get("items", [])
    if not items:
        raise ApiError(404, "channelNotFound", "this login has no YouTube channel")
    c = items[0]
    ctx.channel_id = c["id"]
    ctx.uploads = (c.get("contentDetails", {}).get("relatedPlaylists") or {}).get("uploads")
    sn, st = c.get("snippet", {}), c.get("statistics", {})
    db.upsert(ctx.conn, "yt_channels", {"channel_id": ctx.channel_id, "label": ctx.label, "title": sn.get("title"), "handle": sn.get("customUrl"),
                                        "uploads_playlist": ctx.uploads, "created_at": ctx.started, "analytics_ok": 1 if ctx.analytics else 0}, ("channel_id",), keep=("created_at",))
    for metric, key in (("subscribers_count", "subscriberCount"), ("views_total", "viewCount"), ("video_count", "videoCount")):
        v = to_int(st.get(key))
        if v is not None and not (key == "subscriberCount" and st.get("hiddenSubscriberCount")):
            db.upsert(ctx.conn, "yt_daily", {"channel_id": ctx.channel_id, "period_end": ctx.today, "metric": metric, "value": v, "collected_at": ctx.started}, ("channel_id", "period_end", "metric"))
    ctx.conn.commit()
    ctx.bump("channel", 1)


def kind_for(duration_s, title=""):
    return "short" if (duration_s is not None and duration_s <= SHORT_MAX_S) else "video"


def collect_videos(ctx):
    if not ctx.uploads:
        return
    ids, token, pages = [], None, 0
    while pages < ctx.opts["max_pages"]:
        params = {"part": "contentDetails", "playlistId": ctx.uploads, "maxResults": 50}
        if token:
            params["pageToken"] = token
        d = ctx.client.data("playlistItems", params)
        ids += [i["contentDetails"]["videoId"] for i in d.get("items", []) if i.get("contentDetails", {}).get("videoId")]
        token, pages = d.get("nextPageToken"), pages + 1
        if not token:
            break
    seen = set()
    for i in range(0, len(ids), 50):
        for v in ctx.client.data("videos", {"part": "snippet,statistics,contentDetails,status", "id": ",".join(ids[i:i + 50])}).get("items", []):
            vid, sn, st = v["id"], v.get("snippet", {}), v.get("statistics", {})
            dur = iso_duration_s((v.get("contentDetails") or {}).get("duration"))
            ctx.videos[vid] = v
            seen.add(vid)
            prev = db.one(ctx.conn, f"SELECT comments FROM yt_snapshots WHERE video_id = {db.PH} ORDER BY captured_at DESC LIMIT 1", (vid,))
            ctx.prev_comments[vid] = prev["comments"] if prev else None
            th = (sn.get("thumbnails") or {})
            thumb = (th.get("medium") or th.get("default") or {}).get("url")
            db.upsert(ctx.conn, "yt_videos", {"video_id": vid, "channel_id": ctx.channel_id, "slug": None, "kind": kind_for(dur), "title": sn.get("title"), "published_at": norm_ts(sn.get("publishedAt")),
                                              "duration_s": dur, "privacy": (v.get("status") or {}).get("privacyStatus"), "thumbnail_url": thumb, "first_seen_at": ctx.started,
                                              "last_seen_at": ctx.started, "deleted_at": None}, ("video_id",), keep=("first_seen_at", "slug", "kind"), coalesce=("thumbnail_url",))
            db.upsert(ctx.conn, "yt_snapshots", {"video_id": vid, "captured_at": ctx.started, "views": to_int(st.get("viewCount")), "likes": to_int(st.get("likeCount")),
                                                 "comments": to_int(st.get("commentCount"))}, ("video_id", "captured_at"))
            ctx.bump("snapshots")
    if len(ids) == len(seen):  # complete listing: a video missing from the uploads list was deleted
        for r in db.rows(ctx.conn, f"SELECT video_id FROM yt_videos WHERE channel_id = {db.PH} AND deleted_at IS NULL", (ctx.channel_id,)):
            if r["video_id"] not in seen:
                ctx.conn.execute(f"UPDATE yt_videos SET deleted_at = {db.PH} WHERE video_id = {db.PH}", (ctx.started, r["video_id"]))
    ctx.conn.commit()
    ctx.bump("videos", len(seen))


def store_comment(ctx, video_id, c, parent):
    sn = c.get("snippet", {})
    ach = (sn.get("authorChannelId") or {}).get("value")
    row = {"comment_id": c["id"], "video_id": video_id, "parent_id": parent, "username": sn.get("authorDisplayName"), "author_channel_id": ach, "text": sn.get("textDisplay") or sn.get("textOriginal"),
           "posted_at": norm_ts(sn.get("publishedAt")), "like_count": to_int(sn.get("likeCount")), "is_own": 1 if ach and ach == ctx.channel_id else 0, "first_seen_at": ctx.started, "last_seen_at": ctx.started}
    db.upsert(ctx.conn, "yt_comments", row, ("comment_id",), keep=("first_seen_at", "category", "language", "sentiment", "tagged_at", "reply_status"))
    ctx.bump("comments")


def collect_comments(ctx):
    for vid, v in ctx.videos.items():
        count = to_int((v.get("statistics") or {}).get("commentCount"))
        if not count:
            continue
        pub = parse_ts(norm_ts((v.get("snippet") or {}).get("publishedAt")))
        recent = pub and (ctx.now - pub).days <= ctx.opts["comment_days"]
        if not (ctx.opts["force"] or recent or ctx.prev_comments.get(vid) != count):
            continue

        def work(vid=vid):
            token, pages = None, 0
            while pages < ctx.opts["max_pages"]:
                params = {"part": "snippet,replies", "videoId": vid, "maxResults": 100, "order": "time", "textFormat": "plainText"}
                if token:
                    params["pageToken"] = token
                d = ctx.client.data("commentThreads", params)
                for t in d.get("items", []):
                    top = t["snippet"]["topLevelComment"]
                    store_comment(ctx, vid, top, None)
                    got = (t.get("replies") or {}).get("comments", [])
                    if t["snippet"].get("totalReplyCount", 0) > len(got):
                        got, rt = [], None
                        while True:
                            rp = {"part": "snippet", "parentId": top["id"], "maxResults": 100, "textFormat": "plainText"}
                            if rt:
                                rp["pageToken"] = rt
                            rd = ctx.client.data("comments", rp)
                            got += rd.get("items", [])
                            rt = rd.get("nextPageToken")
                            if not rt:
                                break
                    for r in got:
                        store_comment(ctx, vid, r, top["id"])
                token, pages = d.get("nextPageToken"), pages + 1
                if not token:
                    break
        ctx.soft(f"comments {vid}", work)
    ctx.conn.commit()


def analytics_unavailable(ctx, what):
    ctx.stats[what] = "unavailable: sign in with yt_collect.py auth (read only analytics)"


def rows_of(resp):
    cols = [c["name"] for c in resp.get("columnHeaders", [])]
    return [dict(zip(cols, r)) for r in resp.get("rows", [])]


DAILY = {"views": "views", "estimatedMinutesWatched": "minutes_watched", "subscribersGained": "subs_gained", "subscribersLost": "subs_lost", "likes": "likes",
         "comments": "comments", "shares": "shares", "averageViewDuration": "avg_view_s"}


def collect_analytics(ctx):
    if not ctx.analytics:
        analytics_unavailable(ctx, "analytics")
        return
    end = ctx.today
    start = (ctx.now - datetime.timedelta(days=max(1, int(ctx.opts["days"])))).strftime("%Y-%m-%d")
    d = ctx.soft("analytics daily", lambda: ctx.client.report({"startDate": start, "endDate": end, "dimensions": "day", "metrics": ",".join(DAILY), "sort": "day"}))
    for r in rows_of(d or {}):
        for src, name in DAILY.items():
            if r.get(src) is not None:
                db.upsert(ctx.conn, "yt_daily", {"channel_id": ctx.channel_id, "period_end": r["day"], "metric": name, "value": r[src], "collected_at": ctx.started}, ("channel_id", "period_end", "metric"))
        ctx.bump("daily_rows")
    pubs = [norm_ts((v.get("snippet") or {}).get("publishedAt")) for v in ctx.videos.values()]
    pubs = [p for p in pubs if p]
    if pubs:
        vstart = min(pubs)[:10]
        d = ctx.soft("analytics videos", lambda: ctx.client.report({"startDate": vstart, "endDate": end, "dimensions": "video", "sort": "-views", "maxResults": 200,
                                                                    "metrics": "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,subscribersLost,shares"}))
        for r in rows_of(d or {}):
            vid = r.get("video")
            if vid not in ctx.videos:
                continue
            db.upsert(ctx.conn, "yt_snapshots", {"video_id": vid, "captured_at": ctx.started, "minutes_watched": r.get("estimatedMinutesWatched"), "avg_view_s": r.get("averageViewDuration"),
                                                 "avg_view_pct": r.get("averageViewPercentage"), "subs_gained": to_int(r.get("subscribersGained")), "subs_lost": to_int(r.get("subscribersLost")),
                                                 "shares": to_int(r.get("shares"))}, ("video_id", "captured_at"))
            ctx.bump("video_analytics")
    d = ctx.soft("analytics traffic", lambda: ctx.client.report({"startDate": (ctx.now - datetime.timedelta(days=28)).strftime("%Y-%m-%d"), "endDate": end, "dimensions": "insightTrafficSourceType",
                                                                 "metrics": "views,estimatedMinutesWatched", "sort": "-views"}))
    for r in rows_of(d or {}):
        db.upsert(ctx.conn, "yt_traffic", {"channel_id": ctx.channel_id, "captured_on": ctx.today, "source": r["insightTrafficSourceType"], "views": to_int(r.get("views")), "minutes": r.get("estimatedMinutesWatched")},
                  ("channel_id", "captured_on", "source"))
    d90 = (ctx.now - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    d = ctx.soft("analytics demographics", lambda: ctx.client.report({"startDate": d90, "endDate": end, "dimensions": "ageGroup,gender", "metrics": "viewerPercentage"}))
    age, gen = {}, {}
    for r in rows_of(d or {}):
        age[r["ageGroup"]] = age.get(r["ageGroup"], 0) + (r.get("viewerPercentage") or 0)
        gen[r["gender"]] = gen.get(r["gender"], 0) + (r.get("viewerPercentage") or 0)
    for br, vals in (("age", age), ("gender", gen)):
        for b, v in vals.items():
            db.upsert(ctx.conn, "yt_audience", {"channel_id": ctx.channel_id, "captured_on": ctx.today, "breakdown": br, "bucket": b, "value": round(v, 2)}, ("channel_id", "captured_on", "breakdown", "bucket"))
    d = ctx.soft("analytics countries", lambda: ctx.client.report({"startDate": d90, "endDate": end, "dimensions": "country", "metrics": "views", "sort": "-views", "maxResults": 10}))
    for r in rows_of(d or {}):
        db.upsert(ctx.conn, "yt_audience", {"channel_id": ctx.channel_id, "captured_on": ctx.today, "breakdown": "country", "bucket": r["country"], "value": r.get("views")}, ("channel_id", "captured_on", "breakdown", "bucket"))
    ctx.conn.commit()


def collect_retention(ctx):
    if not ctx.analytics:
        analytics_unavailable(ctx, "retention")
        return
    recent = sorted(ctx.videos.values(), key=lambda v: (v.get("snippet") or {}).get("publishedAt", ""), reverse=True)[:ctx.opts["retention_videos"]]
    for v in recent:
        vid = v["id"]
        if (to_int((v.get("statistics") or {}).get("viewCount")) or 0) < 1:
            continue
        pub = norm_ts((v.get("snippet") or {}).get("publishedAt")) or ctx.today
        d = ctx.soft(f"retention {vid}", lambda vid=vid, pub=pub: ctx.client.report({"startDate": pub[:10], "endDate": ctx.today, "dimensions": "elapsedVideoTimeRatio",
                                                                                   "metrics": "audienceWatchRatio,relativeRetentionPerformance", "filters": f"video=={vid}"}))
        n = 0
        for r in rows_of(d or {}):
            db.upsert(ctx.conn, "yt_retention", {"video_id": vid, "captured_on": ctx.today, "ratio": r["elapsedVideoTimeRatio"], "watch_ratio": r.get("audienceWatchRatio"),
                                                 "relative": r.get("relativeRetentionPerformance")}, ("video_id", "captured_on", "ratio"))
            n += 1
        if n:
            ctx.bump("retention_curves")
    ctx.conn.commit()


def link_songs(conn):
    """Tie videos to songs through published.youtube_items (full videos) and published.youtube_short in meta.json. Also refreshes the songs table."""
    import ig_collect
    from navaan_common import songs_root, load_json
    ig_collect.link_songs(conn)
    root, linked = songs_root(), 0
    if not os.path.isdir(root):
        return 0
    for slug in sorted(os.listdir(root)):
        d = os.path.join(root, slug)
        if slug.startswith("_") or not os.path.isdir(d):
            continue
        pub = (load_json(os.path.join(d, "meta.json"), default={}) or {}).get("published") or {}
        pairs = [(i.get("id"), "video") for i in pub.get("youtube_items", []) if isinstance(i, dict)]
        if isinstance(pub.get("youtube_short"), dict) and pub["youtube_short"].get("id"):
            pairs.append((pub["youtube_short"]["id"], "short"))
        for vid, kind in pairs:
            if vid:
                linked += conn.execute(f"UPDATE yt_videos SET slug = {db.PH}, kind = {db.PH} WHERE video_id = {db.PH}", (slug, kind, vid)).rowcount
    conn.commit()
    return linked


def collect(conn, client, label, only=ALL_COLLECTORS, opts=None):
    """Run the chosen collectors for one channel. Returns the run summary that is also stored in yt_runs."""
    o = {"days": 14, "comment_days": 60, "max_pages": 20, "force": False, "retention_videos": 8, "hashtags": False}
    o.update(opts or {})
    ctx = Ctx(client, conn, label, o)
    run_id = uuid.uuid4().hex[:12]
    status = "ok"
    try:
        collect_channel(ctx)   # always: every other step needs the channel id
        db.upsert(conn, "yt_runs", {"run_id": run_id, "channel_id": ctx.channel_id, "started_at": ctx.started, "collectors": ",".join(only), "status": "running"}, ("run_id",))
        conn.commit()
        steps = {"videos": lambda: collect_videos(ctx), "comments": lambda: collect_comments(ctx), "analytics": lambda: collect_analytics(ctx), "retention": lambda: collect_retention(ctx)}
        eff = set(only) | ({"videos"} if {"comments", "analytics", "retention"} & set(only) else set())   # the other steps need the video list
        for name in ALL_COLLECTORS[1:]:
            if name in eff:
                try:
                    steps[name]()
                except ApiError as e:
                    if e.auth or e.quota:
                        raise
                    ctx.errors.append({"where": name, "error": str(e)[:300]})
        if o["hashtags"]:   # public Shorts that use your hashtags, for the best-time card. Weekly, and soft on every error.
            import yt_hashtags
            yt_hashtags.collect_step(ctx)
        link_songs(conn)
        status = "ok" if not ctx.errors else "partial"
    except ApiError as e:
        L.ignored(LOG, "collect: ApiError (optional or expected)", e)
        status = "failed"
        hint = " Sign in again: yt_collect.py auth." if e.auth else " Quota used up for today: try again tomorrow." if e.quota else ""
        ctx.errors.append({"where": "auth" if e.auth else "quota" if e.quota else "run", "error": str(e)[:300] + hint})
    ctx.stats["api_calls"] = client.calls
    if ctx.channel_id:
        if status != "failed":
            conn.execute(f"UPDATE yt_channels SET last_collected_at = {db.PH} WHERE channel_id = {db.PH}", (db.utcnow(), ctx.channel_id))
        db.upsert(conn, "yt_runs", {"run_id": run_id, "channel_id": ctx.channel_id, "started_at": ctx.started, "finished_at": db.utcnow(), "collectors": ",".join(only), "status": status,
                                    "stats_json": json.dumps(ctx.stats), "errors_json": json.dumps(ctx.errors, ensure_ascii=False)}, ("run_id",))
        conn.commit()
    return {"run_id": run_id, "account": label, "channel_id": ctx.channel_id, "status": status, "stats": ctx.stats, "errors": ctx.errors}


# ---------------------------------------------------------------- cli

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
            auth = load_auth(label)
        except SystemExit as e:
            if a.account == "all":
                print(f"{label}: skipped ({e})")
                continue
            raise
        res = collect(conn, Client(auth), label, only, {"days": a.days, "force": a.force, "max_pages": a.max_pages, "hashtags": True})
        print(f"{label}: {res['status']}  {json.dumps(res['stats'])}")
        for e in res["errors"]:
            print(f"  note: {e['where']}: {e['error']}")
        worst = max(worst, 2 if res["status"] == "failed" else 1 if res["status"] == "partial" else 0)
    sys.exit(0 if worst < 2 else 2)


def cmd_status(a):
    conn = db.connect(a.db)
    print("database:", db.db_path(a.db))
    for ch in db.rows(conn, "SELECT * FROM yt_channels ORDER BY label"):
        if a.account not in ("all", ch["label"]):
            continue
        c = ch["channel_id"]
        run = db.one(conn, f"SELECT status, finished_at FROM yt_runs WHERE channel_id = {db.PH} ORDER BY started_at DESC LIMIT 1", (c,)) or {}
        n = lambda sql: db.one(conn, sql, (c,))["n"]
        print(f"{ch['label']} ({ch['title']}): last run {run.get('status')} at {run.get('finished_at')}  analytics login={'yes' if ch['analytics_ok'] else 'no'}")
        print("  videos", n(f"SELECT COUNT(*) AS n FROM yt_videos WHERE channel_id = {db.PH} AND deleted_at IS NULL"),
              " snapshots", n(f"SELECT COUNT(*) AS n FROM yt_snapshots WHERE video_id IN (SELECT video_id FROM yt_videos WHERE channel_id = {db.PH})"),
              " comments waiting", n(WAITING_SQL))


WAITING_SQL = ("SELECT COUNT(*) AS n FROM yt_comments c WHERE c.parent_id IS NULL AND c.is_own = 0 AND c.video_id IN (SELECT video_id FROM yt_videos WHERE channel_id = " + db.PH + ") "
               "AND NOT EXISTS (SELECT 1 FROM yt_comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1)")


def cmd_link(a):
    print("videos linked to songs:", link_songs(db.connect(a.db)))


def cmd_auth(a):
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as _e:
        L.ignored(LOG, "cmd_auth: ImportError (optional or expected)", _e)
        sys.exit("navaan: pip install google-auth-oauthlib")
    ana, pub = token_paths(a.account)
    secret = os.environ.get("NAVAAN_YT_CLIENT_SECRETS", f"{conf_dir()}/youtube_client_secret.json")
    if a.account != "music":
        from navaan_common import account
        secret = account(a.account).get("yt_secret") or secret
    if not os.path.exists(secret):
        sys.exit(f"navaan: client secret not found at {secret}. Same Google Cloud OAuth client as publishing; enable the YouTube Analytics API too.")
    creds = InstalledAppFlow.from_client_secrets_file(secret, READ_SCOPES).run_local_server(port=0)
    os.makedirs(os.path.dirname(ana), exist_ok=True)
    with open(ana, "w") as f:
        f.write(creds.to_json())
    os.chmod(ana, 0o600)
    print(f"read only analytics token saved: {ana}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("collect"); c.add_argument("--account", default="music"); c.add_argument("--only"); c.add_argument("--days", type=int, default=14)
    c.add_argument("--max-pages", type=int, default=20); c.add_argument("--force", action="store_true"); c.set_defaults(fn=cmd_collect)
    s = sp.add_parser("status"); s.add_argument("--account", default="all"); s.set_defaults(fn=cmd_status)
    sp.add_parser("link").set_defaults(fn=cmd_link)
    au = sp.add_parser("auth"); au.add_argument("--account", default="music"); au.set_defaults(fn=cmd_auth)
    sp.add_parser("dbpath").set_defaults(fn=lambda a: print(db.db_path(a.db)))
    a = ap.parse_args()
    a.fn(a)
