"""analytics_api.py  read-only queries and the Collect now job behind the portal's Analytics page.

overview(account, days) returns one JSON-ready dict built from the analytics database that ig_collect.py fills.
start_collect(account) runs ig_collect.py in a child process so the portal never blocks and a collector exit cannot stop the server.
Nothing here writes to Instagram."""
import os, re, sys, json, subprocess, threading, time
import analytics_db as db

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECT = {"running": False, "account": None, "rc": None, "tail": "", "started": 0, "finished": 0}
ASK = {"running": False, "account": None, "rc": None, "tail": "", "started": 0, "finished": 0}
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
        return {"empty": False, "reco": reco, "peers": peers, "accounts": accounts, "account": account, "days": days, "kpis": kpis,
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
        return {"empty": False, "slug": slug, "posts": posts, "totals": tot, "unlinked": unlinked, "collect": dict(COLLECT)}
    finally:
        conn.close()


def by_song(db_file=None):
    """{slug: {posts, views, reach, saved, likes}} from the latest snapshot of every linked post. Empty dict when there is no database."""
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


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    return None if not xs else (xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2.0)


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


def recommendations(conn, uids):
    """Open, done and dismissed recommendations with the findings and market notes they cite. Empty lists when the advisor has not run."""
    marks = _in(len(uids))
    try:
        recs = db.rows(conn, f"""SELECT r.rec_id, r.source, r.priority, r.category, r.title, r.why, r.action, r.expected_effect, r.confidence, r.status, r.finding_ids, r.note_ids,
            r.created_at, r.updated_at, r.done_at, r.dismissed_reason, r.outcome_json, a.label AS account FROM recommendations r JOIN accounts a ON a.ig_user_id = r.ig_user_id
            WHERE r.ig_user_id IN ({marks}) AND r.status != 'superseded' ORDER BY r.priority, r.updated_at DESC""", uids)
        finds = {r["finding_id"]: r for r in db.rows(conn, f"SELECT finding_id, title, severity, status FROM findings WHERE ig_user_id IN ({marks})", uids)}
        notes = {r["note_id"]: r for r in db.rows(conn, "SELECT note_id, topic, summary, source_url, source_title, collected_at FROM market_notes")}
        last = db.one(conn, f"SELECT MAX(last_seen_at) AS t FROM findings WHERE ig_user_id IN ({marks})", uids)["t"]
        open_findings = db.one(conn, f"SELECT COUNT(*) AS n FROM findings WHERE ig_user_id IN ({marks}) AND status = 'open'", uids)["n"]
        fresh_notes = db.one(conn, "SELECT COUNT(*) AS n FROM market_notes")["n"]
    except Exception:
        return {"ready": False, "open": [], "done": [], "dismissed": [], "findings": 0, "notes": 0, "analyzed_at": None, "ask": dict(ASK)}
    out = {"open": [], "done": [], "dismissed": []}
    for r in recs:
        r["outcome"] = json.loads(r.pop("outcome_json") or "null")
        r["evidence"] = [{"title": finds[i]["title"], "severity": finds[i]["severity"]} for i in json.loads(r.pop("finding_ids") or "[]") if i in finds]
        r["sources"] = [{"topic": notes[i]["topic"], "summary": notes[i]["summary"], "url": notes[i]["source_url"], "title": notes[i]["source_title"]} for i in json.loads(r.pop("note_ids") or "[]") if i in notes]
        out.get(r["status"], out["open"]).append(r)
    out["done"], out["dismissed"] = out["done"][:20], out["dismissed"][:20]
    return {"ready": True, **out, "findings": open_findings, "notes": fresh_notes, "analyzed_at": last, "ask": dict(ASK)}


def analyze_now(account="all", db_file=None):
    """Run the rules in this process (fast, offline). Returns one summary line per account."""
    import ig_reco
    if not ACCOUNT_OK.match(account or ""):
        raise ValueError("bad account name")
    conn = db.connect(db_file)
    try:
        rows = ig_reco.account_rows(conn, account)
        if not rows:
            raise ValueError("no analytics data yet: press Collect now first")
        res = [dict(label=r["label"], **ig_reco.analyze(conn, r["ig_user_id"])) for r in rows]
        ig_reco.outcomes(conn)
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


def ask_prompt(account):
    scope = "both accounts" if account == "all" else f"the {account} account"
    return (f"Use the growth-advice skill of the navaan-studio plugin for {scope}. Do not run a new collect unless the data is more than a day old. "
            "You run headless: nobody can answer you, never ask a question, state any assumption and continue. Organic growth only. "
            "Never write to Instagram, never touch meta.json approvals. Store sourced market notes and at most 6 recommendations through scripts/ig_reco.py, then give a short summary.")


def start_ask(account="all"):
    """Start a headless Claude run that researches the market and writes recommendations. Returns False when one is already going."""
    import shlex
    if not ACCOUNT_OK.match(account or ""):
        raise ValueError("bad account name")
    if ASK["running"]:
        return False
    base = shlex.split(os.environ.get("NAVAAN_CLAUDE_CMD", "claude -p"))
    flags = shlex.split(os.environ["NAVAAN_CLAUDE_FLAGS"]) if "NAVAAN_CLAUDE_FLAGS" in os.environ else ["--permission-mode", "acceptEdits", "--allowedTools", ",".join(ASK_TOOLS)]
    cmd = base + [ask_prompt(account)] + flags
    ASK.update(running=True, account=account, rc=None, tail="", started=int(time.time()), finished=0)

    def work():
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, cwd=os.environ.get("NAVAAN_ROOT") or os.getcwd())
            ASK.update(rc=p.returncode, tail=((p.stdout or "") + (p.stderr or "")).strip()[-1800:])
        except FileNotFoundError:
            ASK.update(rc=127, tail="The claude command was not found. Install Claude Code, or set NAVAAN_CLAUDE_CMD.")
        except Exception as e:
            ASK.update(rc=2, tail=str(e)[:500])
        ASK.update(running=False, finished=int(time.time()))
    threading.Thread(target=work, daemon=True).start()
    return True


def start_collect(account="all"):
    """Start ig_collect.py collect in the background. Returns False when a run is already going."""
    if not ACCOUNT_OK.match(account or ""):
        raise ValueError("bad account name")
    if COLLECT["running"]:
        return False
    COLLECT.update(running=True, account=account, rc=None, tail="", started=int(time.time()), finished=0)

    def work():
        try:
            p = subprocess.run([sys.executable, os.path.join(HERE, "ig_collect.py"), "collect", "--account", account],
                               capture_output=True, text=True, timeout=1800, cwd=os.environ.get("NAVAAN_ROOT") or os.getcwd())
            COLLECT.update(rc=p.returncode, tail=((p.stdout or "") + (p.stderr or "")).strip()[-1500:])
        except Exception as e:
            COLLECT.update(rc=2, tail=str(e)[:500])
        COLLECT.update(running=False, finished=int(time.time()))
    threading.Thread(target=work, daemon=True).start()
    return True
