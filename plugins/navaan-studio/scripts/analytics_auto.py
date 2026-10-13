#!/usr/bin/env python3
"""analytics_auto.py  refresh the analytics by itself, from the portal.

While the portal runs it checks once a minute. When the next run is due it collects Instagram, then YouTube (read only), re-runs the rule based
analysis for both and, if you ticked it, asks Claude for market research on both. The settings live in analytics_auto.json next to the songs folder:
  enabled, every_days (1, 2, 3, 7 or 14), hour (your local time, 0 to 23), ask (also run Ask Claude, uses your Claude plan)
A run missed because the portal or the computer was off starts when the portal is next open. A failed collect (for example an expired sign-in)
is written into last_note and tried again at the next due time. Needs no Claude scheduled task."""
import os, sys, json, time, datetime, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analytics_api as api
import navaan_common as C

EVERY = (1, 2, 3, 7, 14)
STATE = {"running": False, "step": "", "started": 0}
WAIT_COLLECT_S, WAIT_ASK_S = 40 * 60, 45 * 60


def path(): return os.path.join(os.path.dirname(C.songs_root()), "analytics_auto.json")
def _now(): return datetime.datetime.now(datetime.timezone.utc)
def _iso(t): return t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def _parse(s):
    try: return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc) if s else None
    except Exception: return None


def load():
    try: c = json.load(open(path(), encoding="utf-8"))
    except Exception: c = {}
    return {"enabled": bool(c.get("enabled")), "every_days": c.get("every_days") if c.get("every_days") in EVERY else 7,
            "hour": c.get("hour") if isinstance(c.get("hour"), int) and 0 <= c["hour"] <= 23 else 9, "ask": bool(c.get("ask")),
            "anchor": c.get("anchor"), "last_run": c.get("last_run"), "last_note": c.get("last_note", "")}


def _save(c):
    p = path(); tmp = p + ".tmp"
    json.dump(c, open(tmp, "w", encoding="utf-8"), indent=1); os.replace(tmp, p)


def next_due(c):
    """UTC time of the next run, or None when off. After a run: the chosen hour (local time) every_days later. First run: the next time the hour comes round."""
    if not c["enabled"]: return None
    last, anchor = _parse(c["last_run"]), _parse(c["anchor"]) or _now()
    if last:
        d = last.astimezone().date() + datetime.timedelta(days=c["every_days"])
        t = datetime.datetime.combine(d, datetime.time(c["hour"])).astimezone()
    else:
        a = anchor.astimezone()
        t = a.replace(hour=c["hour"], minute=0, second=0, microsecond=0)
        if t <= a: t += datetime.timedelta(days=1)
    return t.astimezone(datetime.timezone.utc)


def settings():
    c = load(); nd = next_due(c)
    return {"enabled": c["enabled"], "every_days": c["every_days"], "hour": c["hour"], "ask": c["ask"], "last_run": c["last_run"], "last_note": c["last_note"],
            "next_run": _iso(nd) if nd else None, "running": STATE["running"], "step": STATE["step"], "choices": list(EVERY)}


def set_settings(enabled, every_days, hour, ask):
    c = load()
    if int(every_days) not in EVERY: raise ValueError("every_days must be one of " + ", ".join(map(str, EVERY)))
    if not 0 <= int(hour) <= 23: raise ValueError("hour must be 0 to 23")
    turned_on = bool(enabled) and not c["enabled"]
    c.update(enabled=bool(enabled), every_days=int(every_days), hour=int(hour), ask=bool(ask))
    if turned_on or not c["anchor"]: c["anchor"] = _iso(_now())
    _save(c)
    return settings()


def _last_line(tail):
    lines = [l for l in (tail or "").strip().splitlines() if l.strip()]
    return lines[-1][:160] if lines else "failed"


def _wait(platform, kind, limit):
    st = api._state(platform)[0 if kind == "collect" else 1]
    t0 = time.time()
    while st["running"] and time.time() - t0 < limit: time.sleep(2)
    return st


def run_once(ask=None):
    """One refresh now. Blocks until done. Returns the note that is also saved."""
    if STATE["running"]: return "already running"
    STATE.update(running=True, started=int(time.time()), step="starting")
    notes = []
    try:
        c = load(); do_ask = c["ask"] if ask is None else ask
        for pl in ("instagram", "youtube"):
            STATE["step"] = f"collecting {pl}"
            api.start_collect("all", pl)  # False when a run is already going, we wait for that one
            st = _wait(pl, "collect", WAIT_COLLECT_S)
            if st.get("rc"): notes.append(f"{pl} collect: {_last_line(st.get('tail'))}")
        for pl in ("instagram", "youtube"):
            STATE["step"] = f"analysing {pl}"
            try: api.analyze_now("all", None, pl)
            except Exception as e: notes.append(f"{pl} analysis: {str(e)[:160]}")
        if do_ask:
            for pl in ("instagram", "youtube"):
                STATE["step"] = f"asking Claude about {pl}"
                try:
                    api.start_ask("all", pl)
                    st = _wait(pl, "ask", WAIT_ASK_S)
                    if st.get("rc"): notes.append(f"{pl} Ask Claude did not finish")
                except Exception as e: notes.append(f"{pl} Ask Claude: {str(e)[:160]}")
        note = "ok" if not notes else "; ".join(notes)
        c = load(); c.update(last_run=_iso(_now()), last_note=note); _save(c)
        return note
    finally:
        STATE.update(running=False, step="")


def tick():
    if STATE["running"]: return False
    c = load(); nd = next_due(c)
    if nd and _now() >= nd:
        threading.Thread(target=run_once, daemon=True).start(); return True
    return False


def loop(every=60):
    while True:
        try: tick()
        except Exception as e: print("analytics auto error:", e, flush=True)
        time.sleep(every)


def run_async():
    if STATE["running"]: return False
    threading.Thread(target=run_once, daemon=True).start(); return True


if __name__ == "__main__":
    print(json.dumps(settings(), indent=1))
