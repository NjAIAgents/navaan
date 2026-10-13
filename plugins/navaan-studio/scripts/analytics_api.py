"""analytics_api.py  read-only queries and the Collect now job behind the portal's Analytics page.

overview(account, days) returns one JSON-ready dict built from the analytics database that ig_collect.py fills.
start_collect(account) runs ig_collect.py in a child process so the portal never blocks and a collector exit cannot stop the server.
Nothing here writes to Instagram."""
import os, re, sys, json, subprocess, threading, time
import analytics_db as db

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECT = {"running": False, "account": None, "rc": None, "tail": "", "started": 0, "finished": 0}
ASK = {"running": False, "account": None, "rc": None, "tail": "", "started": 0, "finished": 0}
YT_COLLECT = {"running": False, "account": None, "rc": None, "tail": "", "started": 0, "finished": 0}
YT_ASK = {"running": False, "account": None, "rc": None, "tail": "", "started": 0, "finished": 0}
PLATFORMS = ("instagram", "youtube")
VIDEO_OK = re.compile(r"^[A-Za-z0-9_-]{2,20}$")


def _state(platform):
    """(collect state, ask state) for a platform. Each platform runs its own collector and advisor at the same time."""
    if platform not in PLATFORMS:
        raise ValueError("platform must be instagram or youtube")
    return (YT_COLLECT, YT_ASK) if platform == "youtube" else (COLLECT, ASK)
ASK_TOOLS = ["Read", "Glob", "Grep", "WebSearch", "WebFetch", "Bash(python3:*)", "Bash(python:*)", "Bash(ls:*)", "Bash(cat:*)"]
ACCOUNT_OK = re.compile(r"^(all|[a-z0-9_-]{1,30})$")
SLUG_OK = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
MEDIA_OK = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def _in(n):
    return ",".join([db.PH] * n)


def _pct(a, b):
    return round(100.0 * a / b, 2) if a is not None and b else None


def overview(account="all", days=30, db_file=None):
    days = max(1, min(int(days or 30), 365))
    try:
        conn = db.connect(db_file, readonly=True)
    except Exception as e:
        return {"empty": True, "reason": "db_error", "error": str(e), "db": db.db_path(db_file), "collect": dict(COLLECT)}
    if conn is None:
        return {"empty": True, "reason": "no_database", "db": db.db_path(db_file), "collect": dict(COLLECT)}
    try:
        accounts = db.rows(conn, "SELECT ig_user_id, label, username, last_collected_at FROM accounts ORDER BY CASE WHEN label = 'music' THEN 0 ELSE 1 END, label")
        if not accounts:
            return {"empty": True, "reason": "no_data", "db": db.db_path(db_file), "collect": dict(COLLECT)}
        sel = [a for a in accounts if account in ("all", a["label"])] or accounts
        uids = [a["ig_user_id"] for a in sel]
        marks = _in(len(uids))
        start = (time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400)))

        def series(metric):
            return [[r["d"], r["v"]] for r in db.rows(conn, f"SELECT period_end AS d, SUM(value) AS v FROM account_daily WHERE metric = {db.PH} "
                                                          f"AND ig_user_id IN ({marks}) AND period_end >= {db.PH} GROUP BY period_end ORDER BY period_end", [metric, *uids, start])]

        def total(metric):
            r = db.one(conn, f"SELECT SUM(value) AS v FROM account_daily WHERE metric = {db.PH} AND ig_user_id IN ({marks}) AND period_end >= {db.PH}", [metric, *uids, start])
            return r["v"]
        followers = series("followers_count")
        kpis = {"followers": followers[-1][1] if followers else None,
                "followers_change": (followers[-1][1] - followers[0][1]) if len(followers) > 1 else None,
                "views": total("views"), "interactions": total("total_interactions"), "accounts_engaged": total("accounts_engaged"),
                "waiting": db.one(conn, f"SELECT COUNT(*) AS n FROM comments c WHERE c.parent_id IS NULL AND c.is_own = 0 AND c.hidden = 0 "
                                        f"AND c.media_id IN (SELECT media_id FROM media WHERE ig_user_id IN ({marks})) "
                                        f"AND NOT EXISTS (SELECT 1 FROM comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1)", uids)["n"]}
        posts = db.rows(conn, f"""SELECT m.media_id, m.slug, m.permalink, m.caption, m.posted_at, m.product_type, a.label AS account, s.title, s.language, s.genre, s.item_type,
            sn.captured_at, sn.like_count, sn.comments_count, sn.reach, sn.views, sn.saved, sn.shares, sn.total_interactions, sn.avg_watch_time_ms, sn.skip_rate
            FROM media m JOIN accounts a ON a.ig_user_id = m.ig_user_id LEFT JOIN songs s ON s.slug = m.slug
            LEFT JOIN media_snapshots sn ON sn.media_id = m.media_id AND sn.captured_at = (SELECT MAX(captured_at) FROM media_snapshots WHERE media_id = m.media_id)
            WHERE m.deleted_at IS NULL AND m.ig_user_id IN ({marks}) ORDER BY m.posted_at DESC LIMIT 100""", uids)
        for p in posts:
            p["caption"] = (p["caption"] or "").strip().splitlines()[0][:60] if (p["caption"] or "").strip() else ""
            p["save_rate"] = _pct(p["saved"], p["reach"])
            p["engagement_rate"] = _pct(p["total_interactions"], p["reach"])
            p["avg_watch_s"] = round(p["avg_watch_time_ms"] / 1000.0, 1) if p["avg_watch_time_ms"] is not None else None
            p["trend"] = [r["views"] for r in db.rows(conn, f"SELECT views FROM media_snapshots WHERE media_id = {db.PH} AND views IS NOT NULL ORDER BY captured_at DESC LIMIT 12", (p["media_id"],))][::-1]
        patterns = {}
        for key in ("language", "genre"):
            groups = {}
            for p in posts:
                if p["views"] is not None and p.get(key):
                    groups.setdefault(p[key], []).append(p)
            patterns[key] = sorted(({"name": k, "posts": len(v), "avg_views": round(sum(x["views"] for x in v) / len(v)),
                                     "avg_save_rate": round(sum(x["save_rate"] or 0 for x in v) / len(v), 2)} for k, v in groups.items()), key=lambda r: -r["avg_views"])
        waiting = db.rows(conn, f"""SELECT c.comment_id, c.username, c.text, c.posted_at, m.permalink, COALESCE(s.title, m.slug, m.media_id) AS post
            FROM comments c JOIN media m ON m.media_id = c.media_id LEFT JOIN songs s ON s.slug = m.slug
            WHERE c.parent_id IS NULL AND c.is_own = 0 AND c.hidden = 0 AND m.ig_user_id IN ({marks})
            AND NOT EXISTS (SELECT 1 FROM comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1) ORDER BY c.posted_at DESC LIMIT 8""", uids)
        aud = {}
        for r in db.rows(conn, f"""SELECT breakdown, bucket, SUM(value) AS v FROM audience a WHERE ig_user_id IN ({marks})
            AND captured_on = (SELECT MAX(captured_on) FROM audience b WHERE b.ig_user_id = a.ig_user_id AND b.breakdown = a.breakdown)
            GROUP BY breakdown, bucket ORDER BY v DESC""", uids):
            aud.setdefault(r["breakdown"], []).append([r["bucket"], r["v"]])
        hours = [[r["hour"], r["v"]] for r in db.rows(conn, f"""SELECT hour, SUM(followers) AS v FROM online_hours o WHERE ig_user_id IN ({marks})
            AND captured_on = (SELECT MAX(captured_on) FROM online_hours q WHERE q.ig_user_id = o.ig_user_id) GROUP BY hour ORDER BY hour""", uids)]
        runs = db.rows(conn, f"""SELECT r.started_at, r.finished_at, r.status, r.stats_json, r.errors_json, a.label FROM collector_runs r
            LEFT JOIN accounts a ON a.ig_user_id = r.ig_user_id WHERE r.ig_user_id IN ({marks}) ORDER BY r.started_at DESC LIMIT 6""", uids)
        for r in runs:
            r["stats"] = json.loads(r.pop("stats_json") or "{}")
            errs = json.loads(r.pop("errors_json") or "[]")
            r["errors"] = len(errs)
            r["first_error"] = (errs[0]["where"] + ": " + errs[0]["error"])[:200] if errs else ""
        reco = recommendations(conn, uids)
        peers = peer_block(conn, uids)
        try: hashtags = hashtag_block(conn, uids)
        except Exception as e: hashtags = {"error": str(e)[:200]}
        try:
            import besttime
            bt = {a["label"]: besttime.analyze(conn, a["label"]) for a in sel}
        except Exception as e: bt = {"error": str(e)[:200]}
        return {"empty": False, "reco": reco, "peers": peers, "hashtags": hashtags, "besttime": bt, "accounts": accounts, "account": account, "days": days, "kpis": kpis,
                "series": {"followers": followers, "views": series("views"), "reach": series("reach"), "interactions": series("total_interactions")},
                "posts": posts, "patterns": patterns, "waiting": waiting, "audience": aud, "hours": hours, "runs": runs,
                "db": db.db_path(db_file), "collect": dict(COLLECT)}
    finally:
        conn.close()


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    n = len(xs)
    return None if not n else xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def song_view(slug, db_file=None):
    """Instagram numbers for one song or short: every post linked to it, its history, how it compares with the account, comments, findings."""
    if not SLUG_OK.match(slug or ""):
        raise ValueError("bad slug")
    try:
        conn = db.connect(db_file, readonly=True)
    except Exception as e:
        return {"empty": True, "reason": "db_error", "error": str(e), "collect": dict(COLLECT)}
    if conn is None:
        return {"empty": True, "reason": "no_database", "collect": dict(COLLECT)}
    try:
        posts = db.rows(conn, f"""SELECT m.media_id, m.ig_user_id, m.permalink, m.caption, m.posted_at, m.product_type, a.label AS account, a.username,
            sn.captured_at, sn.like_count, sn.comments_count, sn.reach, sn.views, sn.saved, sn.shares, sn.total_interactions, sn.avg_watch_time_ms, sn.skip_rate, sn.follows, sn.profile_visits
            FROM media m JOIN accounts a ON a.ig_user_id = m.ig_user_id
            LEFT JOIN media_snapshots sn ON sn.media_id = m.media_id AND sn.captured_at = (SELECT MAX(captured_at) FROM media_snapshots WHERE media_id = m.media_id)
            WHERE m.slug = {db.PH} AND m.deleted_at IS NULL ORDER BY m.posted_at""", (slug,))
        for p in posts:
            uid = p["ig_user_id"]
            peers = db.rows(conn, f"""SELECT sn.views, sn.reach, sn.saved, sn.shares, sn.avg_watch_time_ms FROM media m JOIN media_snapshots sn ON sn.media_id = m.media_id
                AND sn.captured_at = (SELECT MAX(captured_at) FROM media_snapshots WHERE media_id = m.media_id)
                WHERE m.ig_user_id = {db.PH} AND m.deleted_at IS NULL AND m.media_id != {db.PH} AND sn.views IS NOT NULL""", (uid, p["media_id"]))
            med_v = _median([r["views"] for r in peers])
            med_sr = _median([(100.0 * r["saved"] / r["reach"]) for r in peers if r["saved"] is not None and r["reach"]])
            p["save_rate"] = _pct(p["saved"], p["reach"])
            p["engagement_rate"] = _pct(p["total_interactions"], p["reach"])
            p["avg_watch_s"] = round(p["avg_watch_time_ms"] / 1000.0, 1) if p["avg_watch_time_ms"] is not None else None
            p["history"] = db.rows(conn, f"SELECT captured_at, views, reach, saved, shares, like_count, comments_count FROM media_snapshots WHERE media_id = {db.PH} ORDER BY captured_at", (p["media_id"],))[-60:]
            better = len([r for r in peers if p["views"] is not None and r["views"] > p["views"]])
            p["compare"] = {"account_posts": len(peers) + (1 if p["views"] is not None else 0), "views_rank": (better + 1) if p["views"] is not None else None,
                            "median_views": med_v, "views_vs_median": round(p["views"] / med_v, 2) if p["views"] is not None and med_v else None,
                            "median_save_rate": None if med_sr is None else round(med_sr, 2),
                            "median_avg_watch_s": None if _median([r["avg_watch_time_ms"] for r in peers]) is None else round(_median([r["avg_watch_time_ms"] for r in peers]) / 1000.0, 1)}
            p["comments_waiting"] = db.rows(conn, f"""SELECT c.username, c.text, c.posted_at FROM comments c WHERE c.media_id = {db.PH} AND c.parent_id IS NULL AND c.is_own = 0 AND c.hidden = 0
                AND NOT EXISTS (SELECT 1 FROM comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1) ORDER BY c.posted_at DESC LIMIT 5""", (p["media_id"],))
            p["comments_total"] = db.one(conn, f"SELECT COUNT(*) AS n FROM comments WHERE media_id = {db.PH} AND is_own = 0", (p["media_id"],))["n"]
            try:
                fs = db.rows(conn, f"SELECT finding_id, rule_id, severity, title, detail FROM findings WHERE subject = {db.PH} AND status = 'open'", (p["media_id"],))
                ids = {f["finding_id"] for f in fs}
                recs = [r for r in db.rows(conn, f"SELECT rec_id, priority, title, action, status, finding_ids FROM recommendations WHERE ig_user_id = {db.PH} AND status IN ('open','done')", (uid,))
                        if ids & set(json.loads(r["finding_ids"] or "[]"))]
                for r in recs:
                    r.pop("finding_ids")
                p["findings"], p["recommendations"] = fs, recs
            except Exception:
                p["findings"], p["recommendations"] = [], []
        unlinked = []
        if not posts:
            unlinked = db.rows(conn, f"""SELECT m.media_id, m.permalink, m.caption, m.posted_at, m.product_type, a.label AS account FROM media m JOIN accounts a ON a.ig_user_id = m.ig_user_id
                WHERE m.slug IS NULL AND m.deleted_at IS NULL ORDER BY m.posted_at DESC LIMIT 25""")
            for u in unlinked:
                u["caption"] = (u["caption"] or "").strip().splitlines()[0][:70] if (u["caption"] or "").strip() else ""
        tot = {k: sum((p[k] or 0) for p in posts) for k in ("views", "reach", "saved", "shares", "like_count", "comments_count")}
        try:
            yt = yt_song(conn, slug)
        except Exception:
            yt = {"videos": [], "unlinked": [], "totals": {}}
        return {"empty": False, "slug": slug, "posts": posts, "totals": tot, "unlinked": unlinked, "youtube": yt, "collect": dict(COLLECT), "yt_collect": dict(YT_COLLECT)}
    finally:
        conn.close()


def by_song(db_file=None):
    """{slug: {posts, views, reach, saved, likes, yt_videos, yt_views}} from the latest snapshot of every linked post and video. Empty dict when there is no database."""
    try:
        conn = db.connect(db_file, readonly=True)
    except Exception:
        return {}
    if conn is None:
        return {}
    try:
        out = {}
        for r in db.rows(conn, """SELECT m.slug, COUNT(*) AS posts, SUM(sn.views) AS views, SUM(sn.reach) AS reach, SUM(sn.saved) AS saved, SUM(sn.like_count) AS likes
            FROM media m LEFT JOIN media_snapshots sn ON sn.media_id = m.media_id AND sn.captured_at = (SELECT MAX(captured_at) FROM media_snapshots WHERE media_id = m.media_id)
            WHERE m.slug IS NOT NULL AND m.deleted_at IS NULL GROUP BY m.slug"""):
            out[r.pop("slug")] = r
        try:
            for r in db.rows(conn, f"""SELECT v.slug, COUNT(*) AS videos, SUM(sn.views) AS views FROM yt_videos v {LATEST_YT}
                WHERE v.slug IS NOT NULL AND v.deleted_at IS NULL GROUP BY v.slug"""):
                e = out.setdefault(r["slug"], {"posts": 0, "views": None, "reach": None, "saved": None, "likes": None})
                e["yt_videos"], e["yt_views"] = r["videos"], r["views"]
        except Exception:
            pass
        return out
    finally:
        conn.close()


def link_post(media_id, slug, db_file=None):
    """Tie an Instagram post to a song or short by hand (slug empty to unlink). Survives later collects."""
    if not MEDIA_OK.match(media_id or ""):
        raise ValueError("bad media id")
    if slug and not SLUG_OK.match(slug):
        raise ValueError("bad slug")
    conn = db.connect(db_file)
    try:
        if not db.one(conn, f"SELECT 1 AS ok FROM media WHERE media_id = {db.PH}", (media_id,)):
            raise ValueError("no such post in the database")
        if slug:
            conn.execute(f"INSERT INTO songs (slug, updated_at) VALUES ({db.PH}, {db.PH}) ON CONFLICT (slug) DO NOTHING", (slug, db.utcnow()))
        conn.execute(f"UPDATE media SET slug = {db.PH} WHERE media_id = {db.PH}", (slug or None, media_id))
        conn.commit()
    finally:
        conn.close()


LATEST_YT = ("LEFT JOIN yt_snapshots sn ON sn.video_id = v.video_id AND sn.captured_at = "
             "(SELECT MAX(captured_at) FROM yt_snapshots WHERE video_id = v.video_id)")
SNAP_COLS = "sn.captured_at, sn.views, sn.likes, sn.comments, sn.minutes_watched, sn.avg_view_s, sn.avg_view_pct, sn.subs_gained, sn.subs_lost, sn.shares"


def yt_url(video_id, kind):
    return f"https://www.youtube.com/shorts/{video_id}" if kind == "short" else f"https://www.youtube.com/watch?v={video_id}"


def yt_overview(account="all", days=30, db_file=None):
    """Everything the YouTube tab of the Analytics page shows, built from the tables yt_collect.py fills."""
    days = max(1, min(int(days or 30), 365))
    collect = dict(YT_COLLECT)
    try:
        conn = db.connect(db_file, readonly=True)
    except Exception as e:
        return {"empty": True, "reason": "db_error", "error": str(e), "db": db.db_path(db_file), "collect": collect}
    if conn is None:
        return {"empty": True, "reason": "no_database", "db": db.db_path(db_file), "collect": collect}
    try:
        try:
            channels = db.rows(conn, "SELECT channel_id, label, title, handle, last_collected_at, analytics_ok FROM yt_channels ORDER BY CASE WHEN label = 'music' THEN 0 ELSE 1 END, label")
        except Exception:
            channels = []
        if not channels:
            return {"empty": True, "reason": "no_data", "db": db.db_path(db_file), "collect": collect}
        sel = [c for c in channels if account in ("all", c["label"])] or channels
        cids = [c["channel_id"] for c in sel]
        marks = _in(len(cids))
        start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))

        def series(metric):
            return [[r["d"], r["v"]] for r in db.rows(conn, f"SELECT period_end AS d, SUM(value) AS v FROM yt_daily WHERE metric = {db.PH} "
                                                          f"AND channel_id IN ({marks}) AND period_end >= {db.PH} GROUP BY period_end ORDER BY period_end", [metric, *cids, start])]
        subs, views, minutes, gained = series("subscribers_count"), series("views"), series("minutes_watched"), series("subs_gained")
        lost = series("subs_lost")
        total = lambda xs: round(sum(v or 0 for _, v in xs), 1) if xs else None
        waiting_n = db.one(conn, f"SELECT COUNT(*) AS n FROM yt_comments c WHERE c.parent_id IS NULL AND c.is_own = 0 AND c.video_id IN "
                                 f"(SELECT video_id FROM yt_videos WHERE channel_id IN ({marks})) AND NOT EXISTS "
                                 f"(SELECT 1 FROM yt_comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1)", cids)["n"]
        kpis = {"subscribers": subs[-1][1] if subs else None, "subscribers_change": (subs[-1][1] - subs[0][1]) if len(subs) > 1 else None,
                "views": total(views), "watch_hours": None if not minutes else round(total(minutes) / 60.0, 1),
                "subs_gained": total(gained), "subs_net": None if not gained else round((total(gained) or 0) - (total(lost) or 0)), "waiting": waiting_n}
        videos = db.rows(conn, f"""SELECT v.video_id, v.channel_id, v.slug, v.kind, v.title, v.published_at, v.duration_s, v.privacy, c.label AS account, s.title AS song, s.language, s.genre, {SNAP_COLS}
            FROM yt_videos v JOIN yt_channels c ON c.channel_id = v.channel_id LEFT JOIN songs s ON s.slug = v.slug {LATEST_YT}
            WHERE v.deleted_at IS NULL AND v.channel_id IN ({marks}) ORDER BY v.published_at DESC LIMIT 100""", cids)
        for v in videos:
            v["name"] = v["song"] or v["title"] or v["video_id"]
            v["url"] = yt_url(v["video_id"], v["kind"])
            v["subs_per_1000"] = None if v["subs_gained"] is None or not v["views"] else round(1000.0 * v["subs_gained"] / v["views"], 2)
            v["trend"] = [r["views"] for r in db.rows(conn, f"SELECT views FROM yt_snapshots WHERE video_id = {db.PH} AND views IS NOT NULL ORDER BY captured_at DESC LIMIT 12", (v["video_id"],))][::-1]
        patterns = {}
        for key in ("language", "genre", "kind"):
            groups = {}
            for v in videos:
                if v["views"] is not None and v.get(key) and v["privacy"] == "public":
                    groups.setdefault(v[key], []).append(v)
            patterns[key] = sorted(({"name": k, "videos": len(g), "avg_views": round(sum(x["views"] for x in g) / len(g)),
                                     "avg_view_pct": (lambda ps: round(sum(ps) / len(ps), 1) if ps else None)([x["avg_view_pct"] for x in g if x["avg_view_pct"] is not None])}
                                    for k, g in groups.items()), key=lambda r: -r["avg_views"])
        traffic = db.rows(conn, f"""SELECT source, SUM(views) AS views, SUM(minutes) AS minutes FROM yt_traffic t WHERE channel_id IN ({marks})
            AND captured_on = (SELECT MAX(captured_on) FROM yt_traffic q WHERE q.channel_id = t.channel_id) GROUP BY source ORDER BY views DESC""", cids)
        aud = {}
        for r in db.rows(conn, f"""SELECT breakdown, bucket, SUM(value) AS v FROM yt_audience a WHERE channel_id IN ({marks})
            AND captured_on = (SELECT MAX(captured_on) FROM yt_audience b WHERE b.channel_id = a.channel_id AND b.breakdown = a.breakdown)
            GROUP BY breakdown, bucket ORDER BY v DESC""", cids):
            aud.setdefault(r["breakdown"], []).append([r["bucket"], r["v"]])
        retention, names = [], {v["video_id"]: v for v in videos}
        for vid in [v["video_id"] for v in sorted(videos, key=lambda x: -(x["views"] or 0))]:
            pts = db.rows(conn, f"""SELECT ratio, watch_ratio FROM yt_retention WHERE video_id = {db.PH}
                AND captured_on = (SELECT MAX(captured_on) FROM yt_retention WHERE video_id = {db.PH}) ORDER BY ratio""", (vid, vid))
            if pts:
                retention.append({"video_id": vid, "name": names[vid]["name"], "kind": names[vid]["kind"], "points": [[p["ratio"], p["watch_ratio"]] for p in pts]})
            if len(retention) >= 4:
                break
        waiting = db.rows(conn, f"""SELECT c.comment_id, c.username, c.text, c.posted_at, v.video_id, v.kind, COALESCE(s.title, v.title, v.video_id) AS video
            FROM yt_comments c JOIN yt_videos v ON v.video_id = c.video_id LEFT JOIN songs s ON s.slug = v.slug
            WHERE c.parent_id IS NULL AND c.is_own = 0 AND v.channel_id IN ({marks})
            AND NOT EXISTS (SELECT 1 FROM yt_comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1) ORDER BY c.posted_at DESC LIMIT 8""", cids)
        for w in waiting:
            w["url"] = yt_url(w["video_id"], w["kind"])
        runs = db.rows(conn, f"""SELECT r.started_at, r.finished_at, r.status, r.stats_json, r.errors_json, c.label FROM yt_runs r
            LEFT JOIN yt_channels c ON c.channel_id = r.channel_id WHERE r.channel_id IN ({marks}) ORDER BY r.started_at DESC LIMIT 6""", cids)
        for r in runs:
            r["stats"] = json.loads(r.pop("stats_json") or "{}")
            errs = json.loads(r.pop("errors_json") or "[]")
            r["errors"] = len(errs)
            r["first_error"] = (errs[0]["where"] + ": " + errs[0]["error"])[:200] if errs else ""
        return {"empty": False, "reco": recommendations(conn, cids, "youtube"), "accounts": channels, "account": account, "days": days, "kpis": kpis,
                "analytics_ok": all(c["analytics_ok"] for c in sel),
                "series": {"subscribers": subs, "views": views, "watch_hours": [[d, round((v or 0) / 60.0, 1)] for d, v in minutes], "subs_gained": gained},
                "videos": videos, "patterns": patterns, "traffic": traffic, "audience": aud, "retention": retention, "waiting": waiting, "runs": runs,
                "db": db.db_path(db_file), "collect": dict(YT_COLLECT)}
    finally:
        conn.close()


def yt_song(conn, slug):
    """YouTube numbers for one song: every video linked to it with history, retention, comparison with the channel's same kind of video, comments, findings."""
    vids = db.rows(conn, f"""SELECT v.video_id, v.channel_id, v.kind, v.title, v.published_at, v.duration_s, v.privacy, c.label AS account, c.title AS channel, {SNAP_COLS}
        FROM yt_videos v JOIN yt_channels c ON c.channel_id = v.channel_id {LATEST_YT}
        WHERE v.slug = {db.PH} AND v.deleted_at IS NULL ORDER BY v.published_at""", (slug,))
    for v in vids:
        vid, cid = v["video_id"], v["channel_id"]
        peers = db.rows(conn, f"""SELECT sn.views, sn.avg_view_pct, sn.avg_view_s, sn.subs_gained FROM yt_videos x JOIN yt_snapshots sn ON sn.video_id = x.video_id
            AND sn.captured_at = (SELECT MAX(captured_at) FROM yt_snapshots WHERE video_id = x.video_id)
            WHERE x.channel_id = {db.PH} AND x.kind = {db.PH} AND x.privacy = 'public' AND x.deleted_at IS NULL AND x.video_id != {db.PH} AND sn.views IS NOT NULL""", (cid, v["kind"], vid))
        med_v, med_p = _median([r["views"] for r in peers]), _median([r["avg_view_pct"] for r in peers])
        better = len([r for r in peers if v["views"] is not None and r["views"] > v["views"]])
        v["url"] = yt_url(vid, v["kind"])
        v["subs_per_1000"] = None if v["subs_gained"] is None or not v["views"] else round(1000.0 * v["subs_gained"] / v["views"], 2)
        v["compare"] = {"same_kind_videos": len(peers) + (1 if v["views"] is not None else 0), "views_rank": (better + 1) if v["views"] is not None else None,
                        "median_views": med_v, "views_vs_median": round(v["views"] / med_v, 2) if v["views"] is not None and med_v else None,
                        "median_avg_view_pct": None if med_p is None else round(med_p, 1)}
        v["history"] = db.rows(conn, f"SELECT captured_at, views, likes, comments, minutes_watched, avg_view_pct FROM yt_snapshots WHERE video_id = {db.PH} ORDER BY captured_at", (vid,))[-60:]
        v["retention"] = [[r["ratio"], r["watch_ratio"]] for r in db.rows(conn, f"""SELECT ratio, watch_ratio FROM yt_retention WHERE video_id = {db.PH}
            AND captured_on = (SELECT MAX(captured_on) FROM yt_retention WHERE video_id = {db.PH}) ORDER BY ratio""", (vid, vid))]
        v["comments_waiting"] = db.rows(conn, f"""SELECT c.username, c.text, c.posted_at FROM yt_comments c WHERE c.video_id = {db.PH} AND c.parent_id IS NULL AND c.is_own = 0
            AND NOT EXISTS (SELECT 1 FROM yt_comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1) ORDER BY c.posted_at DESC LIMIT 5""", (vid,))
        v["comments_total"] = db.one(conn, f"SELECT COUNT(*) AS n FROM yt_comments WHERE video_id = {db.PH} AND is_own = 0", (vid,))["n"]
        try:
            fs = db.rows(conn, f"SELECT finding_id, rule_id, severity, title, detail FROM findings WHERE subject = {db.PH} AND status = 'open'", (vid,))
            ids = {f["finding_id"] for f in fs}
            recs = [r for r in db.rows(conn, f"SELECT rec_id, priority, title, action, status, finding_ids FROM recommendations WHERE ig_user_id = {db.PH} AND status IN ('open','done')", (cid,))
                    if ids & set(json.loads(r["finding_ids"] or "[]"))]
            for r in recs:
                r.pop("finding_ids")
            v["findings"], v["recommendations"] = fs, recs
        except Exception:
            v["findings"], v["recommendations"] = [], []
    unlinked = []
    if not vids:
        unlinked = db.rows(conn, f"""SELECT v.video_id, v.kind, v.title, v.published_at, c.label AS account FROM yt_videos v JOIN yt_channels c ON c.channel_id = v.channel_id
            WHERE v.slug IS NULL AND v.deleted_at IS NULL ORDER BY v.published_at DESC LIMIT 25""")
        for u in unlinked:
            u["url"] = yt_url(u["video_id"], u["kind"])
    tot = {k: sum((v[k] or 0) for v in vids) for k in ("views", "likes", "comments", "minutes_watched", "subs_gained")}
    return {"videos": vids, "unlinked": unlinked, "totals": tot}


def link_video(video_id, slug, db_file=None):
    """Tie a YouTube video to a song or short by hand (slug empty to unlink). Survives later collects."""
    if not VIDEO_OK.match(video_id or ""):
        raise ValueError("bad video id")
    if slug and not SLUG_OK.match(slug):
        raise ValueError("bad slug")
    conn = db.connect(db_file)
    try:
        if not db.one(conn, f"SELECT 1 AS ok FROM yt_videos WHERE video_id = {db.PH}", (video_id,)):
            raise ValueError("no such video in the database")
        if slug:
            conn.execute(f"INSERT INTO songs (slug, updated_at) VALUES ({db.PH}, {db.PH}) ON CONFLICT (slug) DO NOTHING", (slug, db.utcnow()))
        conn.execute(f"UPDATE yt_videos SET slug = {db.PH} WHERE video_id = {db.PH}", (slug or None, video_id))
        conn.commit()
    finally:
        conn.close()


STOP_TAGS = {"fyp", "foryou", "foryoupage", "reels", "reel", "viral", "trending", "explore", "explorepage", "instagood", "instagram", "love", "follow", "like",
             "ad", "ads", "sponsored", "paidpartnership", "collab", "giveaway", "sale", "link", "linkinbio"}


def hashtag_block(conn, uids, write=False):
    """What tags the strongest peer posts carry that we do not use yet, and how our own tags did.
    Peer posts are ranked inside each peer by likes plus comments, so a big account cannot drown a small one; a tag scores by how many
    peers use it in their top 40 percent of posts. With write=True the result is saved as hashtags.json next to the songs folder, where the
    caption skills read it."""
    import re, datetime
    tags = lambda t: {x.lower() for x in re.findall(r"#(\w+)", t or "")} - STOP_TAGS
    peers = {r["username"]: r for r in db.rows(conn, "SELECT username, note, followers_count FROM peers")}
    by = {}
    for m in db.rows(conn, "SELECT username, caption, like_count, comments_count FROM peer_media"):
        by.setdefault(m["username"], []).append(m)
    group_of = lambda note: "inspiration" if "inspiration" in (note or "").lower() else "music"
    score = {"music": {}, "inspiration": {}}
    for u, ms in by.items():
        g = group_of(peers.get(u, {}).get("note"))
        ms = sorted(ms, key=lambda m: -((m["like_count"] or 0) + (m["comments_count"] or 0)))
        top = ms[:max(3, int(len(ms) * 0.4))]
        seen = {}
        own_name = re.sub(r"[^a-z0-9]", "", u.lower())
        for m in top:
            for t in tags(m["caption"]):
                if len(t) < 3 or t in own_name or own_name in t or t.isdigit(): continue  # a peer's own brand tag helps nobody else
                seen[t] = seen.get(t, 0) + 1
        for t, n in seen.items():
            e = score[g].setdefault(t, {"tag": t, "peers": [], "posts": 0})
            e["peers"].append(u); e["posts"] += n
    own_tags = {}
    own_rows = db.rows(conn, f"""SELECT a.label, m.caption, sn.views, sn.reach FROM media m JOIN accounts a ON a.ig_user_id = m.ig_user_id
        LEFT JOIN media_snapshots sn ON sn.media_id = m.media_id AND sn.captured_at = (SELECT MAX(captured_at) FROM media_snapshots WHERE media_id = m.media_id)
        WHERE m.deleted_at IS NULL AND m.ig_user_id IN ({_in(len(uids))})""", uids)
    for r in own_rows:
        for t in tags(r["caption"]):
            e = own_tags.setdefault((r["label"], t), {"tag": t, "label": r["label"], "uses": 0, "views": []})
            e["uses"] += 1
            if r["views"] is not None: e["views"].append(r["views"])
    own = {}
    for (lab, t), e in own_tags.items():
        own.setdefault(lab, []).append({"tag": t, "uses": e["uses"], "avg_views": (round(sum(e["views"]) / len(e["views"])) if e["views"] else None)})
    for lab in own: own[lab].sort(key=lambda x: -(x["avg_views"] or 0))
    used = {lab: {x["tag"] for x in rows} for lab, rows in own.items()}
    suggested = {}
    for g, d in score.items():
        rows = sorted(d.values(), key=lambda e: (-len(set(e["peers"])), -e["posts"]))
        suggested[g] = [{"tag": e["tag"], "peers": sorted(set(e["peers"])), "posts": e["posts"], "in_use": e["tag"] in used.get(g, set())} for e in rows[:12]]
    out = {"suggested": suggested, "own": own, "peer_posts_with_tags": sum(1 for ms in by.values() for m in ms if tags(m["caption"])),
           "updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if write:
        try:
            import navaan_common as C
            path = os.path.join(os.path.dirname(C.songs_root()), "hashtags.json")
            json.dump(out, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            out["file"] = path
        except Exception as e:
            out["file_error"] = str(e)[:200]
    return out


def peer_block(conn, uids):
    """Benchmark table: one row per peer from Business Discovery, plus the same numbers for the selected own accounts.
    Only public numbers exist for peers (followers, likes, comments, cadence), so the comparison is on engagement per follower."""
    import datetime, re
    peers = db.rows(conn, "SELECT username, label, note, followers_count, media_count, last_fetched_at, last_error FROM peers ORDER BY followers_count DESC")
    if not peers:
        return {"rows": [], "own": []}
    media = db.rows(conn, "SELECT username, media_type, product_type, permalink, caption, posted_at, like_count, comments_count FROM peer_media ORDER BY posted_at DESC")
    by = {}
    for m in media:
        by.setdefault(m["username"], []).append(m)
    def ts(x):
        try: return datetime.datetime.strptime(x[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception: return None
    def summarize(ms, followers):
        likes = [m["like_count"] for m in ms if m["like_count"] is not None]
        coms = [m["comments_count"] for m in ms if m["comments_count"] is not None]
        eng = [((m["like_count"] or 0) + (m["comments_count"] or 0)) for m in ms]
        times = sorted(t for t in (ts(m["posted_at"] or "") for m in ms) if t)
        cadence = (len(times) / max(1.0, (times[-1] - times[0]).days / 7.0)) if len(times) >= 3 and (times[-1] - times[0]).days >= 7 else None
        reels = len([m for m in ms if (m.get("product_type") or "").upper() == "REELS" or (m.get("media_type") or "").upper() == "VIDEO"])
        best = max(ms, key=lambda m: (m["like_count"] or 0) + (m["comments_count"] or 0)) if ms else None
        tags = {}
        for m in ms:
            for t in set(re.findall(r"#(\w+)", m.get("caption") or "")): tags[t.lower()] = tags.get(t.lower(), 0) + 1
        med_e = _median(eng)
        return {"posts": len(ms), "median_likes": _median(likes), "median_comments": _median(coms),
                "eng_per_1k": (None if not followers or med_e is None else round(1000.0 * med_e / followers, 2)),
                "posts_per_week": None if cadence is None else round(cadence, 1), "reel_share": (None if not ms else round(100.0 * reels / len(ms))),
                "caption_len": _median([len(m.get("caption") or "") for m in ms]),
                "top_tags": [t for t, n in sorted(tags.items(), key=lambda kv: -kv[1])[:6]],
                "best": (None if not best else {"permalink": best["permalink"], "likes": best["like_count"], "comments": best["comments_count"], "caption": (best["caption"] or "")[:120], "posted_at": best["posted_at"]})}
    rows = []
    for p in peers:
        r = {"username": p["username"], "note": p["note"] or "", "followers": p["followers_count"], "media_count": p["media_count"], "fetched": p["last_fetched_at"], "error": p["last_error"]}
        r.update(summarize(by.get(p["username"], []), p["followers_count"]))
        rows.append(r)
    own = []
    for a in db.rows(conn, f"SELECT ig_user_id, label, username FROM accounts WHERE ig_user_id IN ({_in(len(uids))})", uids):
        f = db.one(conn, f"SELECT value FROM account_daily WHERE ig_user_id = {db.PH} AND metric = 'followers_count' ORDER BY period_end DESC LIMIT 1", (a["ig_user_id"],))
        ms = db.rows(conn, f"""SELECT m.media_type, m.product_type, m.permalink, m.caption, m.posted_at, sn.like_count, sn.comments_count FROM media m
            LEFT JOIN media_snapshots sn ON sn.media_id = m.media_id AND sn.captured_at = (SELECT MAX(captured_at) FROM media_snapshots WHERE media_id = m.media_id)
            WHERE m.ig_user_id = {db.PH} AND m.deleted_at IS NULL ORDER BY m.posted_at DESC LIMIT 25""", (a["ig_user_id"],))
        fol = f["value"] if f else None
        o = {"username": a["username"], "label": a["label"], "followers": fol}
        o.update(summarize([dict(m) for m in ms], fol))
        own.append(o)
    return {"rows": rows, "own": own}


def recommendations(conn, uids, platform="instagram"):
    """Open, done and dismissed recommendations with the findings and market notes they cite. Empty lists when the advisor has not run."""
    marks = _in(len(uids))
    ask_state = _state(platform)[1]
    owners = "yt_channels a ON a.channel_id" if platform == "youtube" else "accounts a ON a.ig_user_id"
    try:
        recs = db.rows(conn, f"""SELECT r.rec_id, r.source, r.priority, r.category, r.title, r.why, r.action, r.expected_effect, r.confidence, r.status, r.finding_ids, r.note_ids,
            r.created_at, r.updated_at, r.done_at, r.dismissed_reason, r.outcome_json, a.label AS account FROM recommendations r JOIN {owners} = r.ig_user_id
            WHERE r.ig_user_id IN ({marks}) AND r.status != 'superseded' ORDER BY r.priority, r.updated_at DESC""", uids)
        finds = {r["finding_id"]: r for r in db.rows(conn, f"SELECT finding_id, title, severity, status FROM findings WHERE ig_user_id IN ({marks})", uids)}
        notes = {r["note_id"]: r for r in db.rows(conn, f"SELECT note_id, topic, summary, source_url, source_title, collected_at FROM market_notes WHERE platform IN ('any', {db.PH})", (platform,))}
        last = db.one(conn, f"SELECT MAX(last_seen_at) AS t FROM findings WHERE ig_user_id IN ({marks})", uids)["t"]
        open_findings = db.one(conn, f"SELECT COUNT(*) AS n FROM findings WHERE ig_user_id IN ({marks}) AND status = 'open'", uids)["n"]
        fresh_notes = db.one(conn, f"SELECT COUNT(*) AS n FROM market_notes WHERE platform IN ('any', {db.PH})", (platform,))["n"]
    except Exception:
        return {"ready": False, "open": [], "done": [], "dismissed": [], "findings": 0, "notes": 0, "analyzed_at": None, "ask": dict(ask_state)}
    out = {"open": [], "done": [], "dismissed": []}
    for r in recs:
        r["outcome"] = json.loads(r.pop("outcome_json") or "null")
        r["evidence"] = [{"title": finds[i]["title"], "severity": finds[i]["severity"]} for i in json.loads(r.pop("finding_ids") or "[]") if i in finds]
        r["sources"] = [{"topic": notes[i]["topic"], "summary": notes[i]["summary"], "url": notes[i]["source_url"], "title": notes[i]["source_title"]} for i in json.loads(r.pop("note_ids") or "[]") if i in notes]
        out.get(r["status"], out["open"]).append(r)
    out["done"], out["dismissed"] = out["done"][:20], out["dismissed"][:20]
    return {"ready": True, **out, "findings": open_findings, "notes": fresh_notes, "analyzed_at": last, "ask": dict(ask_state)}


def analyze_now(account="all", db_file=None, platform="instagram"):
    """Run the rules in this process (fast, offline). Returns one summary line per account."""
    import ig_reco
    if not ACCOUNT_OK.match(account or ""):
        raise ValueError("bad account name")
    _state(platform)
    conn = db.connect(db_file)
    try:
        if platform == "youtube":
            import yt_reco
            rows = [r for r in db.rows(conn, "SELECT channel_id, label FROM yt_channels ORDER BY CASE WHEN label = 'music' THEN 0 ELSE 1 END, label") if account in ("all", r["label"])]
            if not rows:
                raise ValueError("no YouTube data yet: press Collect now first")
            res = [dict(label=r["label"], **yt_reco.analyze(conn, r["channel_id"])) for r in rows]
            ig_reco.outcomes(conn)
            return res
        rows = ig_reco.account_rows(conn, account)
        if not rows:
            raise ValueError("no analytics data yet: press Collect now first")
        res = [dict(label=r["label"], **ig_reco.analyze(conn, r["ig_user_id"])) for r in rows]
        ig_reco.outcomes(conn)
        try: hashtag_block(conn, [r["ig_user_id"] for r in rows], write=True)
        except Exception: pass
        return res
    finally:
        conn.close()


def set_rec_status(rec_id, status, reason=None, db_file=None):
    import ig_reco
    if not re.match(r"^[rc]-[0-9a-f]{6,12}$", rec_id or ""):
        raise ValueError("bad recommendation id")
    conn = db.connect(db_file)
    try:
        ig_reco.set_status(conn, rec_id, status, (reason or "")[:300] or None)
    finally:
        conn.close()
    if status != "done": _rules_remove(rec_id)  # reopened or dismissed: the standing rule it created goes away


def rules_path():
    import navaan_common as C
    return os.path.join(os.path.dirname(C.songs_root()), "standing_rules.json")


def _rules_load():
    try: return json.load(open(rules_path(), encoding="utf-8"))
    except Exception: return []


def _rules_save(rules):
    json.dump(rules, open(rules_path(), "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def _rules_remove(rec_id):
    rules = _rules_load()
    keep = [r for r in rules if r.get("rec_id") != rec_id]
    if len(keep) != len(rules): _rules_save(keep)


def implement_rec(rec_id, db_file=None):
    """Put a recommendation to work from the Analytics page. Timing: the portal opens the schedule picker. Hashtags: the tag file is refreshed.
    Everything else becomes a standing rule in standing_rules.json, which the caption, YouTube text and director steps read for every new item.
    The recommendation is marked done (which also starts its before and after measurement) except timing, which is marked done once a time is scheduled."""
    import ig_reco, datetime
    if not re.match(r"^[rc]-[0-9a-f]{6,12}$", rec_id or ""):
        raise ValueError("bad recommendation id")
    conn = db.connect(db_file)
    try:
        r = db.one(conn, f"""SELECT r.rec_id, r.category, r.title, r.action, r.ig_user_id, COALESCE(a.label, y.label) AS label, CASE WHEN y.channel_id IS NULL THEN 'instagram' ELSE 'youtube' END AS platform
            FROM recommendations r LEFT JOIN accounts a ON a.ig_user_id = r.ig_user_id LEFT JOIN yt_channels y ON y.channel_id = r.ig_user_id WHERE r.rec_id = {db.PH}""", (rec_id,))
        if not r: raise ValueError("no such recommendation")
        if r["category"] == "timing": return {"kind": "schedule", "type": r["label"]}
        if r["category"] == "hashtags" and r["platform"] == "instagram":
            uids = [x["ig_user_id"] for x in db.rows(conn, "SELECT ig_user_id FROM accounts")]
            try: hashtag_block(conn, uids, write=True)
            except Exception: pass
        rules = [x for x in _rules_load() if x.get("rec_id") != rec_id]
        rules.append({"rec_id": rec_id, "account": r["label"], "platform": r["platform"], "category": r["category"], "title": r["title"], "action": r["action"],
                      "applied_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        _rules_save(rules)
        ig_reco.set_status(conn, rec_id, "done")
    finally:
        conn.close()
    msg = {"hashtags": "Done. hashtags.json is refreshed and every new caption now takes two of the peer tags.",
           "cadence": "Saved as a standing rule. Use Schedule publishing on your next songs to keep the pace."}.get(r["category"],
           "Saved as a standing rule. The caption, YouTube text and shot list steps follow it for every new item. Reopen the recommendation to remove it.")
    return {"kind": "rule", "message": msg}


def ask_prompt(account, platform="instagram"):
    scope = "all accounts" if account == "all" else f"the {account} account"
    if platform == "youtube":
        return (f"Use the growth-advice skill of the navaan-studio plugin for the YouTube channel of {scope}. Pass --platform youtube to every scripts/ig_reco.py call "
                "and --note-platform youtube when you store market notes. Do not run a new collect unless the data is more than a day old. "
                "You run headless: nobody can answer you, never ask a question, state any assumption and continue. Organic growth only. "
                "Impressions and click through rate are not available from the API, so do not guess them. "
                "Never write to YouTube, never touch meta.json approvals. Store sourced market notes and at most 6 recommendations through scripts/ig_reco.py, then give a short summary.")
    scope = "both accounts" if account == "all" else f"the {account} account"
    return (f"Use the growth-advice skill of the navaan-studio plugin for {scope}. Do not run a new collect unless the data is more than a day old. "
            "You run headless: nobody can answer you, never ask a question, state any assumption and continue. Organic growth only. "
            "Never write to Instagram, never touch meta.json approvals. Store sourced market notes and at most 6 recommendations through scripts/ig_reco.py, then give a short summary.")


def start_ask(account="all", platform="instagram"):
    """Start a headless Claude run that researches the market and writes recommendations. Returns False when one is already going on that platform."""
    import shlex
    if not ACCOUNT_OK.match(account or ""):
        raise ValueError("bad account name")
    ask = _state(platform)[1]
    if ask["running"]:
        return False
    base = shlex.split(os.environ.get("NAVAAN_CLAUDE_CMD", "claude -p"))
    flags = shlex.split(os.environ["NAVAAN_CLAUDE_FLAGS"]) if "NAVAAN_CLAUDE_FLAGS" in os.environ else ["--permission-mode", "acceptEdits", "--allowedTools", ",".join(ASK_TOOLS)]
    cmd = base + [ask_prompt(account, platform)] + flags
    ask.update(running=True, account=account, rc=None, tail="", started=int(time.time()), finished=0)

    def work():
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, cwd=os.environ.get("NAVAAN_ROOT") or os.getcwd())
            ask.update(rc=p.returncode, tail=((p.stdout or "") + (p.stderr or "")).strip()[-1800:])
        except FileNotFoundError:
            ask.update(rc=127, tail="The claude command was not found. Install Claude Code, or set NAVAAN_CLAUDE_CMD.")
        except Exception as e:
            ask.update(rc=2, tail=str(e)[:500])
        ask.update(running=False, finished=int(time.time()))
    threading.Thread(target=work, daemon=True).start()
    return True


def start_collect(account="all", platform="instagram"):
    """Start ig_collect.py or yt_collect.py collect in the background. Returns False when a run is already going on that platform."""
    if not ACCOUNT_OK.match(account or ""):
        raise ValueError("bad account name")
    st = _state(platform)[0]
    if st["running"]:
        return False
    script = "yt_collect.py" if platform == "youtube" else "ig_collect.py"
    st.update(running=True, account=account, rc=None, tail="", started=int(time.time()), finished=0)

    def work():
        try:
            p = subprocess.run([sys.executable, os.path.join(HERE, script), "collect", "--account", account],
                               capture_output=True, text=True, timeout=1800, cwd=os.environ.get("NAVAAN_ROOT") or os.getcwd())
            st.update(rc=p.returncode, tail=((p.stdout or "") + (p.stderr or "")).strip()[-1500:])
        except Exception as e:
            st.update(rc=2, tail=str(e)[:500])
        st.update(running=False, finished=int(time.time()))
    threading.Thread(target=work, daemon=True).start()
    return True
