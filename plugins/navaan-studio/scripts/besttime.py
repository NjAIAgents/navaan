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


if __name__ == "__main__":
    import sys, json
    print(json.dumps(for_label(sys.argv[1] if len(sys.argv) > 1 else "music"), indent=2))
