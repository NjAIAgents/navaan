#!/usr/bin/env python3
"""besttime.py  when to publish, from the analytics database. Offline, deterministic, read only.

Three signals, all in UTC (the portal shows them in your local time):
  online   hours when your followers are online (Instagram's online_followers, averaged over the last 14 collected days)
  own      how your own Reels did, by hour and weekday: views (else reach) of each post divided by your median, so one viral post cannot decide alone
  peers    when the strongest posts of your peers went out (top 40 percent of each peer's posts by likes plus comments)
Each signal becomes a share per hour (and per weekday for own and peers). Own needs 8 or more posts, peers 10 or more strong posts, otherwise
they are left out and the weights of the remaining signals are scaled up. Weights: online 0.5, own 0.3, peers 0.2.
Best slots are the next 7 days: weekday score times hour score. We recommend posting one hour before the followers' peak hour,
because Reels get most of their first push in the first hours, and keep at most two slots a day.

YouTube has its own block further down (analyze_youtube): your own videos, viewer countries and Instagram followers online, one answer for videos and one for Shorts.

analyze(conn, label, now=None) -> {"hours": [24 scores 0 to 100], "weekdays": [7 scores, Monday first], "slots": [...], "basis": {...}, "notes": [...]}"""
import datetime
import analytics_db as db

UTC = datetime.timezone.utc
W_ONLINE, W_OWN, W_PEERS = 0.5, 0.3, 0.2
MIN_OWN, MIN_PEERS, LEAD_MIN = 8, 10, 90
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _ts(s):
    try: return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) if s else None
    except Exception:
        try: return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC)
        except Exception: return None


def _norm(v):
    t = float(sum(v))
    return [x / t for x in v] if t > 0 else None


def _smooth(h):
    """Spread each hour a little onto its neighbours (half weight), the 24 hours wrap around midnight."""
    return [h[i] + 0.5 * h[(i - 1) % 24] + 0.5 * h[(i + 1) % 24] for i in range(24)]


def _median(xs):
    xs = sorted(xs); n = len(xs)
    return 0 if not n else (xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0)


def signals(conn, label):
    acc = db.one(conn, f"SELECT ig_user_id FROM accounts WHERE label = {db.PH}", (label,))
    if not acc: return None
    uid = acc["ig_user_id"]
    last = db.one(conn, f"SELECT MAX(captured_on) AS d FROM online_hours WHERE ig_user_id = {db.PH}", (uid,))["d"]
    online = [0.0] * 24
    if last:
        rows = db.rows(conn, f"SELECT hour, AVG(followers) AS f FROM online_hours WHERE ig_user_id = {db.PH} AND captured_on >= "
                             f"(SELECT date(MAX(captured_on), '-13 day') FROM online_hours WHERE ig_user_id = {db.PH}) GROUP BY hour", (uid, uid)) \
            if getattr(db, "PH", "?") == "?" else db.rows(conn, f"SELECT hour, AVG(followers) AS f FROM online_hours WHERE ig_user_id = {db.PH} GROUP BY hour", (uid,))
        for r in rows:
            if r["f"] is not None and 0 <= int(r["hour"]) < 24: online[int(r["hour"])] = float(r["f"])
    posts = db.rows(conn, f"""SELECT m.posted_at, sn.views, sn.reach FROM media m
        LEFT JOIN media_snapshots sn ON sn.media_id = m.media_id AND sn.captured_at = (SELECT MAX(captured_at) FROM media_snapshots WHERE media_id = m.media_id)
        WHERE m.ig_user_id = {db.PH} AND m.deleted_at IS NULL AND m.posted_at IS NOT NULL""", (uid,))
    vals = [(p["views"] if p["views"] is not None else p["reach"]) for p in posts]
    med = _median([v for v in vals if v]) or 0
    own_h, own_d, n_own = [0.0] * 24, [0.0] * 7, 0
    for p, v in zip(posts, vals):
        t = _ts(p["posted_at"])
        if not t or not v or not med: continue
        r = min(4.0, v / med)  # capped, one viral post cannot decide alone
        own_h[t.hour] += r; own_d[t.weekday()] += r; n_own += 1
    peers_all = db.rows(conn, "SELECT username, note FROM peers")
    group = "inspiration" if label == "inspiration" else "music"
    mine = {p["username"] for p in peers_all if (("inspiration" in (p["note"] or "").lower()) == (group == "inspiration"))}
    by = {}
    for m in db.rows(conn, "SELECT username, posted_at, like_count, comments_count FROM peer_media WHERE posted_at IS NOT NULL"):
        if m["username"] in mine: by.setdefault(m["username"], []).append(m)
    pe_h, pe_d, n_pe = [0.0] * 24, [0.0] * 7, 0
    for u, ms in by.items():
        ms.sort(key=lambda m: -((m["like_count"] or 0) + (m["comments_count"] or 0)))
        for m in ms[:max(3, int(len(ms) * 0.4))]:
            t = _ts(m["posted_at"])
            if t: pe_h[t.hour] += 1; pe_d[t.weekday()] += 1; n_pe += 1
    return {"online": online, "own_h": own_h, "own_d": own_d, "n_own": n_own, "pe_h": pe_h, "pe_d": pe_d, "n_pe": n_pe, "online_days": bool(last)}


def analyze(conn, label, now=None):
    now = now or datetime.datetime.now(UTC)
    s = signals(conn, label)
    if not s: return {"label": label, "empty": True, "reason": "no_account"}
    parts, notes = [], []
    on = _norm(s["online"])
    if on: parts.append((W_ONLINE, on, "followers online"))
    else: notes.append("No follower online data yet. Run Collect now on the Analytics page.")
    own = _norm(_smooth(s["own_h"])) if s["n_own"] >= MIN_OWN else None
    if own: parts.append((W_OWN, own, "your own posts"))
    else: notes.append(f"Your own posts: {s['n_own']} with numbers, {MIN_OWN} needed before they count.")
    pe = _norm(_smooth(s["pe_h"])) if s["n_pe"] >= MIN_PEERS else None
    if pe: parts.append((W_PEERS, pe, "peers' best posts"))
    else: notes.append(f"Peers: {s['n_pe']} strong posts, {MIN_PEERS} needed before they count.")
    if not parts: return {"label": label, "empty": True, "reason": "no_signal", "notes": notes}
    tw = sum(w for w, _, _ in parts)
    hour = [sum(w * v[i] for w, v, _ in parts) / tw for i in range(24)]  # followers' peak hour score
    # posting hour = one hour earlier than the audience peak
    post_hour = [hour[(i + 1) % 24] for i in range(24)]
    dparts = [(w, _norm(d)) for w, d in ((W_OWN, s["own_d"] if own else None), (W_PEERS, s["pe_d"] if pe else None)) if d and _norm(d)]
    if dparts:
        dtw = sum(w for w, _ in dparts); day = [sum(w * v[i] for w, v in dparts) / dtw for i in range(7)]
    else:
        day = [1.0 / 7] * 7; notes.append("No weekday data yet, all days count the same.")
    mx = max(post_hour); top_h = sorted(range(24), key=lambda i: -post_hour[i])[:4]
    cand = []
    for k in range(0, 8):
        d0 = (now + datetime.timedelta(days=k)).replace(minute=0, second=0, microsecond=0)
        for h in top_h:
            t = d0.replace(hour=h)
            if t < now + datetime.timedelta(minutes=LEAD_MIN): continue
            cand.append((day[t.weekday()] * post_hour[h], t, h))
    cand.sort(key=lambda c: -c[0])
    slots, per = [], {}
    cmax = cand[0][0] if cand else 1
    for sc, t, h in cand:
        key = t.date()
        if per.get(key, 0) >= 2 or any(abs((t - x["_t"]).total_seconds()) < 3 * 3600 for x in slots if x["_t"].date() == key): continue
        per[key] = per.get(key, 0) + 1
        slots.append({"at": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "weekday": DAYS[t.weekday()], "hour_utc": h, "audience_peak_hour_utc": (h + 1) % 24,
                      "score": round(100 * sc / cmax), "_t": t})
        if len(slots) >= 5: break
    for x in slots: del x["_t"]
    return {"label": label, "empty": False, "hours": [round(100 * v / mx) for v in post_hour], "weekdays": [round(100 * v / max(day)) for v in day],
            "slots": slots, "notes": notes,
            "basis": {"signals": [n for _, _, n in parts], "own_posts": s["n_own"], "peer_posts": s["n_pe"], "weekday_known": bool(dparts),
                      "rule": "post one hour before the hour most of your followers are online"}}


def for_label(label, db_file=None):
    try: conn = db.connect(db_file, readonly=True)
    except Exception as e: return {"empty": True, "reason": "db_error", "error": str(e)[:200]}
    if conn is None: return {"empty": True, "reason": "no_database"}
    try: return analyze(conn, label)
    finally:
        try: conn.close()
        except Exception: pass



# ---------------------------------------------------------------- YouTube

# Usual UTC offset (hours) of the countries YouTube reports viewers from. One value per country, daylight saving ignored, large countries use their middle.
TZ_OFFSET = {"IN": 5.5, "US": -6, "GB": 0, "CA": -5, "AU": 10, "AE": 4, "PK": 5, "BD": 6, "NP": 5.75, "LK": 5.5, "SG": 8, "MY": 8, "DE": 1, "FR": 1, "NL": 1, "IT": 1, "ES": 1,
             "SA": 3, "QA": 3, "KW": 3, "OM": 4, "BH": 3, "NZ": 12, "ZA": 2, "NG": 1, "ID": 7, "PH": 8, "MU": 4, "FJ": 12, "TT": -4, "GY": -4, "BR": -3, "MX": -6, "JP": 9,
             "KR": 9, "RU": 3, "TR": 3, "EG": 2, "IE": 0, "SE": 1, "CH": 1, "BT": 6, "MV": 5, "TH": 7, "HK": 8}
# Share of a day's listening by local hour. An assumption (evenings and lunch), not a measurement, and the notes say so.
LOCAL_LISTEN = {7: 0.3, 8: 0.3, 12: 0.5, 13: 0.5, 17: 0.5, 18: 1.0, 19: 1.5, 20: 2.0, 21: 2.0, 22: 1.5, 23: 0.8}
W_YT_OWN, W_YT_ONLINE, W_YT_AUD = 0.45, 0.25, 0.30
W_YT_PEERS, MIN_YT_PEERS, PEER_MIN_AGE_D = 0.25, 15, 2   # similar Shorts found by hashtag (yt_hashtags.py)
MIN_YT_OWN, MIN_AGE_D, PRIOR = 8, 7, 2.0
YT_LEAD_H = {"video": 1, "short": 0}   # post this many hours before the audience peak


def _yt_audience_hours(conn, cid):
    """UTC hour shares from the countries viewers come from (latest country breakdown), listening assumed to peak in local evenings."""
    rows = db.rows(conn, f"""SELECT bucket, value FROM yt_audience WHERE channel_id = {db.PH} AND breakdown = 'country'
        AND captured_on = (SELECT MAX(captured_on) FROM yt_audience WHERE channel_id = {db.PH} AND breakdown = 'country')""", (cid, cid))
    tot = float(sum(r["value"] or 0 for r in rows if r["bucket"] in TZ_OFFSET))
    if tot <= 0: return None, []
    h, used = [0.0] * 24, []
    for r in rows:
        off = TZ_OFFSET.get(r["bucket"])
        if off is None or not r["value"]: continue
        share = r["value"] / tot
        used.append((r["bucket"], round(100 * share)))
        for lh, w in LOCAL_LISTEN.items():
            u = (lh - off) % 24
            lo = int(u) % 24; frac = u - int(u)
            h[lo] += share * w * (1 - frac); h[(lo + 1) % 24] += share * w * frac
    return _norm(h), used


def _yt_own(videos, kind, now):
    """Hour and weekday scores from your own videos of one kind. Each video is scored against the median of its kind on views per day (age damped),
    average share watched and subscribers per 1,000 views, so a video that was liked and kept viewers counts for more than one that only got views."""
    pool = [v for v in videos if v["kind"] == kind and v["privacy"] == "public" and v["views"] and v["age"] is not None and v["age"] >= MIN_AGE_D]
    for v in pool:
        v["rate"] = v["views"] / (min(v["age"], 30.0) + 3.0)
        v["spk"] = (1000.0 * v["subs_gained"] / v["views"]) if v["subs_gained"] is not None else None
    meds = {k: _median([v[k] for v in pool if v.get(k) is not None]) for k in ("rate", "avg_view_pct", "spk")}
    parts = (("rate", 0.5), ("avg_view_pct", 0.25), ("spk", 0.25))
    hs, ds = {}, {}
    for v in pool:
        num = den = 0.0
        for k, w in parts:
            if v.get(k) is not None and meds[k]:
                num += w * max(0.25, min(4.0, v[k] / meds[k])); den += w
        if not den: continue
        s = num / den
        hs.setdefault(v["t"].hour, []).append(s); ds.setdefault(v["t"].weekday(), []).append(s)
    shrink = lambda d, n: [(sum(d.get(i, [])) + PRIOR * 1.0) / (len(d.get(i, [])) + PRIOR) for i in range(n)]
    return {"n": len(pool), "hour": shrink(hs, 24), "day": shrink(ds, 7), "used": [p for p in ("views per day", "share watched", "subscribers per 1,000 views")]}


def _yt_peers(conn, label, now):
    """UTC hour scores from public Shorts that use your hashtags (table yt_hashtag_posts). Each is scored on views per day against the median, age damped.
    Returns (hours, n) or (None, n) when fewer than MIN_YT_PEERS posts older than PEER_MIN_AGE_D days exist. Posting hours are UTC, the peers' own time zones are unknown."""
    try:
        rows = db.rows(conn, f"SELECT published_at, views, tag FROM yt_hashtag_posts WHERE label = {db.PH} AND views IS NOT NULL", (label,))
    except Exception:
        return None, 0
    pool = []
    for r in rows:
        t = _ts(r["published_at"])
        age = (now - t).total_seconds() / 86400.0 if t else None
        if t and age is not None and age >= PEER_MIN_AGE_D:
            pool.append((t, r["views"] / (min(age, 30.0) + 3.0)))
    if len(pool) < MIN_YT_PEERS: return None, len(pool)
    med = _median([x[1] for x in pool])
    if not med: return None, len(pool)
    hs = {}
    for t, rate in pool: hs.setdefault(t.hour, []).append(max(0.25, min(4.0, rate / med)))
    return _norm(_smooth([(sum(hs.get(i, [])) + PRIOR) / (len(hs.get(i, [])) + PRIOR) for i in range(24)])), len(pool)


def _yt_traffic(conn, cid):
    rows = db.rows(conn, f"""SELECT source, views FROM yt_traffic WHERE channel_id = {db.PH}
        AND captured_on = (SELECT MAX(captured_on) FROM yt_traffic WHERE channel_id = {db.PH})""", (cid, cid))
    tot = float(sum(r["views"] or 0 for r in rows))
    if tot <= 0: return None
    sh = lambda *names: sum((r["views"] or 0) for r in rows if r["source"] in names) / tot
    sub = sh("SUBSCRIBER", "NOTIFICATION")
    return {"subscribers_pct": round(100 * sub), "shorts_pct": round(100 * sh("SHORTS")), "search_pct": round(100 * sh("YT_SEARCH")),
            "sensitivity": "high" if sub >= 0.25 else "low" if sub < 0.10 else "medium"}


def _yt_slots(post_hour, day, now, lead_min=LEAD_MIN):
    top_h = sorted(range(24), key=lambda i: -post_hour[i])[:4]
    cand = []
    for k in range(0, 8):
        d0 = (now + datetime.timedelta(days=k)).replace(minute=0, second=0, microsecond=0)
        for h in top_h:
            t = d0.replace(hour=h)
            if t < now + datetime.timedelta(minutes=lead_min): continue
            cand.append((day[t.weekday()] * post_hour[h], t, h))
    cand.sort(key=lambda c: -c[0])
    slots, per, cmax = [], {}, (cand[0][0] if cand else 1)
    for sc, t, h in cand:
        key = t.date()
        if per.get(key, 0) >= 2 or any(abs((t - x["_t"]).total_seconds()) < 3 * 3600 for x in slots if x["_t"].date() == key): continue
        per[key] = per.get(key, 0) + 1
        slots.append({"at": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "weekday": DAYS[t.weekday()], "hour_utc": h, "score": round(100 * sc / cmax), "_t": t})
        if len(slots) >= 5: break
    for x in slots: del x["_t"]
    return slots


def analyze_youtube(conn, label, now=None):
    """Best time to publish on YouTube, one answer for full videos and one for Shorts.
    Signals: your own videos of that kind scored on views, share watched and subscribers per view (weight 0.45, needs 8 or more videos older than a week),
    Instagram followers online by hour (0.25, measured, same audience), and the countries viewers come from with listening assumed to peak in local evenings (0.30, an assumption).
    Missing signals drop out and the rest scale up. Subscriber and notification traffic decides how much the exact time matters."""
    now = now or datetime.datetime.now(UTC)
    ch = db.one(conn, f"SELECT channel_id FROM yt_channels WHERE label = {db.PH}", (label,))
    if not ch: return {"label": label, "empty": True, "reason": "no_channel"}
    cid = ch["channel_id"]
    vids = db.rows(conn, f"""SELECT v.video_id, v.kind, v.published_at, v.privacy, sn.views, sn.avg_view_pct, sn.subs_gained FROM yt_videos v
        LEFT JOIN yt_snapshots sn ON sn.video_id = v.video_id AND sn.captured_at = (SELECT MAX(captured_at) FROM yt_snapshots WHERE video_id = v.video_id)
        WHERE v.channel_id = {db.PH} AND v.deleted_at IS NULL AND v.published_at IS NOT NULL""", (cid,))
    for v in vids:
        v["t"] = _ts(v["published_at"])
        v["age"] = (now - v["t"]).total_seconds() / 86400.0 if v["t"] else None
    vids = [v for v in vids if v["t"]]
    aud, countries = _yt_audience_hours(conn, cid)
    ig = signals(conn, label)
    online = _norm(ig["online"]) if ig and ig.get("online_days") and sum(ig["online"]) > 0 else None
    traffic = _yt_traffic(conn, cid)
    peer_hours, peer_n = _yt_peers(conn, label, now)
    out = {"label": label, "empty": False, "kinds": {}, "traffic": traffic, "countries": countries}
    for kind in ("video", "short"):
        own = _yt_own(vids, kind, now)
        parts, notes = [], []
        if own["n"] >= MIN_YT_OWN: parts.append((W_YT_OWN, _norm(_smooth(own["hour"])), "your own " + ("Shorts" if kind == "short" else "videos")))
        else: notes.append(f"Your own {'Shorts' if kind == 'short' else 'videos'}: {own['n']} older than {MIN_AGE_D} days with numbers, {MIN_YT_OWN} needed before they count.")
        if online: parts.append((W_YT_ONLINE, online, "Instagram followers online"))
        else: notes.append("No Instagram follower online data yet, so that signal is off.")
        if kind == "short":
            if peer_hours: parts.append((W_YT_PEERS, peer_hours, f"{peer_n} similar Shorts found by hashtag (posting hours in UTC)"))
            else: notes.append(f"Similar Shorts by hashtag: {peer_n} of {MIN_YT_PEERS} needed. Run yt_hashtags.py collect, or a full YouTube collect.")
        if aud: parts.append((W_YT_AUD, aud, "viewer countries (evening listening assumed)"))
        else: notes.append("No viewer country data yet. It needs the analytics sign-in and a collect.")
        if not parts:
            out["kinds"][kind] = {"empty": True, "reason": "no_signal", "notes": notes}; continue
        tw = sum(w for w, _, _ in parts)
        hour = [sum(w * v[i] for w, v, _ in parts) / tw for i in range(24)]
        lead = YT_LEAD_H[kind]
        post_hour = [hour[(i + lead) % 24] for i in range(24)]
        if own["n"] >= MIN_YT_OWN:
            dn = _norm(own["day"]); day = dn
        else:
            day = [1.0 / 7] * 7; notes.append("No weekday signal yet, all days count the same.")
        mx = max(post_hour)
        conf = "high" if own["n"] >= MIN_YT_OWN and len(parts) >= 2 else "medium" if own["n"] >= MIN_YT_OWN or online else "low"
        if traffic:
            if traffic["sensitivity"] == "low": notes.append(f"Only {traffic['subscribers_pct']}% of views come from subscribers and notifications, so the exact hour matters less than the title and the first seconds.")
            elif traffic["sensitivity"] == "high": notes.append(f"{traffic['subscribers_pct']}% of views come from subscribers and notifications, so they react in the first hours and the posting time matters.")
            if kind == "short" and traffic["shorts_pct"] >= 50: notes.append(f"{traffic['shorts_pct']}% of views come from the Shorts feed, which spreads a Short over days, so keep a steady rhythm rather than chasing one hour.")
        out["kinds"][kind] = {"empty": False, "hours": [round(100 * v / mx) for v in post_hour], "weekdays": [round(100 * v / max(day)) for v in day],
                              "slots": _yt_slots(post_hour, day, now), "notes": notes, "confidence": conf,
                              "basis": {"signals": [n for _, _, n in parts], "own_videos": own["n"], "peer_shorts": peer_n if kind == "short" else 0, "scored_on": own["used"], "lead_hours": lead,
                                        "rule": f"post {lead} hour{'s' if lead != 1 else ''} before the hour most viewers are around" if lead else "post at the hour most viewers are around"}}
    if all(k.get("empty") for k in out["kinds"].values()):
        out["empty"], out["reason"] = True, "no_signal"
    return out


def for_label_youtube(label, db_file=None):
    try: conn = db.connect(db_file, readonly=True)
    except Exception as e: return {"empty": True, "reason": "db_error", "error": str(e)[:200]}
    if conn is None: return {"empty": True, "reason": "no_database"}
    try: return analyze_youtube(conn, label)
    except Exception as e: return {"empty": True, "reason": "error", "error": str(e)[:200]}
    finally:
        try: conn.close()
        except Exception: pass


if __name__ == "__main__":
    import sys, json
    print(json.dumps(for_label(sys.argv[1] if len(sys.argv) > 1 else "music"), indent=2))
