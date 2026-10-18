#!/usr/bin/env python3
"""publish_schedule.py  publish at a chosen time, from the approvals you already gave.

meta.json of an item gets  "schedule": {"youtube_at": "...Z", "instagram_at": "...Z", "created_at", "attempts", "missed", "blocked", "done"}.
  youtube_at     when the YouTube video and Short go public (step go_public), or None: YouTube is not scheduled and stays manual
  instagram_at   when the Reel goes out (step publish_instagram), or None: Instagram is not scheduled and stays manual. The two platforms are independent: neither waits for the other
Scheduling never approves anything. The gates go_public, instagram_caption and publish_instagram are still yours: approve them before the time.
At the time, the scheduler runs the step only if its gates are approved. If a gate is missing it waits and shows "waiting for approval", and
fires on the next check once you approve, up to 12 hours late. After that the slot is marked missed and you pick a new time.
Until its time, `navaan.py run` and the pipeline stop at those two steps ("scheduled").

The portal checks every minute while it runs. Without the portal: `navaan.py schedule-run --loop` (keep the computer awake) or run `navaan.py schedule-run` from cron.
YouTube and Instagram are both published through their APIs from this computer, so it must be on and online at the time.
"""
import os, sys, json, time, datetime, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
LOG = L.get("publish_schedule")

UTC = datetime.timezone.utc
GRACE_H = 12
MAX_TRIES = 3
BACKOFF_MIN = 10
MIN_LEAD_MIN = 2
YT_BEFORE_IG_MIN = 15
FIRING = set()  # items being fired by the scheduler right now, so navaan.run lets those steps through


def now(): return datetime.datetime.now(UTC)
def iso(t): return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s):
    if not s: return None
    try: return datetime.datetime.strptime(str(s), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError as _e:
        L.ignored(LOG, "parse: ValueError (optional or expected)", _e)
        try: return datetime.datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(UTC)
        except ValueError as _e: L.ignored(LOG, "parse: ValueError (optional or expected)", _e); return None


def get(m): return (m or {}).get("schedule") or None


CENTRAL = "America/Chicago"   # the owner's clock: a time typed in the new-item form is US Central (CST or CDT, whichever is in force that day)


def from_central(text):
    """'YYYY-MM-DDTHH:MM' read as US Central time -> ISO UTC ('...Z'). ValueError with a sentence for a bad or past time."""
    from zoneinfo import ZoneInfo
    try: local = datetime.datetime.strptime(str(text or "").strip()[:16], "%Y-%m-%dT%H:%M")
    except ValueError: raise ValueError("pick a publishing date and time") from None
    t = local.replace(tzinfo=ZoneInfo(CENTRAL)).astimezone(UTC)
    if t < now() + datetime.timedelta(minutes=MIN_LEAD_MIN): raise ValueError("pick a publishing time in the future (Central Time)")
    return iso(t)


def when(m, sid):
    """ISO time an unfinished step waits for, or None."""
    s = get(m)
    if not s or s.get("done"): return None
    return s.get({"go_public": "youtube_at", "publish_instagram": "instagram_at"}.get(sid, "")) or None


def hold(m, sid, at=None):
    """The ISO time to wait for when step sid must not run yet, else None."""
    w = when(m, sid); t = parse(w)
    return w if t and (at or now()) < t and not m.get("schedule", {}).get("missed", {}).get(sid) else None


def set_schedule(slug, instagram_at=None, youtube_at=None, nav=None):
    """Schedule YouTube, Instagram or both, each on its own: a platform without a time stays manual, and neither waits for the other. A platform already posted is not scheduled again.
    ValueError with a sentence for a bad time, a time too close, or when there is nothing to schedule."""
    import navaan as N
    m = N.meta(slug)
    ig = parse(instagram_at) if instagram_at else None; yt = parse(youtube_at) if youtube_at else None
    if instagram_at and not ig: raise ValueError("bad Instagram time")
    if youtube_at and not yt: raise ValueError("bad YouTube time")
    if ig and N.ig_done(m) and not yt: raise ValueError("this item is already on Instagram")
    if N.ig_done(m): ig = None
    if N.public_done(m): yt = None   # already public: only the Instagram time, if there is one, matters
    if not ig and not yt: raise ValueError("pick a time for YouTube, for Instagram, or for both")
    n = now()
    for t in (ig, yt):
        if t and t < n + datetime.timedelta(minutes=MIN_LEAD_MIN): raise ValueError("pick a time at least a few minutes ahead")
    sched = {"youtube_at": iso(yt) if yt else None, "instagram_at": iso(ig) if ig else None, "created_at": iso(n), "attempts": {}, "missed": {}, "blocked": {}, "done": False}
    def put(d):
        d["schedule"] = sched
        N.log_hist(d, "publishing scheduled: " + "; ".join(x for x in (f"YouTube {iso(yt)}" if yt else "", f"Instagram {iso(ig)}" if ig else "") if x))
    N.edit_meta(slug, put)
    return sched


def suggest(slug, at=None):
    """Best times to publish this item, from the analytics, or None when there is no timing data or nothing left to schedule. YouTube and Instagram are separate: each gets the best upcoming slot
    of its own (the Short goes public with the video), and a platform with no timing data, or one already posted, gets no time and stays manual. Computed on request, never stored,
    and it approves nothing."""
    import navaan as N, besttime
    m = N.meta(slug)
    if m.get("cleanup") or (N.ig_done(m) and N.public_done(m)): return None   # nothing left to schedule (one platform may still be, and then only it is suggested)
    label = C.item_type(m); n = at or now()
    ig, yt = besttime.for_label(label), besttime.for_label_youtube(label)
    igs = [(parse(x["at"]), x["score"]) for x in ig.get("slots", [])] if not ig.get("empty") else []
    yk = (yt.get("kinds") or {}).get("video") or {}
    yts = [(parse(x["at"]), x["score"]) for x in yk.get("slots", [])] if yk and not yk.get("empty") else []
    best = lambda c: max(c, key=lambda t: (t[1], -t[0].timestamp()))
    day = datetime.timedelta
    y = r = None; basis = []; conf = "medium"
    if not N.public_done(m):
        c = [t for t in yts if t[0] >= n + day(minutes=MIN_LEAD_MIN + 1)]
        if c: y = best(c)[0]; conf = yk.get("confidence", "low"); basis = list((yk.get("basis") or {}).get("signals", []))
    if not N.ig_done(m):
        c = [t for t in igs if t[0] >= n + day(minutes=MIN_LEAD_MIN + 3)]
        if c: r = best(c)[0]; basis += ["Instagram followers online"] + (["your own Reels"] if "your own posts" in (ig.get("basis") or {}).get("signals", []) else [])
    if not r and not y: return None
    note = " ".join(x for x in ("No YouTube timing data yet, so YouTube is left for you to publish." if not y and not N.public_done(m) else "", "No Instagram timing data yet, so the Reel is left for you to post." if not r and not N.ig_done(m) else "") if x)
    return {"youtube_at": iso(y) if y else None, "instagram_at": iso(r) if r else None, "confidence": conf, "basis": basis, "youtube_data": bool(y), "note": note}


def accept(slug):
    """Schedule the suggested times. Gates are still yours."""
    sg = suggest(slug)
    if not sg: raise ValueError("no timing suggestion yet: collect analytics first, or pick a time yourself")
    return set_schedule(slug, sg["instagram_at"], sg["youtube_at"])   # either may be None: that platform stays manual


def clear(slug):
    import navaan as N
    def drop(d):
        if d.pop("schedule", None) is not None: N.log_hist(d, "publishing schedule cleared")
    N.edit_meta(slug, drop)


def status_text(m):
    s = get(m)
    if not s: return ""
    if s.get("done"): return "published on schedule"
    parts = []
    for sid, key, lab in (("go_public", "youtube_at", "YouTube public"), ("publish_instagram", "instagram_at", "Instagram")):
        if not s.get(key): continue   # not scheduled: left for you
        if s.get("missed", {}).get(sid): parts.append(f"{lab}: missed")
        else: parts.append(f"{lab} {s.get(key)}" + (f" ({s['blocked'][sid]})" if s.get("blocked", {}).get(sid) else ""))
    return "; ".join(parts)


def entries(slug, m, title=""):
    """One row per publish step of a scheduled item, for the calendar and the list: {slug, title, type, platform, at, state, reason}.
    state is done, missed, blocked (reason says why) or scheduled."""
    import navaan as N
    s = get(m)
    if not s: return []
    out = []
    for sid, key, plat, done in (("go_public", "youtube_at", "YouTube", N.public_done(m)), ("publish_instagram", "instagram_at", "Instagram", N.ig_done(m))):
        at = s.get(key)
        if not at: continue
        blocked = (s.get("blocked") or {}).get(sid) or ""
        state = "done" if (s.get("done") or done) else "missed" if (s.get("missed") or {}).get(sid) else "blocked" if blocked else "scheduled"
        out.append({"slug": slug, "title": title, "type": C.item_type(m), "platform": plat, "at": at, "state": state, "reason": blocked if state == "blocked" else ""})
    return out


def _due(N, slug, m, n):
    """Steps of this item that are due now: [(step_id, reason_if_blocked_or_None)]."""
    s = get(m); out = []
    if not s or s.get("done"): return out
    D = C.song_dir(slug); ap = m.get("approvals", {})
    def check(sid, key, gates, ready):
        t = parse(s.get(key))
        if not t or n < t or s.get("missed", {}).get(sid): return
        if (n - t) > datetime.timedelta(hours=GRACE_H): out.append((sid, "MISSED")); return
        for g in gates:
            if not N.gate_ok(D, ap, g, N.ig_done(m)): out.append((sid, f"waiting for approval: {g}")); return
        out.append((sid, None))
    if not N.public_done(m): check("go_public", "youtube_at", ["go_public"], True)
    if not N.ig_done(m): check("publish_instagram", "instagram_at", ["publish_instagram", "instagram_caption"], True)   # the Reel does not wait for YouTube
    return out


def tick(fire, skip=None, at=None):
    """Fire what is due. fire(slug, step) runs the step to the end and returns its exit code. Returns a list of what happened.
    A step is claimed under the item's row lock (it counts the attempt before it runs), so two schedulers, or a tick and a retry, can never both run it."""
    import navaan as N
    n = at or now(); log = []
    for p in sorted(glob.glob(os.path.join(C.songs_root(), "*"))):
        slug = os.path.basename(p)
        if slug.startswith("_") or not os.path.isdir(p): continue
        if skip and skip(slug): continue
        try: m = N.meta(slug)
        except Exception as _e: L.soft(LOG, "tick_error"); continue
        if not get(m): continue
        sc0 = m["schedule"]
        if (not sc0.get("instagram_at") or N.ig_done(m)) and (not sc0.get("youtube_at") or N.public_done(m)) and not sc0.get("done"):   # every platform that was scheduled is posted
            N.edit_meta(slug, lambda d: d["schedule"].__setitem__("done", True)); m = N.meta(slug)
        s = m["schedule"]
        for sid, why in _due(N, slug, m, n):
            if why == "MISSED":
                def miss(d, sid=sid):
                    sc = d["schedule"]; sc.setdefault("missed", {})[sid] = True; sc.setdefault("blocked", {}).pop(sid, None)
                    N.log_hist(d, f"scheduled step {sid} missed: more than {GRACE_H} h late")
                N.edit_meta(slug, miss); log.append((slug, sid, "missed")); continue
            if why:
                if (s.get("blocked") or {}).get(sid) != why: N.edit_meta(slug, lambda d, sid=sid, why=why: d["schedule"].setdefault("blocked", {}).__setitem__(sid, why))
                continue
            won = []
            def claim(d, sid=sid):
                sc = d.get("schedule") or {}
                a = (sc.get("attempts") or {}).get(sid, {})
                if sc.get("done") or (sc.get("missed") or {}).get(sid) or a.get("n", 0) >= MAX_TRIES: return
                last = parse(a.get("last"))
                if last and n - last < datetime.timedelta(minutes=BACKOFF_MIN): return
                sc.setdefault("blocked", {}).pop(sid, None); sc.setdefault("attempts", {})[sid] = {"n": a.get("n", 0) + 1, "last": iso(n), "error": ""}
                d["schedule"] = sc; won.append(a.get("n", 0))
            N.edit_meta(slug, claim)
            if not won: continue   # already claimed by another run, too soon after the last try, or out of tries
            FIRING.add(slug)
            try: rc = fire(slug, sid)
            except SystemExit as _e: L.ignored(LOG, "tick: SystemExit (optional or expected)", _e); rc = 1
            except Exception as e: rc = 1; print("schedule fire error:", e)
            finally: FIRING.discard(slug)
            def record(d, sid=sid, rc=rc, prev=won[0]):
                sc = d.get("schedule") or s; sc.setdefault("attempts", {})[sid] = {"n": prev + 1, "last": iso(n), "error": "" if rc == 0 else f"exit {rc}"}
                N.log_hist(d, f"scheduled step {sid} {'done' if rc == 0 else 'failed (exit ' + str(rc) + ')'}")
                if N.ig_done(d) and N.public_done(d): sc["done"] = True
                d["schedule"] = sc
            N.edit_meta(slug, record); log.append((slug, sid, rc)); break
    return log


def loop(fire, skip=None, every=60):
    while True:
        try: tick(fire, skip)
        except Exception as e: print("scheduler error:", e, flush=True)
        time.sleep(every)
