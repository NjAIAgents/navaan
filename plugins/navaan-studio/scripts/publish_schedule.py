#!/usr/bin/env python3
"""publish_schedule.py  publish at a chosen time, from the approvals you already gave.

meta.json of an item gets  "schedule": {"youtube_at": "...Z", "instagram_at": "...Z", "created_at", "attempts", "missed", "blocked", "done"}.
  youtube_at     when the YouTube video and Short go public (step go_public), 15 minutes before the Instagram time by default
  instagram_at   when the Reel goes out (step publish_instagram), which needs the video to be public first
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


def when(m, sid):
    """ISO time an unfinished step waits for, or None."""
    s = get(m)
    if not s or s.get("done"): return None
    return s.get({"go_public": "youtube_at", "publish_instagram": "instagram_at"}.get(sid, "")) or None


def hold(m, sid, at=None):
    """The ISO time to wait for when step sid must not run yet, else None."""
    w = when(m, sid); t = parse(w)
    return w if t and (at or now()) < t and not m.get("schedule", {}).get("missed", {}).get(sid) else None


def set_schedule(slug, instagram_at, youtube_at=None, nav=None):
    import navaan as N
    m = N.meta(slug)
    if N.ig_done(m): raise ValueError("this item is already on Instagram")
    ig = parse(instagram_at)
    if not ig: raise ValueError("bad Instagram time")
    yt = parse(youtube_at) if youtube_at else ig - datetime.timedelta(minutes=YT_BEFORE_IG_MIN)
    if not yt: raise ValueError("bad YouTube time")
    n = now()
    if ig < n + datetime.timedelta(minutes=MIN_LEAD_MIN): raise ValueError("pick a time at least a few minutes ahead")
    if N.public_done(m):
        yt = n  # already public, only the Instagram time matters
    elif yt < n + datetime.timedelta(minutes=MIN_LEAD_MIN - 1):
        yt = n + datetime.timedelta(minutes=MIN_LEAD_MIN - 1)
    if not N.public_done(m) and ig < yt + datetime.timedelta(minutes=5): raise ValueError("the Instagram time must be at least 5 minutes after the YouTube time, the Reel links to the public video")
    m["schedule"] = {"youtube_at": iso(yt), "instagram_at": iso(ig), "created_at": iso(n), "attempts": {}, "missed": {}, "blocked": {}, "done": False}
    N.log_hist(m, f"publishing scheduled: YouTube {iso(yt)}, Instagram {iso(ig)}")
    N.save_meta(slug, m)
    return m["schedule"]


def suggest(slug, at=None):
    """Best times to publish this item, from the analytics, or None when there is no timing data or nothing left to schedule.
    YouTube first: the best upcoming slot for full videos (the Short goes public with it). The Reel goes at the best Instagram slot that falls 5 minutes to 12 hours
    after it, else one hour after. Without YouTube data only the Reel time is suggested and YouTube stays on auto (15 minutes before). Computed on request, never stored,
    and it approves nothing."""
    import navaan as N, besttime
    m = N.meta(slug)
    if N.ig_done(m) or m.get("cleanup"): return None
    label = C.item_type(m); n = at or now()
    ig, yt = besttime.for_label(label), besttime.for_label_youtube(label)
    igs = [(parse(x["at"]), x["score"]) for x in ig.get("slots", [])] if not ig.get("empty") else []
    yk = (yt.get("kinds") or {}).get("video") or {}
    yts = [(parse(x["at"]), x["score"]) for x in yk.get("slots", [])] if yk and not yk.get("empty") else []
    best = lambda c: max(c, key=lambda t: (t[1], -t[0].timestamp()))
    day = datetime.timedelta
    y = r = None; basis = []; conf = "medium"
    if N.public_done(m):  # already public, only the Reel time matters
        c = [t for t in igs if t[0] >= n + day(minutes=MIN_LEAD_MIN + 3)]
        if c: r = best(c)[0]; basis = ["Instagram followers online"] + (["your own Reels"] if "your own posts" in (ig.get("basis") or {}).get("signals", []) else [])
    else:
        c = [t for t in yts if t[0] >= n + day(minutes=MIN_LEAD_MIN + 1)]
        if c:
            y = best(c)[0]; conf = yk.get("confidence", "low"); basis = list((yk.get("basis") or {}).get("signals", []))
            rc = [t for t in igs if y + day(minutes=5) <= t[0] <= y + day(hours=12)]
            r = best(rc)[0] if rc else y + day(minutes=60)
        else:
            c = [t for t in igs if t[0] >= n + day(minutes=MIN_LEAD_MIN + 18)]
            if c: r = best(c)[0]; basis = ["Instagram followers online"]
    if not r: return None
    return {"youtube_at": iso(y) if y else None, "instagram_at": iso(r), "confidence": conf, "basis": basis,
            "youtube_data": bool(y), "note": "" if y else "No YouTube timing data yet, so YouTube goes public 15 minutes before the Reel."}


def accept(slug):
    """Schedule the suggested times. Gates are still yours."""
    sg = suggest(slug)
    if not sg: raise ValueError("no timing suggestion yet: collect analytics first, or pick a time yourself")
    return set_schedule(slug, sg["instagram_at"], sg["youtube_at"])


def clear(slug):
    import navaan as N
    m = N.meta(slug)
    if m.pop("schedule", None) is not None:
        N.log_hist(m, "publishing schedule cleared"); N.save_meta(slug, m)


def status_text(m):
    s = get(m)
    if not s: return ""
    if s.get("done"): return "published on schedule"
    parts = []
    for sid, key, lab in (("go_public", "youtube_at", "YouTube public"), ("publish_instagram", "instagram_at", "Instagram")):
        if s.get("missed", {}).get(sid): parts.append(f"{lab}: missed")
        else: parts.append(f"{lab} {s.get(key)}" + (f" ({s['blocked'][sid]})" if s.get("blocked", {}).get(sid) else ""))
    return "; ".join(parts)


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
        if not ready: out.append((sid, "waiting for YouTube to be public")); return
        out.append((sid, None))
    if not N.public_done(m): check("go_public", "youtube_at", ["go_public"], True)
    if not N.ig_done(m): check("publish_instagram", "instagram_at", ["publish_instagram", "instagram_caption"], N.public_done(m))
    return out


def tick(fire, skip=None, at=None):
    """Fire what is due. fire(slug, step) runs the step to the end and returns its exit code. Returns a list of what happened."""
    import navaan as N
    n = at or now(); log = []
    for p in sorted(glob.glob(os.path.join(C.songs_root(), "*"))):
        slug = os.path.basename(p)
        if slug.startswith("_") or not os.path.isdir(p): continue
        if skip and skip(slug): continue
        try: m = N.meta(slug)
        except Exception as _e: L.soft(LOG, "tick_error"); continue
        if not get(m): continue
        s = m["schedule"]; changed = False
        if N.ig_done(m) and N.public_done(m) and not s.get("done"):
            s["done"] = True; changed = True
        for sid, why in _due(N, slug, m, n):
            blk = s.setdefault("blocked", {}); att = s.setdefault("attempts", {}); ms = s.setdefault("missed", {})
            if why == "MISSED":
                ms[sid] = True; blk.pop(sid, None); changed = True; N.log_hist(m, f"scheduled step {sid} missed: more than {GRACE_H} h late"); log.append((slug, sid, "missed")); continue
            if why:
                if blk.get(sid) != why: blk[sid] = why; changed = True
                continue
            a = att.get(sid, {})
            if a.get("n", 0) >= MAX_TRIES: continue
            last = parse(a.get("last"))
            if last and n - last < datetime.timedelta(minutes=BACKOFF_MIN): continue
            blk.pop(sid, None); att[sid] = {"n": a.get("n", 0) + 1, "last": iso(n), "error": ""}
            N.save_meta(slug, m); changed = False
            FIRING.add(slug)
            try: rc = fire(slug, sid)
            except SystemExit as _e: L.ignored(LOG, "tick: SystemExit (optional or expected)", _e); rc = 1
            except Exception as e: rc = 1; print("schedule fire error:", e)
            finally: FIRING.discard(slug)
            m = N.meta(slug); s = m.get("schedule") or s; s.setdefault("attempts", {})[sid] = {"n": a.get("n", 0) + 1, "last": iso(n), "error": "" if rc == 0 else f"exit {rc}"}
            N.log_hist(m, f"scheduled step {sid} {'done' if rc == 0 else 'failed (exit ' + str(rc) + ')'}")
            if N.ig_done(m) and N.public_done(m): s["done"] = True
            m["schedule"] = s; N.save_meta(slug, m); log.append((slug, sid, rc)); break
        else:
            if changed: m["schedule"] = s; N.save_meta(slug, m)
    return log


def loop(fire, skip=None, every=60):
    while True:
        try: tick(fire, skip)
        except Exception as e: print("scheduler error:", e, flush=True)
        time.sleep(every)
