#!/usr/bin/env python3
"""ig_reco.py  recommendation engine for NAVAAN Instagram growth.

Hybrid by design:
  1. Rules read the analytics database and write FINDINGS: facts with evidence ("saves per reach is low on Hindi Reels", "posts go out
     3 hours before your followers are online"). Deterministic, offline, checkable. Each finding also gets a plain rule based
     recommendation, so the portal always has advice.
  2. Claude (growth-advisor agent) reads the evidence pack, researches current trends on the web, stores sourced market notes and writes
     better recommendations. Every Claude recommendation must cite a stored finding or market note, or it is rejected.
  3. You mark recommendations Done or Dismissed. Done ones store a baseline; later runs compare it with posts made afterwards.

  analyze  [--account all]                    run the rules, store findings, refresh rule based recommendations
  pack     [--account all] [--out FILE]       JSON evidence pack for the advisor (findings, top and bottom posts, market data, history)
  note     --topic T --summary S --url U      store one sourced market note (web research result)
  add      --file FILE|-                      store recommendations written by Claude (JSON list), validated
  list     [--status open|done|dismissed|all] show recommendations
  status   REC_ID open|done|dismissed [--reason TEXT]
  outcomes                                    compare done recommendations with posts made after them

Read only towards Instagram. Nothing here posts, comments, likes or boosts. Thresholds are rules of thumb and are tuned in navaan.config.json under
analytics.thresholds. Where a rule has no honest industry benchmark it compares you with your own history instead.
"""
import os, sys, json, re, hashlib, argparse, datetime, statistics, uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analytics_db as db
import navaan_log as L
LOG = L.get("ig_reco")

UTC = datetime.timezone.utc
CATEGORIES = ("data", "hook", "content", "timing", "cadence", "hashtags", "caption", "engagement", "audience", "format", "market", "growth", "retention", "packaging")
SEVERITY_PRIORITY = {"high": 1, "medium": 2, "low": 3, "info": 3}
THRESHOLDS = {
    "target_posts_per_week": 2,
    "stale_days": 3,
    "gap_medium_days": 7,
    "gap_high_days": 14,
    "min_measured": 4,
    "underperform_ratio": 0.5,
    "weak_watch_ratio": 0.7,
    "passive_mix": 0.15,        # (saves + shares) / likes below this means people like but do not keep or send
    "low_conversation": 0.02,   # comments / likes
    "reach_per_follower": 0.3,
    "timing_hours_off": 3,
    "decline_views": 0.30,
    "decline_engagement": 0.25,
    "language_gap": 1.5,
    "peer_engagement_ratio": 0.6,
}


def parse_ts(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) if s else None
    except ValueError as _e:
        L.ignored(LOG, "parse_ts: ValueError (optional or expected)", _e)
        return None


def med(xs):
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def tags_in(text):
    return re.findall(r"#(\w+)", (text or "").lower())


def hdist(a, b):
    d = abs(a - b) % 24
    return min(d, 24 - d)


def fid(*parts):
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:12]


def settings():
    t = dict(THRESHOLDS)
    tz = "UTC"
    try:
        from navaan_common import cfg
        t.update({k: v for k, v in (cfg("analytics.thresholds", {}) or {}).items() if k in t})
        if cfg("analytics.target_posts_per_week"):
            t["target_posts_per_week"] = cfg("analytics.target_posts_per_week")
        tz = cfg("analytics.timezone", "UTC") or "UTC"
    except SystemExit as _e:
        L.ignored(LOG, "settings: SystemExit (optional or expected)", _e)
        pass
    return t, tz


# ---------------------------------------------------------------- data

def account_rows(conn, account):
    rows = db.rows(conn, "SELECT ig_user_id, label, username FROM accounts ORDER BY CASE WHEN label = 'music' THEN 0 ELSE 1 END, label")
    return [r for r in rows if account in ("all", r["label"])]


def load(conn, uid, now):
    D = {"uid": uid, "now": now}
    D["account"] = db.one(conn, f"SELECT * FROM accounts WHERE ig_user_id = {db.PH}", (uid,))
    posts = db.rows(conn, f"""SELECT m.media_id, m.slug, m.permalink, m.caption, m.posted_at, m.product_type, s.title, s.language, s.genre,
        sn.like_count, sn.comments_count, sn.reach, sn.views, sn.saved, sn.shares, sn.total_interactions, sn.avg_watch_time_ms, sn.skip_rate
        FROM media m LEFT JOIN songs s ON s.slug = m.slug
        LEFT JOIN media_snapshots sn ON sn.media_id = m.media_id AND sn.captured_at = (SELECT MAX(captured_at) FROM media_snapshots WHERE media_id = m.media_id)
        WHERE m.ig_user_id = {db.PH} AND m.deleted_at IS NULL ORDER BY m.posted_at DESC""", (uid,))
    for p in posts:
        dt = parse_ts(p["posted_at"])
        p["age"] = (now - dt).total_seconds() / 86400 if dt else None
        p["hour"] = dt.hour if dt else None
        p["weekday"] = dt.strftime("%A") if dt else None
        p["save_rate"] = (p["saved"] / p["reach"]) if p["saved"] is not None and p["reach"] else None
        p["share_rate"] = (p["shares"] / p["reach"]) if p["shares"] is not None and p["reach"] else None
        p["avg_watch_s"] = p["avg_watch_time_ms"] / 1000.0 if p["avg_watch_time_ms"] is not None else None
        p["hashtags"] = len(tags_in(p["caption"]))
        p["caption_len"] = len(p["caption"] or "")
        p["name"] = p["title"] or (p["caption"] or "").strip()[:40] or p["media_id"]
    D["posts"] = posts
    D["measured"] = [p for p in posts if p["views"] is not None]
    series = lambda m: db.rows(conn, f"SELECT period_end AS d, SUM(value) AS v FROM account_daily WHERE ig_user_id = {db.PH} AND metric = {db.PH} GROUP BY period_end ORDER BY period_end", (uid, m))
    D["followers"], D["views"], D["interactions"] = series("followers_count"), series("views"), series("total_interactions")
    D["hours"] = {r["hour"]: r["followers"] for r in db.rows(conn, f"""SELECT hour, followers FROM online_hours WHERE ig_user_id = {db.PH}
        AND captured_on = (SELECT MAX(captured_on) FROM online_hours WHERE ig_user_id = {db.PH})""", (uid, uid))}
    aud = {}
    for r in db.rows(conn, f"""SELECT breakdown, bucket, value FROM audience a WHERE ig_user_id = {db.PH}
        AND captured_on = (SELECT MAX(captured_on) FROM audience b WHERE b.ig_user_id = a.ig_user_id AND b.breakdown = a.breakdown) ORDER BY value DESC""", (uid,)):
        aud.setdefault(r["breakdown"], []).append((r["bucket"], r["value"]))
    D["audience"] = aud
    D["waiting"] = db.rows(conn, f"""SELECT c.comment_id, c.posted_at FROM comments c JOIN media m ON m.media_id = c.media_id
        WHERE m.ig_user_id = {db.PH} AND c.parent_id IS NULL AND c.is_own = 0 AND c.hidden = 0
        AND NOT EXISTS (SELECT 1 FROM comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1) ORDER BY c.posted_at""", (uid,))
    D["last_ok"] = db.one(conn, f"SELECT finished_at FROM collector_runs WHERE ig_user_id = {db.PH} AND status IN ('ok','partial') ORDER BY finished_at DESC LIMIT 1", (uid,))
    D["peers"] = db.rows(conn, "SELECT username, followers_count FROM peers WHERE last_fetched_at IS NOT NULL")
    D["peer_media"] = db.rows(conn, "SELECT username, caption, posted_at, like_count, comments_count FROM peer_media")
    D["tag_media"] = db.rows(conn, "SELECT hashtag, caption, like_count, comments_count FROM hashtag_media WHERE kind = 'top_media'")
    D["notes"] = db.rows(conn, f"SELECT note_id, topic, summary, source_url, source_title, region, language, confidence, collected_at FROM market_notes WHERE (expires_at IS NULL OR expires_at >= {db.PH}) AND platform IN ('any', 'instagram') ORDER BY collected_at DESC", (now.strftime("%Y-%m-%dT%H:%M:%SZ"),))
    return D


def latest_followers(D):
    return D["followers"][-1]["v"] if D["followers"] else None


def f(rule, subject, category, severity, title, detail, evidence):
    return {"rule_id": rule, "subject": subject, "category": category, "severity": severity, "title": title, "detail": detail, "evidence": evidence}


def brief_post(p):
    return {"media_id": p["media_id"], "name": p["name"], "slug": p["slug"], "posted_at": p["posted_at"], "language": p["language"], "genre": p["genre"],
            "views": p["views"], "reach": p["reach"], "saved": p["saved"], "shares": p["shares"], "likes": p["like_count"], "comments": p["comments_count"],
            "avg_watch_s": None if p["avg_watch_s"] is None else round(p["avg_watch_s"], 1), "save_rate_pct": None if p["save_rate"] is None else round(100 * p["save_rate"], 2)}


# ---------------------------------------------------------------- rules (each returns a list of findings)

def r_data_health(D, T):
    out = []
    last = parse_ts((D["last_ok"] or {}).get("finished_at"))
    age = (D["now"] - last).total_seconds() / 86400 if last else None
    if age is None or age > T["stale_days"]:
        out.append(f("data_stale", "account", "data", "high", "Analytics data is stale" if last else "No successful collect yet",
                     "Every other recommendation depends on fresh numbers.", {"last_success": (D["last_ok"] or {}).get("finished_at"), "days_old": None if age is None else round(age, 1)}))
    if len(D["measured"]) < T["min_measured"] + 1:
        out.append(f("data_thin", "account", "data", "info", f"Only {len(D['measured'])} posts have numbers",
                     "Patterns need several posts. Treat advice as directional.", {"measured_posts": len(D["measured"]), "needed": T["min_measured"] + 1}))
    return out


def r_cadence(D, T):
    posts = [p for p in D["posts"] if p["age"] is not None]
    if not posts:
        return []
    out, gap = [], min(p["age"] for p in posts)
    if gap > T["gap_medium_days"]:
        out.append(f("posting_gap", "account", "cadence", "high" if gap > T["gap_high_days"] else "medium", f"No post for {int(gap)} days",
                     "Reach and follower growth fade when posting stops.", {"days_since_last_post": round(gap, 1), "last_post": min(posts, key=lambda p: p["age"])["posted_at"]}))
    n28 = len([p for p in posts if p["age"] <= 28])
    ppw = n28 / 4.0
    if gap <= T["gap_medium_days"] and ppw < 0.5 * T["target_posts_per_week"]:
        out.append(f("cadence_low", "account", "cadence", "medium", f"About {ppw:.1f} posts per week against a target of {T['target_posts_per_week']}",
                     "Steady posting gives each release a chance to build on the last.", {"posts_last_28_days": n28, "posts_per_week": round(ppw, 2), "target": T["target_posts_per_week"]}))
    return out


def window_sum(series, now, start_back, end_back):
    lo, hi = (now - datetime.timedelta(days=start_back)).strftime("%Y-%m-%d"), (now - datetime.timedelta(days=end_back)).strftime("%Y-%m-%d")
    xs = [r["v"] for r in series if lo <= r["d"] < hi]
    return (sum(xs), len(xs)) if xs else (None, 0)


def r_trend(D, T):
    out, now = [], D["now"]
    fol = [r for r in D["followers"] if r["d"] >= (now - datetime.timedelta(days=14)).strftime("%Y-%m-%d")]
    recent_posts = len([p for p in D["posts"] if p["age"] is not None and p["age"] <= 14])
    if len(fol) >= 8 and fol[-1]["v"] - fol[0]["v"] <= 0:
        delta = fol[-1]["v"] - fol[0]["v"]
        out.append(f("follower_stall", "account", "growth", "medium" if recent_posts else "high", "Followers have not grown in 14 days" if delta == 0 else f"Followers fell by {abs(int(delta))} in 14 days",
                     "Views are not turning into follows.", {"followers_start": fol[0]["v"], "followers_now": fol[-1]["v"], "posts_in_period": recent_posts}))
    v_now, n1 = window_sum(D["views"], now, 7, -1)
    v_prev, n2 = window_sum(D["views"], now, 14, 7)
    if n1 >= 5 and n2 >= 5 and v_prev and v_now < v_prev * (1 - T["decline_views"]):
        out.append(f("views_decline", "account", "content", "medium", f"Views fell {round(100 * (1 - v_now / v_prev))}% week on week", "Last 7 days against the 7 before.",
                     {"views_last_7d": v_now, "views_prev_7d": v_prev}))
    i_now, _ = window_sum(D["interactions"], now, 7, -1)
    i_prev, _ = window_sum(D["interactions"], now, 14, 7)
    if v_now and v_prev and i_now is not None and i_prev:
        r_now, r_prev = i_now / v_now, i_prev / v_prev
        if r_prev > 0 and r_now < r_prev * (1 - T["decline_engagement"]):
            out.append(f("engagement_decline", "account", "engagement", "medium", "Fewer people interact per view than last week", "Interactions per view dropped.",
                         {"interactions_per_view_now": round(r_now, 4), "interactions_per_view_prev": round(r_prev, 4)}))
    return out


def r_posts(D, T):
    out, M = [], [p for p in D["measured"] if p["age"] is not None and p["age"] >= 3]
    if len(M) < T["min_measured"]:
        return out
    mv, mw = med([p["views"] for p in M]), med([p["avg_watch_s"] for p in M])
    for p in M:
        if mv and p["views"] < T["underperform_ratio"] * mv:
            out.append(f("underperformer", p["media_id"], "content", "medium", f"\"{p['name']}\" reached under half of your usual views",
                         f"{p['views']} views against a median of {int(mv)}.", {"post": brief_post(p), "median_views": mv, "ratio": round(p["views"] / mv, 2)}))
        if mw and p["avg_watch_s"] is not None and p["avg_watch_s"] < T["weak_watch_ratio"] * mw and mv and p["views"] < mv:
            out.append(f("weak_hook", p["media_id"], "hook", "medium", f"\"{p['name']}\" lost viewers early",
                         f"Average watch {p['avg_watch_s']:.1f}s against a median of {mw:.1f}s, with below median views.",
                         {"post": brief_post(p), "median_avg_watch_s": round(mw, 1), "skip_rate": p["skip_rate"]}))
    best = max(M, key=lambda p: p["views"])
    f_now = latest_followers(D)
    out.append(f("best_post_pattern", best["media_id"], "content", "info", f"Your best recent post: \"{best['name']}\"", "What it had that the others did not is worth repeating.",
                 {"post": brief_post(best), "hour_utc": best["hour"], "weekday": best["weekday"], "hashtags": best["hashtags"], "caption_len": best["caption_len"],
                  "reach_per_follower": round(best["reach"] / f_now, 2) if best["reach"] and f_now else None}))
    return out


def r_mix(D, T):
    out, M = [], [p for p in D["measured"] if p["age"] is not None and p["age"] >= 3][:5]
    if len(M) < 3:
        return out
    likes = sum(p["like_count"] or 0 for p in M)
    keep = sum((p["saved"] or 0) + (p["shares"] or 0) for p in M)
    com = sum(p["comments_count"] or 0 for p in M)
    if likes >= 20 and keep / likes < T["passive_mix"]:
        out.append(f("passive_likes", "account", "engagement", "medium", "People like your Reels but rarely save or share them", "Saves and shares tell Instagram a Reel is worth showing to new people.",
                     {"likes": likes, "saves_plus_shares": keep, "ratio": round(keep / likes, 3), "posts": len(M), "basis": "rule_of_thumb"}))
    if likes >= 20 and com / likes < T["low_conversation"]:
        out.append(f("low_conversation", "account", "engagement", "low", "Very few comments compared with likes", "Comments signal a Reel started a conversation.",
                     {"likes": likes, "comments": com, "ratio": round(com / likes, 4), "basis": "rule_of_thumb"}))
    f_now = latest_followers(D)
    reels = [p for p in M if p["reach"]]
    if f_now and len(reels) >= 3 and med([p["reach"] for p in reels]) / f_now < T["reach_per_follower"]:
        out.append(f("low_distribution", "account", "growth", "medium", "Reels mostly reach your existing followers or fewer", "Growth needs reach beyond followers.",
                     {"median_reach": med([p["reach"] for p in reels]), "followers": f_now, "reach_per_follower": round(med([p["reach"] for p in reels]) / f_now, 2), "basis": "rule_of_thumb"}))
    return out


def tz_label(hours_utc, tzs, now):
    from datetime import timedelta
    parts = []
    for h in hours_utc:
        base = now.replace(hour=h, minute=0, second=0, microsecond=0)
        local = []
        for tz in tzs:
            try:
                from zoneinfo import ZoneInfo
                local.append(f"{base.astimezone(ZoneInfo(tz)):%H:%M} {tz.split('/')[-1]}")
            except Exception as _e:
                L.soft(LOG, "tz_label_error")
                pass
        parts.append(f"{h:02d}:00 UTC" + (f" ({', '.join(local)})" if local else ""))
    return parts


def r_timing(D, T, tz="UTC"):
    if len(D["hours"]) < 12:
        return []
    top = [h for h, _ in sorted(D["hours"].items(), key=lambda kv: -(kv[1] or 0))[:3]]
    recent = [p for p in D["posts"] if p["hour"] is not None][:5]
    if len(recent) < 3:
        return []
    off = [p for p in recent if min(hdist(p["hour"], h) for h in top) > T["timing_hours_off"]]
    if len(off) < 3:
        return []
    tzs = [tz] + (["Asia/Kolkata"] if (D["audience"].get("country") or [("", 0)])[0][0] == "IN" and tz != "Asia/Kolkata" else [])
    return [f("timing_mismatch", "account", "timing", "medium", f"{len(off)} of your last {len(recent)} posts went out when few followers were online",
              "Reels get most of their first push in the first hours.", {"peak_hours_utc": sorted(top), "peak_hours_local": tz_label(sorted(top), tzs, D["now"]), "post_hours_utc": [p["hour"] for p in recent], "window": "last 30 days of online follower data"})]


def r_groups(D, T):
    out = []
    for key, rule in (("language", "language_gap"), ("genre", "genre_gap")):
        groups = {}
        for p in D["measured"]:
            if p[key]:
                groups.setdefault(p[key], []).append(p["views"])
        big = {k: v for k, v in groups.items() if len(v) >= 2}
        if len(big) >= 2:
            avg = {k: sum(v) / len(v) for k, v in big.items()}
            hi, lo = max(avg, key=avg.get), min(avg, key=avg.get)
            if avg[lo] and avg[hi] / avg[lo] >= T["language_gap"]:
                out.append(f(rule, key, "content", "low", f"{hi} posts get {avg[hi] / avg[lo]:.1f}x the views of {lo} posts", f"Compared by {key}, average views.",
                             {"groups": {k: {"posts": len(big[k]), "avg_views": round(avg[k])} for k in big}, "better": hi, "weaker": lo}))
    return out


def r_comments(D, T):
    if not D["waiting"]:
        return []
    oldest = parse_ts(D["waiting"][0]["posted_at"])
    hours = (D["now"] - oldest).total_seconds() / 3600 if oldest else 0
    if hours < 24:
        return []
    return [f("comments_unanswered", "account", "engagement", "medium", f"{len(D['waiting'])} comments are waiting for a reply", "Early replies keep a conversation going and tell followers you are there.",
              {"waiting": len(D["waiting"]), "oldest_hours": round(hours)})]


def r_caption(D, T):
    M = D["measured"]
    if len(M) < 6:
        return []
    s = sorted(M, key=lambda p: -p["views"])
    k = max(2, len(s) // 3)
    top, bot = s[:k], s[-k:]
    dh = mean([p["hashtags"] for p in top]) - mean([p["hashtags"] for p in bot])
    if abs(dh) >= 2 or (mean([p["hashtags"] for p in bot]) == 0 and mean([p["hashtags"] for p in top]) >= 1):
        return [f("caption_traits", "caption", "caption", "low", "Your best and weakest posts differ in hashtag use", "Small sample, so test it before trusting it.",
                  {"top_avg_hashtags": round(mean([p["hashtags"] for p in top]), 1), "bottom_avg_hashtags": round(mean([p["hashtags"] for p in bot]), 1),
                   "top_avg_caption_len": round(mean([p["caption_len"] for p in top])), "bottom_avg_caption_len": round(mean([p["caption_len"] for p in bot])), "posts_each_group": k})]
    return []


def r_audience(D, T):
    c = D["audience"].get("country") or []
    total = sum(v or 0 for _, v in c)
    if total and len(c) >= 2 and c[1][1] / total >= 0.25:
        return [f("audience_split", "account", "audience", "info", f"Your audience splits between {c[0][0]} and {c[1][0]}", "Two regions mean two good posting windows.",
                  {"countries": [(b, v, round(100 * v / total)) for b, v in c[:4]]})]
    return []


def r_market(D, T):
    out = []
    f_now = latest_followers(D)
    peers = {p["username"]: p["followers_count"] for p in D["peers"] if p["followers_count"]}
    by = {}
    for m in D["peer_media"]:
        if m["username"] in peers:
            by.setdefault(m["username"], []).append(m)
    if len(by) >= 3 and f_now:
        peer_rates = [mean([(m["like_count"] or 0) + (m["comments_count"] or 0) for m in ms]) / peers[u] for u, ms in by.items() if ms]
        mine = [p for p in D["measured"][:10]]
        if mine:
            own = mean([(p["like_count"] or 0) + (p["comments_count"] or 0) for p in mine]) / f_now
            pm = med(peer_rates)
            if pm and own < T["peer_engagement_ratio"] * pm:
                out.append(f("peer_engagement_gap", "peers", "market", "medium", "Peers get more likes and comments per follower", f"Your rate is {own * 100:.1f}% against a peer median of {pm * 100:.1f}%.",
                             {"own_rate": round(own, 4), "peer_median_rate": round(pm, 4), "peers": len(by)}))
        spans = []
        for u, ms in by.items():
            ts = sorted(t for t in (parse_ts(m["posted_at"]) for m in ms) if t)
            if len(ts) >= 4 and (ts[-1] - ts[0]).days >= 14:
                spans.append(len(ts) / ((ts[-1] - ts[0]).days / 7.0))
        n28 = len([p for p in D["posts"] if p["age"] is not None and p["age"] <= 28]) / 4.0
        if len(spans) >= 3 and med(spans) and n28 < 0.5 * med(spans):
            out.append(f("peer_cadence_gap", "peers", "cadence", "low", "Peers post more often than you", f"Peer median {med(spans):.1f} posts per week against your {n28:.1f}.",
                         {"peer_median_posts_per_week": round(med(spans), 1), "own_posts_per_week": round(n28, 1)}))
    if not D["tag_media"] and len(by) >= 2:
        mine = {t for p in D["posts"] for t in tags_in(p["caption"])}
        stop = {"fyp", "foryou", "foryoupage", "reels", "reel", "viral", "trending", "explore", "explorepage", "instagood", "instagram", "love", "follow", "like"}
        counts = {}
        for u, ms in by.items():
            ms = sorted(ms, key=lambda m: -((m["like_count"] or 0) + (m["comments_count"] or 0)))
            un = re.sub(r"[^a-z0-9]", "", u.lower())
            for t in {t for m in ms[:max(3, int(len(ms) * 0.4))] for t in tags_in(m["caption"])} - stop - mine:
                if len(t) < 3 or t in un or un in t or t.isdigit(): continue
                counts.setdefault(t, set()).add(u)
        cand = [t for t, us in sorted(counts.items(), key=lambda kv: -len(kv[1])) if len(us) >= 2][:8] or [t for t, us in sorted(counts.items(), key=lambda kv: -len(kv[1]))][:5]
        if cand:
            out.append(f("hashtag_peers", "hashtags", "hashtags", "info", "Tags your peers use on their strongest posts", "From the top 40 percent of each peer's posts by likes and comments. Test, do not copy blindly.",
                         {"tags": cand, "peers": len(by), "by_tag": {t: sorted(counts[t]) for t in cand}}))
    if D["tag_media"]:
        mine = {t for p in D["posts"] for t in tags_in(p["caption"])}
        counts = {}
        for m in D["tag_media"]:
            for t in set(tags_in(m["caption"])):
                counts[t] = counts.get(t, 0) + 1
        missing = [t for t, n in sorted(counts.items(), key=lambda kv: -kv[1]) if t not in mine and n >= 2][:8]
        if missing:
            out.append(f("hashtag_overlap", "hashtags", "hashtags", "info", "Tags that appear in top posts in your niche but not in yours", "Candidates to test, not a guarantee.", {"tags": missing, "from_posts": len(D["tag_media"])}))
    return out


RULES = (r_data_health, r_cadence, r_trend, r_posts, r_mix, r_groups, r_comments, r_caption, r_audience, r_market)


def run_rules(D, T, tz):
    out = []
    for r in RULES:
        out.extend(r(D, T))
    out.extend(r_timing(D, T, tz))
    return out


# ---------------------------------------------------------------- rule based advice (fallback when Claude has not written better)

def advice(fd):
    e, r = fd["evidence"], fd["rule_id"]
    A = {
        "data_stale": ("Refresh the analytics data", "Run /navaan-studio:collect or press Collect now. If it stops with an auth error, refresh the long-lived Instagram token.", "Fresh numbers, so every other finding is trustworthy.", "high"),
        "data_thin": ("Keep posting before drawing conclusions", "Publish steadily for the next few weeks and re-run the analysis once at least 5 posts have numbers.", "Clearer patterns and fewer false alarms.", "high"),
        "posting_gap": ("Publish the next ready item this week", "Post the next finished song, a Reel cut from the best part of a released song, or an inspiration Reel. Do not wait for a perfect one.", "Posting again restarts distribution to your followers.", "medium"),
        "cadence_low": ("Raise posting frequency toward your target", f"Plan {e.get('target', 2)} posts per week, mixing full releases with short Reels cut from released songs and inspiration clips.", "More chances per week for a Reel to travel beyond followers.", "medium"),
        "follower_stall": ("Give viewers a reason to follow", "End each Reel with a one line reason to follow (what comes next, a release day), and say it in the caption. Check that the profile bio names the languages and genres you make.", "A higher share of viewers who follow.", "low"),
        "views_decline": ("Find what changed in the last two weeks", "Compare the last two Reels with your best one: opening seconds, length, language, post time. Repeat what the best one did.", "Views return toward your earlier level.", "low"),
        "engagement_decline": ("Add one clear reason to react", "Ask a specific question about a lyric or ask which language people want next, and reply to every early comment.", "More comments and shares per view.", "low"),
        "underperformer": ("Learn from a weak post, then re-cut it", f"Compare \"{(e.get('post') or {}).get('name', 'this post')}\" with your best post on opening seconds, length and posting time. Re-cut the best 20 to 30 seconds with the hook first.", "A better hook usually lifts both watch time and reach.", "low"),
        "weak_hook": ("Fix the first three seconds", "Start on the strongest lyric or visual moment instead of an intro. Put the hook line on screen in the first second. Test on the next Reel.", "Longer average watch time and fewer early swipes.", "medium"),
        "best_post_pattern": ("Make the next post resemble your best one", f"Match the best post's posting hour ({e.get('hour_utc')} UTC), language and caption style, and change one thing at a time.", "Repeats what already worked, with a clean comparison.", "medium"),
        "passive_likes": ("Make Reels worth saving or sending", "Pick the most quotable lyric, show it on screen, and say in the caption who this song is for (\"send this to the person who...\"). Saves and shares move distribution more than likes.", "More saves and shares per reach.", "medium"),
        "low_conversation": ("Invite a reply", "End the caption with one concrete question about the lyric, and reply to the first comments within the first hour.", "More comments, which keeps the Reel in circulation longer.", "low"),
        "low_distribution": ("Work on discoverability, not only followers", "Use a searchable first line and keywords for language and mood in the caption, post at your followers' peak hours, and check the opening seconds.", "More reach from people who do not follow you yet.", "low"),
        "timing_mismatch": ("Post when your followers are online", f"Post 1 to 2 hours before the peak: {', '.join(e.get('peak_hours_local') or [])}. Keep the same slot for 3 posts to compare fairly.", "A stronger first-hour response, which helps distribution.", "medium"),
        "language_gap": ("Lean into the language that travels", f"{e.get('better')} outperforms {e.get('weaker')}. Release more in {e.get('better')}, and use Reels in it to bring people to the other language.", "Higher average views while you keep both audiences.", "low"),
        "genre_gap": ("Lean into the genre that travels", f"{e.get('better')} outperforms {e.get('weaker')}. Plan the next release in {e.get('better')} and compare.", "Higher average views per release.", "low"),
        "comments_unanswered": ("Reply to waiting comments", f"Answer the {e.get('waiting')} waiting comments, oldest first, in the commenter's language.", "Stronger follower relationship and more repeat engagement.", "medium"),
        "caption_traits": ("Test hashtag use on the next two posts", f"Your best posts average {e.get('top_avg_hashtags')} hashtags and the weakest {e.get('bottom_avg_hashtags')}. Try the pattern of the best posts for two posts and compare.", "A clean test of one variable.", "low"),
        "audience_split": ("Plan two posting windows", "Pick one slot for each main audience region and alternate, then compare first-hour response.", "Better timing for both audiences.", "low"),
        "peer_engagement_gap": ("Study what peers do differently", "Open three peer posts with the highest engagement and note hook, length and caption. Borrow the structure, not the content.", "Closing part of the engagement gap.", "low"),
        "peer_cadence_gap": ("Match peer posting rhythm", "Move toward the peer median cadence using short Reels from released songs.", "More touchpoints per week.", "low"),
        "hashtag_peers": ("Test peer tags on the next two posts", f"Add two of {', '.join('#' + t for t in (e.get('tags') or [])[:5])} to the next two captions, keep five tags in total, and compare reach after a week. The caption skills read hashtags.json and do this on their own for new posts.", "A fair test of whether niche tags bring reach from outside your followers.", "low"),
        "hashtag_overlap": ("Test niche tags seen in top posts", f"Try {', '.join('#' + t for t in (e.get('tags') or [])[:4])} on the next two posts and compare reach.", "A test, not a guarantee.", "low"),
    }
    t = A.get(r)
    if not t:
        return None
    title, action, effect, conf = t
    return {"title": title, "why": fd["detail"] or fd["title"], "action": action, "expected_effect": effect, "confidence": conf}


# ---------------------------------------------------------------- store

def analyze(conn, uid, now=None):
    now = now or db.utcnow()
    nowdt = parse_ts(now)
    T, tz = settings()
    D = load(conn, uid, nowdt)
    return analyze_with(conn, uid, run_rules(D, T, tz), advice, now)


def analyze_with(conn, uid, found, adviser, now):
    """Store findings (dicts from f()), resolve the ones that vanished, and write rule based recommendations. Shared by Instagram and YouTube."""
    ids = set()
    for fd in found:
        i = fid(uid, fd["rule_id"], fd["subject"])
        ids.add(i)
        db.upsert(conn, "findings", {"finding_id": i, "ig_user_id": uid, "rule_id": fd["rule_id"], "subject": fd["subject"], "category": fd["category"], "severity": fd["severity"],
                                     "title": fd["title"], "detail": fd["detail"], "evidence_json": json.dumps(fd["evidence"], ensure_ascii=False, default=str),
                                     "first_seen_at": now, "last_seen_at": now, "status": "open", "resolved_at": None}, ("finding_id",), keep=("first_seen_at",))
        fd["finding_id"] = i
    for r in db.rows(conn, f"SELECT finding_id FROM findings WHERE ig_user_id = {db.PH} AND status = 'open'", (uid,)):
        if r["finding_id"] not in ids:
            conn.execute(f"UPDATE findings SET status = 'resolved', resolved_at = {db.PH} WHERE finding_id = {db.PH}", (now, r["finding_id"]))
    made = 0
    for fd in found:
        a = adviser(fd)
        if not a:
            continue
        rid = "r-" + fid(fd["finding_id"])[:10]
        existing = db.one(conn, f"SELECT status FROM recommendations WHERE rec_id = {db.PH}", (rid,))
        claude_cites = [x for x in db.rows(conn, f"SELECT finding_ids FROM recommendations WHERE ig_user_id = {db.PH} AND source = 'claude' AND status = 'open'", (uid,))
                        if fd["finding_id"] in json.loads(x["finding_ids"] or "[]")]
        if existing and existing["status"] in ("done", "dismissed", "superseded"):
            continue
        if claude_cites:
            if existing:
                conn.execute(f"UPDATE recommendations SET status = 'superseded', updated_at = {db.PH} WHERE rec_id = {db.PH}", (now, rid))
            continue
        row = {"rec_id": rid, "ig_user_id": uid, "source": "rule", "rule_id": fd["rule_id"], "finding_ids": json.dumps([fd["finding_id"]]), "note_ids": "[]",
               "priority": SEVERITY_PRIORITY[fd["severity"]], "category": fd["category"], "title": a["title"], "why": a["why"], "action": a["action"],
               "expected_effect": a["expected_effect"], "confidence": a["confidence"], "status": "open", "created_at": now, "updated_at": now}
        db.upsert(conn, "recommendations", row, ("rec_id",), keep=("created_at", "status"))
        made += 1
    conn.commit()
    return {"findings": len(found), "open_recommendations": made, "by_severity": {s: len([x for x in found if x["severity"] == s]) for s in ("high", "medium", "low", "info")}}


def is_youtube(conn, uid):
    return bool(db.one(conn, f"SELECT 1 AS ok FROM yt_channels WHERE channel_id = {db.PH}", (uid,)))


def metrics_snapshot(conn, uid, now, since=None):
    if is_youtube(conn, uid):
        import yt_reco
        return yt_reco.metrics_snapshot(conn, uid, now, since)
    D = load(conn, uid, now)
    M = [p for p in D["measured"] if p["age"] is not None and p["age"] >= 3]
    if since:
        M = [p for p in M if p["posted_at"] and p["posted_at"] >= since]
    else:
        M = M[:5]
    return {"posts": len(M), "median_views": med([p["views"] for p in M]), "median_save_rate_pct": None if med([p["save_rate"] for p in M]) is None else round(100 * med([p["save_rate"] for p in M]), 2),
            "median_avg_watch_s": None if med([p["avg_watch_s"] for p in M]) is None else round(med([p["avg_watch_s"] for p in M]), 1), "followers": latest_followers(D)}


def set_status(conn, rec_id, status, reason=None, now=None):
    if status not in ("open", "done", "dismissed"):
        raise ValueError("status must be open, done or dismissed")
    now = now or db.utcnow()
    r = db.one(conn, f"SELECT * FROM recommendations WHERE rec_id = {db.PH}", (rec_id,))
    if not r:
        raise ValueError("no such recommendation")
    if status == "done":
        base = metrics_snapshot(conn, r["ig_user_id"], parse_ts(now))
        conn.execute(f"UPDATE recommendations SET status = 'done', done_at = {db.PH}, updated_at = {db.PH}, baseline_json = {db.PH}, outcome_json = NULL, dismissed_reason = NULL WHERE rec_id = {db.PH}",
                     (now, now, json.dumps(base), rec_id))
    elif status == "dismissed":
        conn.execute(f"UPDATE recommendations SET status = 'dismissed', updated_at = {db.PH}, dismissed_reason = {db.PH} WHERE rec_id = {db.PH}", (now, (reason or "")[:300], rec_id))
    else:
        conn.execute(f"UPDATE recommendations SET status = 'open', updated_at = {db.PH}, done_at = NULL, dismissed_reason = NULL WHERE rec_id = {db.PH}", (now, rec_id))
    conn.commit()


def pct(a, b):
    return None if a is None or not b else round(100.0 * (a - b) / b, 1)


def outcomes(conn, now=None):
    now = now or db.utcnow()
    n = 0
    for r in db.rows(conn, "SELECT rec_id, ig_user_id, done_at, baseline_json FROM recommendations WHERE status = 'done' AND done_at IS NOT NULL"):
        base = json.loads(r["baseline_json"] or "{}")
        after = metrics_snapshot(conn, r["ig_user_id"], parse_ts(now), since=r["done_at"])
        second = "median_avg_view_pct" if "median_avg_view_pct" in after else "median_save_rate_pct"
        views, save = pct(after["median_views"], base.get("median_views")), pct(after.get(second), base.get(second))
        fol = None if after["followers"] is None or base.get("followers") is None else after["followers"] - base["followers"]
        if after["posts"] < 2:
            verdict = "too early"
        else:
            moves = [x for x in (views, save) if x is not None]
            verdict = "improved" if moves and min(moves) >= 20 or (moves and sum(moves) / len(moves) >= 20) else "worse" if moves and sum(moves) / len(moves) <= -20 else "flat"
        out = {"checked_at": now, "posts_after": after["posts"], "before": base, "after": after, "change_pct": {"median_views": views, "median_save_rate" if second == "median_save_rate_pct" else "median_avg_view_pct": save}, "followers_change": fol, "verdict": verdict,
               "note": "Compares posts made after you marked this done with the 5 posts before. Few posts and other changes mean this is a hint, not proof."}
        conn.execute(f"UPDATE recommendations SET outcome_json = {db.PH} WHERE rec_id = {db.PH}", (json.dumps(out), r["rec_id"]))
        n += 1
    conn.commit()
    return n


def add_notes(conn, topic, summary, url=None, title=None, region=None, language=None, confidence="medium", ttl_days=45, now=None, platform="any"):
    now = now or db.utcnow()
    if not topic or not summary:
        raise ValueError("topic and summary are required")
    if not (url and re.match(r"^https?://", url)):
        raise ValueError("a source url (http or https) is required: a market note without a source is not stored")
    if confidence not in ("low", "medium", "high"):
        raise ValueError("confidence must be low, medium or high")
    exp = (parse_ts(now) + datetime.timedelta(days=int(ttl_days))).strftime("%Y-%m-%dT%H:%M:%SZ")
    if platform not in ("any", "instagram", "youtube"):
        raise ValueError("platform must be any, instagram or youtube")
    nid = "n-" + fid(topic.lower(), url)[:8]
    db.upsert(conn, "market_notes", {"note_id": nid, "topic": topic[:120], "summary": summary[:700], "source_url": url, "source_title": (title or "")[:160], "region": region, "language": language,
                                     "confidence": confidence, "collected_at": now, "expires_at": exp, "platform": platform}, ("note_id",))
    conn.commit()
    return nid


def add_recs(conn, uid, items, now=None):
    """Validate and store recommendations written by Claude. Every item must cite stored findings or market notes."""
    now = now or db.utcnow()
    if not isinstance(items, list) or not items:
        raise ValueError("expected a non-empty JSON list")
    if len(items) > 8:
        raise ValueError("at most 8 recommendations per call: choose the ones that matter")
    errors, stored = [], []
    open_titles = {re.sub(r"\W+", " ", r["title"].lower()).strip() for r in db.rows(conn, f"SELECT title FROM recommendations WHERE ig_user_id = {db.PH} AND status IN ('open','done')", (uid,))}
    for i, it in enumerate(items):
        where = f"item {i + 1}"
        try:
            title, action = str(it.get("title", "")).strip(), str(it.get("action", "")).strip()
            if not title or not action:
                raise ValueError("title and action are required")
            if len(title) > 120 or len(action) > 500 or len(str(it.get("why", ""))) > 700 or len(str(it.get("expected_effect", ""))) > 300:
                raise ValueError("too long: title 120, action 500, why 700, expected_effect 300 characters")
            cat = it.get("category")
            if cat not in CATEGORIES:
                raise ValueError(f"category must be one of {', '.join(CATEGORIES)}")
            pr = it.get("priority")
            if pr not in (1, 2, 3):
                raise ValueError("priority must be 1, 2 or 3")
            conf = it.get("confidence", "medium")
            if conf not in ("low", "medium", "high"):
                raise ValueError("confidence must be low, medium or high")
            fids, nids = list(it.get("finding_ids") or []), list(it.get("note_ids") or [])
            if not fids and not nids:
                raise ValueError("cite at least one finding_id or note_id: advice without evidence is not stored")
            for x in fids:
                if not db.one(conn, f"SELECT 1 AS ok FROM findings WHERE finding_id = {db.PH} AND ig_user_id = {db.PH}", (x, uid)):
                    raise ValueError(f"unknown finding_id {x}")
            for x in nids:
                if not db.one(conn, f"SELECT 1 AS ok FROM market_notes WHERE note_id = {db.PH}", (x,)):
                    raise ValueError(f"unknown note_id {x}")
            key = re.sub(r"\W+", " ", title.lower()).strip()
            if key in open_titles:
                raise ValueError("a recommendation with this title already exists")
        except ValueError as e:
            L.ignored(LOG, "add_recs: ValueError (optional or expected)", e)
            errors.append(f"{where}: {e}")
            continue
        open_titles.add(key)
        rid = "c-" + uuid.uuid4().hex[:10]
        db.upsert(conn, "recommendations", {"rec_id": rid, "ig_user_id": uid, "source": "claude", "rule_id": None, "finding_ids": json.dumps(fids), "note_ids": json.dumps(nids),
                                            "priority": pr, "category": cat, "title": title, "why": str(it.get("why", "")), "action": action, "expected_effect": str(it.get("expected_effect", "")),
                                            "confidence": conf, "status": "open", "created_at": now, "updated_at": now}, ("rec_id",))
        for x in fids:
            conn.execute(f"UPDATE recommendations SET status = 'superseded', updated_at = {db.PH} WHERE source = 'rule' AND status = 'open' AND ig_user_id = {db.PH} AND finding_ids = {db.PH}",
                         (now, uid, json.dumps([x])))
        stored.append(rid)
    conn.commit()
    return {"stored": stored, "rejected": errors}


# ---------------------------------------------------------------- pack

def pack(conn, uid, now=None):
    nowdt = parse_ts(now or db.utcnow())
    T, tz = settings()
    D = load(conn, uid, nowdt)
    M = sorted([p for p in D["measured"] if p["age"] is not None and p["age"] >= 3], key=lambda p: -p["views"])
    recs = db.rows(conn, f"SELECT rec_id, source, priority, category, title, action, status, dismissed_reason, outcome_json, finding_ids FROM recommendations WHERE ig_user_id = {db.PH} AND status != 'superseded' ORDER BY updated_at DESC LIMIT 40", (uid,))
    for r in recs:
        r["outcome"] = json.loads(r.pop("outcome_json") or "null")
    return {
        "generated_at": nowdt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "account": {"label": D["account"]["label"], "username": D["account"]["username"], "followers": latest_followers(D), "posts_measured": len(D["measured"])},
        "settings": {"target_posts_per_week": T["target_posts_per_week"], "timezone": tz},
        "top_posts": [brief_post(p) for p in M[:5]],
        "bottom_posts": [brief_post(p) for p in M[::-1][:5]] if len(M) >= 8 else [],
        "findings": [{"finding_id": r["finding_id"], "rule_id": r["rule_id"], "category": r["category"], "severity": r["severity"], "title": r["title"], "detail": r["detail"], "evidence": json.loads(r["evidence_json"] or "{}")}
                     for r in db.rows(conn, f"SELECT * FROM findings WHERE ig_user_id = {db.PH} AND status = 'open' ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END", (uid,))],
        "recommendations_so_far": recs,
        "market": {"notes": D["notes"], "peers_tracked": len(D["peers"]), "hashtag_posts_stored": len(D["tag_media"]),
                   "note": "peers and hashtags need Facebook Login and Instagram Public Content Access. If peers_tracked is 0 the web notes are the market view."},
        "content_mix": {"languages": sorted({p["language"] for p in D["posts"] if p["language"]}), "genres": sorted({p["genre"] for p in D["posts"] if p["genre"]})},
        "rules_for_the_advisor": [
            "Cite finding_ids or note_ids on every recommendation. The store rejects anything without evidence.",
            "Organic growth only: content, hooks, timing, captions, hashtags, engagement habits. No paid boosts, no automation of likes or comments.",
            "Say what the numbers support and what they do not. Few posts means low confidence.",
            "Do not repeat recommendations already open, done or dismissed. Check recommendations_so_far, including outcomes.",
            "Market claims need a stored note with a source url. Do not invent statistics.",
        ],
    }


# ---------------------------------------------------------------- cli

def targets(conn, account, platform="instagram"):
    if platform == "youtube":
        rows = [r for r in db.rows(conn, "SELECT channel_id AS ig_user_id, label, title AS username FROM yt_channels ORDER BY CASE WHEN label = 'music' THEN 0 ELSE 1 END, label") if account in ("all", r["label"])]
        if not rows:
            sys.exit("navaan: no YouTube data yet. Run: python3 scripts/yt_collect.py collect")
        return rows
    rows = account_rows(conn, account)
    if not rows:
        sys.exit("navaan: no analytics data yet. Run: python3 scripts/ig_collect.py collect")
    return rows


def cmd_analyze(a):
    conn = db.connect(a.db)
    for r in targets(conn, a.account, a.platform):
        if a.platform == "youtube":
            import yt_reco
            res = yt_reco.analyze(conn, r["ig_user_id"])
        else:
            res = analyze(conn, r["ig_user_id"])
        outcomes(conn)
        print(f"{r['label']}: {res['findings']} findings {json.dumps(res['by_severity'])}, recommendations refreshed {res['open_recommendations']}")
    try:
        import analytics_api
        h = analytics_api.hashtag_block(conn, [r["ig_user_id"] for r in targets(conn, a.account)], write=True)
        print("hashtags.json:", h.get("file") or h.get("file_error"))
    except Exception as e:
        print("hashtags.json not written:", str(e)[:120])


def cmd_pack(a):
    conn = db.connect(a.db)
    t = targets(conn, a.account, a.platform)
    if a.platform == "youtube":
        import yt_reco
        data = [yt_reco.pack(conn, r["ig_user_id"]) for r in t]
    else:
        data = [pack(conn, r["ig_user_id"]) for r in t]
    out = json.dumps(data[0] if len(data) == 1 else data, indent=2, ensure_ascii=False, default=str)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        print("wrote", a.out)
    else:
        print(out)


def cmd_note(a):
    conn = db.connect(a.db)
    try:
        print(add_notes(conn, a.topic, a.summary, a.url, a.title, a.region, a.language, a.confidence, a.ttl_days, platform=a.note_platform))
    except ValueError as e:
        L.ignored(LOG, "cmd_note: ValueError (optional or expected)", e)
        sys.exit(f"navaan: {e}")


def cmd_add(a):
    conn = db.connect(a.db)
    t = targets(conn, a.account, a.platform)
    if len(t) != 1:
        sys.exit("navaan: add needs one account: pass --account music or --account inspiration")
    try:
        res = add_recs(conn, t[0]["ig_user_id"], json.load(sys.stdin if a.file == "-" else open(a.file, encoding="utf-8")))
    except (ValueError, json.JSONDecodeError) as e:
        L.ignored(LOG, "cmd_add: ValueError/JSONDecodeError (optional or expected)", e)
        sys.exit(f"navaan: {e}")
    print(json.dumps(res, indent=2, ensure_ascii=False))
    sys.exit(0 if not res["rejected"] else 1)


def cmd_list(a):
    conn = db.connect(a.db)
    for r in targets(conn, a.account, a.platform):
        q = f"SELECT rec_id, source, priority, category, title, status, action FROM recommendations WHERE ig_user_id = {db.PH} AND status != 'superseded'" + ("" if a.status == "all" else f" AND status = {db.PH}") + " ORDER BY priority, updated_at DESC"
        for x in db.rows(conn, q, (r["ig_user_id"],) if a.status == "all" else (r["ig_user_id"], a.status)):
            print(f"[{x['rec_id']}] P{x['priority']} {x['category']:<10} {x['status']:<9} ({x['source']}) {x['title']}\n      {x['action']}")


def cmd_status(a):
    conn = db.connect(a.db)
    try:
        set_status(conn, a.rec_id, a.new_status, a.reason)
    except ValueError as e:
        L.ignored(LOG, "cmd_status: ValueError (optional or expected)", e)
        sys.exit(f"navaan: {e}")
    print("ok")


def cmd_outcomes(a):
    print("checked", outcomes(db.connect(a.db)), "done recommendations")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db")
    ap.add_argument("--platform", default="instagram", choices=["instagram", "youtube"], help="which platform's data (default instagram)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("analyze"); s.add_argument("--account", default="all"); s.set_defaults(fn=cmd_analyze)
    s = sp.add_parser("pack"); s.add_argument("--account", default="all"); s.add_argument("--out"); s.set_defaults(fn=cmd_pack)
    s = sp.add_parser("note"); s.add_argument("--topic", required=True); s.add_argument("--summary", required=True); s.add_argument("--url"); s.add_argument("--title")
    s.add_argument("--region"); s.add_argument("--language"); s.add_argument("--confidence", default="medium"); s.add_argument("--ttl-days", type=int, default=45)
    s.add_argument("--note-platform", default="any", choices=["any", "instagram", "youtube"], help="which board the note informs"); s.set_defaults(fn=cmd_note)
    s = sp.add_parser("add"); s.add_argument("--file", default="-"); s.add_argument("--account", default="music"); s.set_defaults(fn=cmd_add)
    s = sp.add_parser("list"); s.add_argument("--status", default="open", choices=["open", "done", "dismissed", "all"]); s.add_argument("--account", default="all"); s.set_defaults(fn=cmd_list)
    s = sp.add_parser("status"); s.add_argument("rec_id"); s.add_argument("new_status", choices=["open", "done", "dismissed"]); s.add_argument("--reason"); s.set_defaults(fn=cmd_status)
    sp.add_parser("outcomes").set_defaults(fn=cmd_outcomes)
    a = ap.parse_args()
    a.fn(a)
