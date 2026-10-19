#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: the edit decision list (edl.json) of a reel: what the reel-director skill proposes and reel_render.py executes. Checked here, before anything is rendered, so a bad plan fails loudly and early.

  reel_edl.py <slug>        check edl.json against the footage, write edl_report.json and edl_summary.md (what the human reads at the edit_plan approval)

validate(edl, source_seconds) returns a cleaned copy (defaults filled, numbers clamped) or raises ValueError listing every problem.
Times in `segments` are seconds of the source footage; times in `text`, `quote` and `audio.vo_start` are seconds of the finished reel, which starts with the optional intro (the first frame held) and ends with the optional end card (the last frame held, dimmed, with the account handle and the music credit).
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

W, H, FPS = 1080, 1920, 30
MIN_OUT, MAX_OUT = 3.0, 90.0
LOOKS = ("natural", "warm", "cool", "cinematic", "vivid", "mono")
POLICIES = ("keep", "ambient_low", "denoise", "mute")   # what happens to the sound the footage came with
POS = ("top", "mid", "low")


def _num(v, name, errs, lo, hi, default=None):
    if v is None:
        return default
    try:
        x = float(v)
    except (TypeError, ValueError):   # expected: not a number; it is reported in the list of problems, which validate() raises as one error
        errs.append(f"{name} is not a number: {v!r}"); return default
    if x != x or x < lo or x > hi:
        errs.append(f"{name} {x} is outside {lo} to {hi}"); return default
    return x


def validate(edl, source_seconds):
    errs = []
    if not isinstance(edl, dict): raise ValueError("edl.json must be a JSON object")
    out = {"version": 1}
    # --- segments: which parts of the footage are kept, in play order
    segs = edl.get("segments")
    clean = []
    if not isinstance(segs, list) or not segs: errs.append("segments must be a non-empty list")
    else:
        for i, s in enumerate(segs):
            n = f"segments[{i}]"
            if not isinstance(s, dict): errs.append(n + " must be an object"); continue
            st = _num(s.get("start"), n + ".start", errs, 0, max(0.0, source_seconds))
            en = _num(s.get("end"), n + ".end", errs, 0, source_seconds + 0.25)
            if st is None or en is None: errs.append(n + " needs start and end"); continue
            en = min(en, source_seconds)
            if en - st < 0.4: errs.append(f"{n} is shorter than 0.4 s ({st} to {en})"); continue
            z = _num(s.get("zoom"), n + ".zoom", errs, 1.0, 1.6, 1.0)
            clean.append({"start": round(st, 3), "end": round(en, 3), "crop_x": _num(s.get("crop_x"), n + ".crop_x", errs, 0, 1, 0.5),
                          "crop_y": _num(s.get("crop_y"), n + ".crop_y", errs, 0, 1, 0.5), "zoom": z, "zoom_to": _num(s.get("zoom_to"), n + ".zoom_to", errs, 1.0, 1.6, z)})
        by_start = sorted(enumerate(clean), key=lambda p: p[1]["start"])
        for (ia, a), (ib, b) in zip(by_start, by_start[1:]):
            if b["start"] < a["end"] - 0.01: errs.append(f"segments[{ia}] and segments[{ib}] overlap in the footage ({a['start']}-{a['end']} and {b['start']}-{b['end']})")
    content = round(sum(s["end"] - s["start"] for s in clean), 3)
    # --- intro and end card: the first and last frame held, so a short clip can carry a hook line and a credit
    iv = edl.get("intro") if isinstance(edl.get("intro"), dict) else {}
    ov = edl.get("outro") if isinstance(edl.get("outro"), dict) else {}
    intro_s = _num(iv.get("seconds"), "intro.seconds", errs, 0, 3, 0.0)
    outro = {"seconds": _num(ov.get("seconds"), "outro.seconds", errs, 0, 6, 0.0), "handle": bool(ov.get("handle", True)), "credit": bool(ov.get("credit", True))}
    total = round(intro_s + content + outro["seconds"], 3)
    if clean and not (MIN_OUT <= total <= MAX_OUT): errs.append(f"the reel would be {total} s; it must be {MIN_OUT} to {MAX_OUT} s")
    out["segments"], out["seconds"], out["content_seconds"], out["intro"], out["outro"] = clean, total, content, {"seconds": intro_s}, outro
    # --- grade
    g = edl.get("grade") if isinstance(edl.get("grade"), dict) else {}
    look = str(g.get("look") or "natural").lower()
    if look not in LOOKS: errs.append(f"grade.look {look!r} is not one of {', '.join(LOOKS)}"); look = "natural"
    out["grade"] = {"look": look, "brightness": _num(g.get("brightness"), "grade.brightness", errs, -0.3, 0.3, 0.0), "contrast": _num(g.get("contrast"), "grade.contrast", errs, 0.7, 1.5, 1.0),
                    "saturation": _num(g.get("saturation"), "grade.saturation", errs, 0.0, 1.8, 1.0), "gamma": _num(g.get("gamma"), "grade.gamma", errs, 0.7, 1.4, 1.0), "vignette": bool(g.get("vignette", False))}
    out["stabilize"] = bool(edl.get("stabilize", False))
    # --- audio
    a = edl.get("audio") if isinstance(edl.get("audio"), dict) else {}
    pol = str(a.get("policy") or "ambient_low").lower()
    if pol not in POLICIES: errs.append(f"audio.policy {pol!r} is not one of {', '.join(POLICIES)}"); pol = "ambient_low"
    mu = a.get("music")
    music = None
    if isinstance(mu, dict) and (mu.get("file") or mu.get("slug")):
        f = str(mu.get("file") or "")
        if f != os.path.basename(f) or not f: errs.append("audio.music.file must be a file name, not a path")
        music = {"slug": str(mu.get("slug") or ""), "file": f, "start": _num(mu.get("start"), "audio.music.start", errs, 0, 36000, 0.0), "level": _num(mu.get("level"), "audio.music.level", errs, 0, 1, 0.35),
                 "fade_in": _num(mu.get("fade_in"), "audio.music.fade_in", errs, 0, 10, 1.0), "fade_out": _num(mu.get("fade_out"), "audio.music.fade_out", errs, 0, 10, 1.5)}
    out["audio"] = {"policy": pol, "ambient_level": _num(a.get("ambient_level"), "audio.ambient_level", errs, 0, 1, 0.3), "voice_level": _num(a.get("voice_level"), "audio.voice_level", errs, 0, 1.5, 1.0),
                    "vo_start": _num(a.get("vo_start"), "audio.vo_start", errs, 0, 8, round(intro_s + 0.4, 2)), "music": music}   # the voice starts after the intro unless the plan says otherwise
    # --- text on screen (reel time) and where the quote goes
    texts = []
    for i, t in enumerate(edl.get("text") or []):
        n = f"text[{i}]"
        if not isinstance(t, dict) or not str(t.get("text") or "").strip(): errs.append(n + " needs text"); continue
        if len(str(t["text"])) > 120: errs.append(n + " is over 120 characters")
        st = _num(t.get("start"), n + ".start", errs, 0, MAX_OUT, 0.0); en = _num(t.get("end"), n + ".end", errs, 0, MAX_OUT, None)
        if en is None or st is None or en <= st: errs.append(n + " needs start < end"); continue
        if total and en > total + 0.05: errs.append(f"{n} ends at {en}, after the reel ({total} s)"); continue
        pos = str(t.get("pos") or "mid")
        if pos not in POS: errs.append(f"{n}.pos {pos!r} is not one of {', '.join(POS)}"); pos = "mid"
        texts.append({"text": str(t["text"]).strip(), "start": st, "end": en, "pos": pos})
    if len(texts) > 6: errs.append("at most 6 text items")
    out["text"] = texts
    q = edl.get("quote") if isinstance(edl.get("quote"), dict) else {}
    qpos = str(q.get("pos") or "mid")
    if qpos not in POS: errs.append(f"quote.pos {qpos!r} is not one of {', '.join(POS)}"); qpos = "mid"
    out["quote"] = {"start": _num(q.get("start"), "quote.start", errs, 0, MAX_OUT, round(intro_s + 1.0, 2)), "pos": qpos, "font": "sans" if str(q.get("font")) == "sans" else "serif",
                    "show": bool(q.get("show", True))}   # show false: the footage already carries the words, so the voice speaks them and they are not drawn again
    out["thumb_t"] = _num(edl.get("thumb_t"), "thumb_t", errs, 0, MAX_OUT, round(min(1.5, total / 2), 2))
    if errs: raise ValueError("; ".join(errs))
    return out


def summary(edl, src_probe=None, note=""):
    """The plain-words plan a person reads before approving it."""
    L = [f"# Edit plan: {edl['seconds']:.1f} s reel from the footage" + (f" ({src_probe.get('duration', 0):.0f} s, {src_probe.get('width')}x{src_probe.get('height')})" if src_probe else ""), ""]
    t = edl["intro"]["seconds"]
    if t: L += [f"Intro: the first frame is held for {t:.1f} s (reel 0.0-{t:.1f} s)", ""]
    for i, s in enumerate(edl["segments"]):
        d = s["end"] - s["start"]
        zoom = f", zoom {s['zoom']:.2f} to {s['zoom_to']:.2f}" if s["zoom_to"] != 1.0 or s["zoom"] != 1.0 else ""
        L.append(f"{i + 1}. footage {s['start']:.1f}-{s['end']:.1f} s  ->  reel {t:.1f}-{t + d:.1f} s  (frame centre {s['crop_x']:.2f},{s['crop_y']:.2f}{zoom})"); t += d
    if edl["outro"]["seconds"]: L.append(f"End card: the last frame is held for {edl['outro']['seconds']:.1f} s (reel {t:.1f}-{t + edl['outro']['seconds']:.1f} s), dimmed, with " + " and ".join(x for x, on in (("the account handle", edl["outro"]["handle"]), ("the music credit", edl["outro"]["credit"])) if on or False) + ".")
    g = edl["grade"]
    L += ["", f"Look: {g['look']} (brightness {g['brightness']:+.2f}, contrast {g['contrast']:.2f}, saturation {g['saturation']:.2f}{', vignette' if g['vignette'] else ''}){'; stabilised' if edl['stabilize'] else ''}"]
    a = edl["audio"]; m = a["music"]
    L.append(f"Footage sound: {a['policy']}" + (f" (level {a['ambient_level']:.2f})" if a["policy"] in ("ambient_low", "denoise") else ""))
    L.append(f"Music: {m['slug'] + '/' if m['slug'] else ''}{m['file']} from {m['start']:.0f} s at level {m['level']:.2f}" if m else "Music: none")
    for x in edl["text"]: L.append(f"On-screen text {x['start']:.1f}-{x['end']:.1f} s ({x['pos']}): {x['text']}")
    L.append(f"The quote appears from {edl['quote']['start']:.1f} s ({edl['quote']['pos']})." if edl["quote"]["show"] else "The quote is spoken but not drawn: the footage already shows it.")
    if note: L += ["", note]
    return "\n".join(L) + "\n"


def main(slug):
    D = C.song_dir(slug)
    pr = C.load_json(os.path.join(D, "probe.json"), default=None) or {}
    if not pr.get("duration"): sys.exit("navaan: probe.json is missing. Run the ingest step first.")
    raw = C.load_json(os.path.join(D, "edl.json"), default=None)
    if raw is None: sys.exit("navaan: edl.json is missing. Run the direct step first.")
    try:
        edl = validate(raw, float(pr["duration"]))
    except ValueError as e:
        json.dump({"ok": False, "errors": str(e).split("; ")}, open(os.path.join(D, "edl_report.json"), "w"), indent=2)
        sys.exit("navaan: edl.json is not usable: " + str(e))
    json.dump({"ok": True, "seconds": edl["seconds"], "segments": len(edl["segments"])}, open(os.path.join(D, "edl_report.json"), "w"), indent=2)
    with open(os.path.join(D, "edl_summary.md"), "w", encoding="utf-8") as f: f.write(summary(edl, pr))
    print(f"edl ok: {len(edl['segments'])} segments, {edl['seconds']:.1f} s")


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
