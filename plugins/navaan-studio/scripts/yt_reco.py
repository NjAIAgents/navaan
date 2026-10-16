"""yt_reco.py  YouTube rules for the NAVAAN recommendation engine. Same design as ig_reco.py, other data.

Rules read the YouTube tables that yt_collect.py fills, write FINDINGS with evidence, and each finding gets plain rule based advice.
Claude (growth-advisor) can then research the market and store better recommendations through ig_reco.py --platform youtube.
Findings and recommendations live in the shared tables. Their ig_user_id column holds the channel id for YouTube.

Rules of thumb are marked basis: rule_of_thumb in the evidence. Where no honest benchmark exists a video is compared with the channel's own
videos of the same kind (Shorts with Shorts, full videos with full videos). Thresholds can be tuned in navaan.config.json under
analytics.youtube_thresholds. Nothing here touches YouTube."""
import os, sys, json, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analytics_db as db
import navaan_log as _nl
_LOG = _nl.get("yt_reco")
import ig_reco as R
from ig_reco import f, med, mean, parse_ts, tags_in

THRESHOLDS = {
    "target_uploads_per_week": 1,
    "stale_days": 3,
    "gap_medium_days": 14,
    "gap_high_days": 30,
    "min_measured": 4,
    "min_age_days": 7,           # YouTube keeps distributing for weeks, so a video is judged only after this many days
    "underperform_ratio": 0.5,
    "weak_retention_ratio": 0.75,
    "early_drop_ratio": 0.5,     # share of viewers still watching at 10 percent of the video; below this the opening loses people
    "subs_per_1000_views": 2.0,  # rule of thumb floor, 0.2 percent
    "search_share_floor": 0.05,
    "decline_views": 0.30,
    "language_gap": 1.5,
}


def settings():
    t = dict(THRESHOLDS)
    try:
        from navaan_common import cfg
        t.update({k: v for k, v in (cfg("analytics.youtube_thresholds", {}) or {}).items() if k in t})
    except SystemExit as _e:
        _nl.ignored(_LOG, "no profile yet, the default thresholds are used", _e)
    return t


def load(conn, cid, now):
    D = {"cid": cid, "now": now}
    D["channel"] = db.one(conn, f"SELECT * FROM yt_channels WHERE channel_id = {db.PH}", (cid,))
    vids = db.rows(conn, f"""SELECT v.video_id, v.slug, v.kind, v.title, v.published_at, v.duration_s, v.privacy, s.title AS song, s.language, s.genre,
        sn.views, sn.likes, sn.comments, sn.minutes_watched, sn.avg_view_s, sn.avg_view_pct, sn.subs_gained, sn.subs_lost, sn.shares
        FROM yt_videos v LEFT JOIN songs s ON s.slug = v.slug
        LEFT JOIN yt_snapshots sn ON sn.video_id = v.video_id AND sn.captured_at = (SELECT MAX(captured_at) FROM yt_snapshots WHERE video_id = v.video_id)
        WHERE v.channel_id = {db.PH} AND v.deleted_at IS NULL ORDER BY v.published_at DESC""", (cid,))
    for v in vids:
        dt = parse_ts(v["published_at"])
        v["age"] = (now - dt).total_seconds() / 86400 if dt else None
        v["name"] = v["song"] or v["title"] or v["video_id"]
        v["weekday"], v["hour"] = (dt.strftime("%A"), dt.hour) if dt else (None, None)
        v["subs_per_1000"] = (1000.0 * v["subs_gained"] / v["views"]) if v["subs_gained"] is not None and v["views"] else None
    D["videos"] = vids
    D["public"] = [v for v in vids if v["privacy"] == "public"]
    D["measured"] = [v for v in D["public"] if v["views"] is not None]
    series = lambda m: db.rows(conn, f"SELECT period_end AS d, value AS v FROM yt_daily WHERE channel_id = {db.PH} AND metric = {db.PH} ORDER BY period_end", (cid, m))
    D["subs"], D["views"], D["subs_gained"] = series("subscribers_count"), series("views"), series("subs_gained")
    D["retention"] = {}
    for r in db.rows(conn, f"""SELECT video_id, ratio, watch_ratio FROM yt_retention WHERE video_id IN (SELECT video_id FROM yt_videos WHERE channel_id = {db.PH})
        AND captured_on = (SELECT MAX(captured_on) FROM yt_retention q WHERE q.video_id = yt_retention.video_id) ORDER BY ratio""", (cid,)):
        D["retention"].setdefault(r["video_id"], []).append((r["ratio"], r["watch_ratio"]))
    D["traffic"] = db.rows(conn, f"""SELECT source, views FROM yt_traffic WHERE channel_id = {db.PH} AND captured_on = (SELECT MAX(captured_on) FROM yt_traffic WHERE channel_id = {db.PH}) ORDER BY views DESC""", (cid, cid))
    aud = {}
    for r in db.rows(conn, f"""SELECT breakdown, bucket, value FROM yt_audience a WHERE channel_id = {db.PH}
        AND captured_on = (SELECT MAX(captured_on) FROM yt_audience b WHERE b.channel_id = a.channel_id AND b.breakdown = a.breakdown) ORDER BY value DESC""", (cid,)):
        aud.setdefault(r["breakdown"], []).append((r["bucket"], r["value"]))
    D["audience"] = aud
    D["waiting"] = db.rows(conn, f"""SELECT c.comment_id, c.posted_at FROM yt_comments c WHERE c.parent_id IS NULL AND c.is_own = 0
        AND c.video_id IN (SELECT video_id FROM yt_videos WHERE channel_id = {db.PH})
        AND NOT EXISTS (SELECT 1 FROM yt_comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1) ORDER BY c.posted_at""", (cid,))
    D["last_ok"] = db.one(conn, f"SELECT finished_at FROM yt_runs WHERE channel_id = {db.PH} AND status IN ('ok','partial') ORDER BY finished_at DESC LIMIT 1", (cid,))
    D["notes"] = db.rows(conn, f"""SELECT note_id, topic, summary, source_url, source_title, region, language, confidence, collected_at FROM market_notes
        WHERE (expires_at IS NULL OR expires_at >= {db.PH}) AND platform IN ('any', 'youtube') ORDER BY collected_at DESC""", (now.strftime("%Y-%m-%dT%H:%M:%SZ"),))
    return D


def brief(v):
    return {"video_id": v["video_id"], "name": v["name"], "kind": v["kind"], "slug": v["slug"], "published_at": v["published_at"], "language": v["language"], "genre": v["genre"],
            "duration_s": v["duration_s"], "views": v["views"], "likes": v["likes"], "comments": v["comments"], "avg_view_pct": None if v["avg_view_pct"] is None else round(v["avg_view_pct"], 1),
            "avg_view_s": None if v["avg_view_s"] is None else round(v["avg_view_s"], 1), "subs_gained": v["subs_gained"], "minutes_watched": None if v["minutes_watched"] is None else round(v["minutes_watched"])}


def same_kind(D, v, min_age):
    return [x for x in D["measured"] if x["kind"] == v["kind"] and x["age"] is not None and x["age"] >= min_age]


# ---------------------------------------------------------------- rules

def r_data(D, T):
    out = []
    last = parse_ts((D["last_ok"] or {}).get("finished_at"))
    age = (D["now"] - last).total_seconds() / 86400 if last else None
    if age is None or age > T["stale_days"]:
        out.append(f("yt_data_stale", "account", "data", "high", "YouTube data is stale" if last else "No successful YouTube collect yet", "Every other YouTube recommendation depends on fresh numbers.",
                     {"last_success": (D["last_ok"] or {}).get("finished_at"), "days_old": None if age is None else round(age, 1)}))
    if D["channel"] and not D["channel"]["analytics_ok"]:
        out.append(f("yt_no_analytics", "account", "data", "info", "Watch time and retention are not being collected", "The collector is using the publishing login, which cannot read YouTube Analytics.",
                     {"fix": "python3 scripts/yt_collect.py auth --account " + D["channel"]["label"]}))
    if len(D["measured"]) < T["min_measured"] + 1:
        out.append(f("yt_data_thin", "account", "data", "info", f"Only {len(D['measured'])} public videos have numbers", "Patterns need several videos. Treat advice as directional.",
                     {"measured_videos": len(D["measured"]), "needed": T["min_measured"] + 1}))
    return out


def r_private(D, T):
    old = [v for v in D["videos"] if v["privacy"] in ("private", "unlisted") and v["age"] is not None and v["age"] >= 3]
    if not old:
        return []
    return [f("yt_still_private", "account", "growth", "medium", f"{len(old)} uploaded video{'s are' if len(old) > 1 else ' is'} still not public", "A video that stays private or unlisted earns no views.",
              {"videos": [{"video_id": v["video_id"], "name": v["name"], "privacy": v["privacy"], "days_since_upload": round(v["age"])} for v in old[:8]]})]


def r_cadence(D, T):
    pub = [v for v in D["public"] if v["age"] is not None]
    if not pub:
        return []
    out, gap = [], min(v["age"] for v in pub)
    if gap > T["gap_medium_days"]:
        out.append(f("yt_posting_gap", "account", "cadence", "high" if gap > T["gap_high_days"] else "medium", f"No public upload for {int(gap)} days", "The channel stops surfacing in subscriber feeds when uploads stop.",
                     {"days_since_last_upload": round(gap, 1), "last_upload": min(pub, key=lambda v: v["age"])["published_at"]}))
    n28 = len([v for v in pub if v["age"] <= 28])
    ppw = n28 / 4.0
    if gap <= T["gap_medium_days"] and ppw < 0.5 * T["target_uploads_per_week"]:
        out.append(f("yt_cadence_low", "account", "cadence", "low", f"About {ppw:.1f} uploads per week against a target of {T['target_uploads_per_week']}", "Steady uploads give viewers a reason to come back.",
                     {"uploads_last_28_days": n28, "per_week": round(ppw, 2), "target": T["target_uploads_per_week"]}))
    return out


def window_sum(series, now, start_back, end_back):
    lo, hi = (now - datetime.timedelta(days=start_back)).strftime("%Y-%m-%d"), (now - datetime.timedelta(days=end_back)).strftime("%Y-%m-%d")
    xs = [r["v"] for r in series if lo <= r["d"] < hi and r["v"] is not None]
    return (sum(xs), len(xs)) if xs else (None, 0)


def r_trend(D, T):
    out, now = [], D["now"]
    sub = [r for r in D["subs"] if r["d"] >= (now - datetime.timedelta(days=14)).strftime("%Y-%m-%d")]
    recent = len([v for v in D["public"] if v["age"] is not None and v["age"] <= 14])
    if len(sub) >= 8 and sub[-1]["v"] - sub[0]["v"] <= 0:
        out.append(f("yt_subs_stall", "account", "growth", "medium" if recent else "high", "Subscribers have not grown in 14 days" if sub[-1]["v"] == sub[0]["v"] else "Subscribers fell in 14 days",
                     "Viewers are not turning into subscribers.", {"subscribers_start": sub[0]["v"], "subscribers_now": sub[-1]["v"], "uploads_in_period": recent}))
    v_now, n1 = window_sum(D["views"], now, 7, -1)
    v_prev, n2 = window_sum(D["views"], now, 14, 7)
    if n1 >= 5 and n2 >= 5 and v_prev and v_now < v_prev * (1 - T["decline_views"]):
        out.append(f("yt_views_decline", "account", "content", "medium", f"Views fell {round(100 * (1 - v_now / v_prev))}% week on week", "Last 7 days against the 7 before.", {"views_last_7d": v_now, "views_prev_7d": v_prev}))
    g, _ = window_sum(D["subs_gained"], now, 28, -1)
    v28, _ = window_sum(D["views"], now, 28, -1)
    if g is not None and v28 and v28 >= 500 and 1000.0 * g / v28 < T["subs_per_1000_views"]:
        out.append(f("yt_low_subscribe_rate", "account", "growth", "medium", "Few viewers subscribe", "Views are not turning into subscribers.",
                     {"subscribers_gained_28d": g, "views_28d": v28, "per_1000_views": round(1000.0 * g / v28, 2), "basis": "rule_of_thumb"}))
    return out


def r_videos(D, T):
    out = []
    best_pool = [v for v in D["measured"] if v["age"] is not None and v["age"] >= T["min_age_days"]]
    for v in best_pool:
        peers = same_kind(D, v, T["min_age_days"])
        if len(peers) < T["min_measured"]:
            continue
        mv, mp = med([p["views"] for p in peers]), med([p["avg_view_pct"] for p in peers])
        if mv and v["views"] < T["underperform_ratio"] * mv:
            out.append(f("yt_underperformer", v["video_id"], "content", "medium", f"\"{v['name']}\" got under half the usual views for a {v['kind']}", f"{v['views']} views against a median of {int(mv)}.",
                         {"video": brief(v), "median_views": mv, "ratio": round(v["views"] / mv, 2)}))
        if mp and v["avg_view_pct"] is not None and v["avg_view_pct"] < T["weak_retention_ratio"] * mp:
            out.append(f("yt_weak_retention", v["video_id"], "retention", "medium", f"\"{v['name']}\" lost viewers sooner than your other {v['kind']}s",
                         f"Average {v['avg_view_pct']:.0f}% watched against a median of {mp:.0f}%.", {"video": brief(v), "median_avg_view_pct": round(mp, 1)}))
    for vid, curve in D["retention"].items():
        v = next((x for x in D["videos"] if x["video_id"] == vid), None)
        if not v or v["age"] is None or v["age"] < 3 or (v["views"] or 0) < 50:
            continue
        at10 = next((w for r, w in curve if abs(r - 0.10) < 0.011 and w is not None), None)
        if at10 is not None and at10 < T["early_drop_ratio"]:
            out.append(f("yt_early_dropoff", vid, "hook", "medium", f"\"{v['name']}\" loses half its viewers in the first 10%", f"Only {at10 * 100:.0f}% are still watching at the 10% mark.",
                         {"video": brief(v), "watching_at_10pct": round(at10, 3), "basis": "rule_of_thumb"}))
    if best_pool:
        best = max(best_pool, key=lambda v: v["views"])
        out.append(f("yt_best_video_pattern", best["video_id"], "content", "info", f"Your best recent {best['kind']}: \"{best['name']}\"", "What it had that the others did not is worth repeating.",
                     {"video": brief(best), "weekday": best["weekday"], "hour_utc": best["hour"], "title_length": len(best["title"] or "")}))
    return out


def r_kinds(D, T):
    S = [v for v in D["measured"] if v["kind"] == "short" and v["age"] is not None and v["age"] >= T["min_age_days"]]
    L = [v for v in D["measured"] if v["kind"] == "video" and v["age"] is not None and v["age"] >= T["min_age_days"]]
    if len(S) < 2 or len(L) < 2:
        return []
    ms, ml = med([v["views"] for v in S]), med([v["views"] for v in L])
    ss, sl = med([v["subs_per_1000"] for v in S]), med([v["subs_per_1000"] for v in L])
    if ml and ms and ms >= 3 * ml:
        return [f("yt_shorts_vs_full", "kinds", "format", "info", "Shorts get several times the views of full videos", "Use Shorts to bring people to the full songs.",
                  {"median_views_shorts": ms, "median_views_full": ml, "subs_per_1000_views_shorts": None if ss is None else round(ss, 2), "subs_per_1000_views_full": None if sl is None else round(sl, 2)})]
    return []


def r_groups(D, T):
    out = []
    for key, rule in (("language", "yt_language_gap"), ("genre", "yt_genre_gap")):
        groups = {}
        for v in D["measured"]:
            if v[key] and v["kind"] == "video":
                groups.setdefault(v[key], []).append(v["views"])
        big = {k: x for k, x in groups.items() if len(x) >= 2}
        if len(big) >= 2:
            avg = {k: sum(x) / len(x) for k, x in big.items()}
            hi, lo = max(avg, key=avg.get), min(avg, key=avg.get)
            if avg[lo] and avg[hi] / avg[lo] >= T["language_gap"]:
                out.append(f(rule, key, "content", "low", f"{hi} videos get {avg[hi] / avg[lo]:.1f}x the views of {lo} videos", f"Full videos only, by {key}, average views.",
                             {"groups": {k: {"videos": len(big[k]), "avg_views": round(avg[k])} for k in big}, "better": hi, "weaker": lo}))
    return out


def r_traffic(D, T):
    tot = sum(r["views"] or 0 for r in D["traffic"])
    if tot < 100:
        return []
    share = {r["source"]: (r["views"] or 0) / tot for r in D["traffic"]}
    out = []
    if share.get("YT_SEARCH", 0) < T["search_share_floor"]:
        out.append(f("yt_search_low", "traffic", "packaging", "low", "YouTube search brings almost no views", "Titles and descriptions that match what people type are the main lever for search.",
                     {"search_share": round(share.get("YT_SEARCH", 0), 3), "views_28d": tot, "top_sources": [(r["source"], r["views"]) for r in D["traffic"][:4]], "basis": "rule_of_thumb"}))
    if share.get("SHORTS", 0) > 0.6:
        out.append(f("yt_shorts_feed_dependent", "traffic", "growth", "info", "Most views come from the Shorts feed", "Shorts viewers rarely watch full songs unless pointed there.",
                     {"shorts_share": round(share["SHORTS"], 3), "top_sources": [(r["source"], r["views"]) for r in D["traffic"][:4]]}))
    return out


def r_comments(D, T):
    if not D["waiting"]:
        return []
    oldest = parse_ts(D["waiting"][0]["posted_at"])
    hours = (D["now"] - oldest).total_seconds() / 3600 if oldest else 0
    if hours < 24:
        return []
    return [f("yt_comments_unanswered", "account", "engagement", "medium", f"{len(D['waiting'])} YouTube comments are waiting for a reply", "Replies keep viewers coming back and boost the video.", {"waiting": len(D["waiting"]), "oldest_hours": round(hours)})]


def r_audience(D, T):
    c = D["audience"].get("country") or []
    total = sum(v or 0 for _, v in c)
    if total and len(c) >= 2 and c[1][1] / total >= 0.25:
        return [f("yt_audience_split", "account", "audience", "info", f"Your viewers split between {c[0][0]} and {c[1][0]}", "Titles and descriptions in the language of both groups reach both.",
                  {"countries": [(b, v, round(100 * v / total)) for b, v in c[:4]]})]
    return []


RULES = (r_data, r_private, r_cadence, r_trend, r_videos, r_kinds, r_groups, r_traffic, r_comments, r_audience)


def run_rules(D, T):
    out = []
    for r in RULES:
        out.extend(r(D, T))
    return out


# ---------------------------------------------------------------- advice

def advice(fd):
    e, r = fd["evidence"], fd["rule_id"]
    nm = (e.get("video") or {}).get("name", "this video")
    A = {
        "yt_data_stale": ("Refresh the YouTube data", "Run /navaan-studio:collect or press Collect now on the YouTube tab. If it stops with a sign in error, run yt_collect.py auth again.", "Fresh numbers, so every other finding is trustworthy.", "high"),
        "yt_no_analytics": ("Add the read only analytics login", f"Run {e.get('fix')} once. It asks for read only access to YouTube Analytics and does not touch publishing.", "Watch time, retention curves, traffic sources and audience become available.", "high"),
        "yt_data_thin": ("Keep publishing before drawing conclusions", "Publish steadily for the next weeks and re-run the analysis once at least 5 public videos have numbers.", "Clearer patterns and fewer false alarms.", "high"),
        "yt_still_private": ("Finish publishing the videos that are still private", "Check each listed video, approve go_public in the portal when it is ready, or delete it if it will not be released.", "Views can only start once a video is public.", "high"),
        "yt_posting_gap": ("Publish the next ready item", "Release the next finished song, or cut a Short from a released one. A good enough upload this week beats a perfect one next month.", "The channel appears again in subscriber feeds.", "medium"),
        "yt_cadence_low": ("Raise upload frequency toward your target", f"Plan {e.get('target', 1)} upload per week: alternate a full song with a Short cut from a released song.", "More chances for a video to find new viewers.", "medium"),
        "yt_subs_stall": ("Give viewers a reason to subscribe", "Say in the first lines of the description and in a pinned comment what subscribers get (next release, language, mood). Add the channel to the end screen of every full video.", "A higher share of viewers who subscribe.", "low"),
        "yt_views_decline": ("Find what changed in the last two weeks", "Compare the latest upload with the best one: title, thumbnail, first 30 seconds, length. Repeat what the best one did.", "Views return toward the earlier level.", "low"),
        "yt_low_subscribe_rate": ("Convert viewers into subscribers", "Put one clear call to subscribe in the video (spoken or on screen) and in the description. Link the next song in the end screen so a viewer has a reason to stay.", "More subscribers per 1000 views.", "medium"),
        "yt_underperformer": ("Learn from a weak upload", f"Compare \"{nm}\" with your best {(e.get('video') or {}).get('kind', 'video')} on title, thumbnail, opening seconds and length. Retitle or change the thumbnail first, it costs nothing.", "A better title and thumbnail often lift views on an existing video.", "low"),
        "yt_weak_retention": ("Tighten the middle of the video", f"Watch \"{nm}\" with the retention curve open in Studio, find where it drops, and cut or reorder that part next time.", "A higher average percentage viewed, which helps recommendation.", "medium"),
        "yt_early_dropoff": ("Fix the first seconds", f"Open \"{nm}\" on the strongest line or visual moment instead of an intro. Put the hook text on screen in the first second and test it on the next upload.", "More viewers still watching at the 10% mark.", "medium"),
        "yt_best_video_pattern": ("Make the next upload resemble your best one", f"Match the best video's kind, length, title style and publish slot ({e.get('weekday')}, {e.get('hour_utc')} UTC), and change one thing at a time.", "Repeats what worked, with a clean comparison.", "medium"),
        "yt_shorts_vs_full": ("Use Shorts to send people to full songs", "End each Short with a line pointing to the full song, and put the full video link in the Short's pinned comment.", "Short viewers become full video viewers.", "low"),
        "yt_language_gap": ("Lean into the language that travels", f"{e.get('better')} outperforms {e.get('weaker')}. Release more in {e.get('better')}, and use Shorts in it to bring people to the other language.", "Higher average views while keeping both audiences.", "low"),
        "yt_genre_gap": ("Lean into the genre that travels", f"{e.get('better')} outperforms {e.get('weaker')}. Plan the next release in {e.get('better')} and compare.", "Higher average views per release.", "low"),
        "yt_search_low": ("Write titles and descriptions for search", "Put the song name, language and mood in the title (for example the lyric line plus 'Maithili lo-fi song'), and add a two line description with the same words.", "More views from search, which keep coming for months.", "low"),
        "yt_shorts_feed_dependent": ("Point Shorts viewers to full videos", "Add a pinned comment and an end line in each Short that names the full song. Use the related video link on Shorts.", "Part of the Shorts audience becomes full video viewers and subscribers.", "low"),
        "yt_comments_unanswered": ("Reply to waiting comments", f"Answer the {e.get('waiting')} waiting comments, oldest first, in the commenter's language.", "A stronger relationship with early viewers.", "medium"),
        "yt_audience_split": ("Write for both audiences", "Use both languages in the title or description, and plan a second release slot for the other region.", "Better reach in both regions.", "low"),
    }
    t = A.get(r)
    if not t:
        return None
    title, action, effect, conf = t
    return {"title": title, "why": fd["detail"] or fd["title"], "action": action, "expected_effect": effect, "confidence": conf}


# ---------------------------------------------------------------- store, snapshot, pack

def analyze(conn, cid, now=None):
    now = now or db.utcnow()
    D = load(conn, cid, R.parse_ts(now))
    return R.analyze_with(conn, cid, run_rules(D, settings()), advice, now)


def metrics_snapshot(conn, cid, now, since=None):
    D = load(conn, cid, now)
    M = [v for v in D["measured"] if v["age"] is not None and v["age"] >= 3]
    M = [v for v in M if v["published_at"] and v["published_at"] >= since] if since else M[:5]
    subs = D["subs"][-1]["v"] if D["subs"] else None
    return {"posts": len(M), "median_views": med([v["views"] for v in M]), "median_avg_view_pct": None if med([v["avg_view_pct"] for v in M]) is None else round(med([v["avg_view_pct"] for v in M]), 1),
            "median_save_rate_pct": None, "followers": subs}


def pack(conn, cid, now=None):
    nowdt = R.parse_ts(now or db.utcnow())
    T = settings()
    D = load(conn, cid, nowdt)
    M = sorted([v for v in D["measured"] if v["age"] is not None and v["age"] >= 3], key=lambda v: -v["views"])
    recs = db.rows(conn, f"SELECT rec_id, source, priority, category, title, action, status, dismissed_reason, outcome_json, finding_ids FROM recommendations WHERE ig_user_id = {db.PH} AND status != 'superseded' ORDER BY updated_at DESC LIMIT 40", (cid,))
    for r in recs:
        r["outcome"] = json.loads(r.pop("outcome_json") or "null")
    ch = D["channel"] or {}
    return {
        "platform": "youtube",
        "generated_at": nowdt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "account": {"label": ch.get("label"), "title": ch.get("title"), "subscribers": D["subs"][-1]["v"] if D["subs"] else None, "videos_measured": len(D["measured"]), "analytics_login": bool(ch.get("analytics_ok"))},
        "settings": {"target_uploads_per_week": T["target_uploads_per_week"]},
        "top_videos": [brief(v) for v in M[:5]],
        "bottom_videos": [brief(v) for v in M[::-1][:5]] if len(M) >= 8 else [],
        "retention_at_10pct": {vid: next((round(w, 2) for r, w in c if abs(r - 0.10) < 0.011), None) for vid, c in list(D["retention"].items())[:8]},
        "traffic_sources_28d": [(r["source"], r["views"]) for r in D["traffic"][:8]],
        "audience": {k: v[:5] for k, v in D["audience"].items()},
        "findings": [{"finding_id": r["finding_id"], "rule_id": r["rule_id"], "category": r["category"], "severity": r["severity"], "title": r["title"], "detail": r["detail"], "evidence": json.loads(r["evidence_json"] or "{}")}
                     for r in db.rows(conn, f"SELECT * FROM findings WHERE ig_user_id = {db.PH} AND status = 'open' ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END", (cid,))],
        "recommendations_so_far": recs,
        "market": {"notes": D["notes"], "note": "Thumbnail impressions and click through rate are not available through any YouTube API. Do not claim anything about them."},
        "content_mix": {"languages": sorted({v["language"] for v in D["videos"] if v["language"]}), "genres": sorted({v["genre"] for v in D["videos"] if v["genre"]}), "kinds": sorted({v["kind"] for v in D["videos"] if v["kind"]})},
        "rules_for_the_advisor": [
            "Cite finding_ids or note_ids on every recommendation. The store rejects anything without evidence. Use: ig_reco.py --platform youtube add.",
            "Organic growth only: titles, thumbnails, hooks, descriptions, playlists, Shorts to full video funnel, replies. No paid promotion, bought views or subscribers, sub for sub schemes.",
            "Say what the numbers support and what they do not. Few videos means low confidence. Shorts and full videos are different games: compare like with like.",
            "Do not repeat recommendations already open, done or dismissed. Check recommendations_so_far, including outcomes.",
            "Market claims need a stored note with a source url (ig_reco.py --platform youtube note --note-platform youtube). Do not invent statistics.",
        ],
    }
