#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: the visual plan of a short (visual_plan.json): which Remotion treatment draws which beat, checked before it can reach a render.

  visuals_plan.py <slug>        check <slug>/visual_plan.json for the short's channel and print what it says; exit 1 when it is not usable
  validate(plan, channel, n)    the list of problems with a plan (empty = fine)
  load(D, channel, n)           the plan from D/visual_plan.json when it is valid, else None (the reason is logged and the short renders as it always did)

The plan:  {"beats": [{"line": 2, "treatment": "chat", "data": {...}}]}         an Aha-lorithm beat shown by a scene treatment instead of a picture
           {"caption": {"treatment": "rise", "emph": ["word"], "closing": true}}  how a narrated inspiration's spoken lines are drawn

Each channel has a profile of what it may use. Inspiration is deliberately simple: one calm caption treatment for the whole short, never a scene. The Aha-lorithm may use every scene treatment.
The treatments themselves live in remotion/src/treatments (tests keep the two lists equal). A figure on screen needs a source or the sample label; this check enforces it, so a plan cannot carry an invented statistic.
A real short (load) is stricter than a preview: the sample label is for previews only, so a figure in a published Aha-lorithm short must carry a source.

  picture_beats(plan, n)        the lines that still need a generated picture: a beat shown by a scene treatment needs none (the hook stays over its picture, and line 0 always has one: it is the thumbnail)
  auto_caption(lines, look)     the calm caption plan an inspiration gets when nobody wrote one: karaoke, rise or hero chosen from the words, or the one named by `- look:` in the brief
"""
import os, sys, json, re, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
LOG = L.get("visuals_plan")
FILE = "visual_plan.json"
CAPTIONS = ("karaoke", "rise", "hero")
PROFILES = {"inspiration": {"captions": set(CAPTIONS), "scenes": set()}, "aha": {"captions": set(), "scenes": None}}   # scenes None = every scene treatment


def _text(d, k, errs, name, longest, required=True):
    v = d.get(k)
    if v is None and not required: return
    if not isinstance(v, str) or not v.strip(): errs.append(f"{name}.{k} must be text"); return
    if len(v) > longest: errs.append(f"{name}.{k} is {len(v)} characters, the frame fits {longest}")


def _list(d, k, errs, name, lo, hi):
    v = d.get(k)
    if not isinstance(v, list) or not lo <= len(v) <= hi: errs.append(f"{name}.{k} must be a list of {lo} to {hi}"); return []
    return v


def _num(v, lo=None, hi=None):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and (lo is None or v >= lo) and (hi is None or v <= hi)


STRICT = [False]   # set by validate(strict=True): a real short never shows sample data


def _figure(d, errs, name):
    """A figure on screen has a source or says it is sample data. Anything else would be an invented statistic."""
    sourced = isinstance(d.get("source"), str) and d["source"].strip()
    if not sourced and (STRICT[0] or d.get("sample") is not True):
        errs.append(f"{name} shows a figure: give a \"source\"" + ("" if STRICT[0] else " or set \"sample\": true") + " (a number is never shown without one)")


def _panel(d, k, errs, name):
    p = d.get(k)
    if not isinstance(p, dict): errs.append(f"{name}.{k} must be {{title, text}}"); return
    _text(p, "title", errs, f"{name}.{k}", 18); _text(p, "text", errs, f"{name}.{k}", 24)


def hook(d, e): pass
def compare(d, e): _panel(d, "left", e, "compare"); _panel(d, "right", e, "compare"); _text(d, "sign", e, "compare", 3, False)


def bars(d, e):
    rows = _list(d, "rows", e, "bars", 2, 4)
    for r in rows:
        if not isinstance(r, dict) or not _num(r.get("fill"), 0, 1): e.append("bars.rows need a fill between 0 and 1"); continue
        _text(r, "label", e, "bars.rows", 30)
        if re.search(r"\d", str(r.get("label", ""))) and not d.get("source"): e.append(f"bars label {r['label']!r} has a number: bars are an illustration, add a \"source\" or take the number out")


def stat(d, e):
    if not _num(d.get("value")): e.append("stat.value must be a number")
    if d.get("from") is not None and not _num(d["from"]): e.append("stat.from must be a number")
    if d.get("decimals") is not None and not _num(d["decimals"], 0, 2): e.append("stat.decimals must be 0 to 2")
    _text(d, "label", e, "stat", 40); _text(d, "unit", e, "stat", 4, False); _figure(d, e, "stat")


def chat(d, e):
    _text(d, "question", e, "chat", 40); _text(d, "answer", e, "chat", 110)
    for t in d.get("tags") or []: _text({"t": t}, "t", e, "chat.tags", 18)
    if len(d.get("tags") or []) > 2: e.append("chat.tags holds at most 2")


def flow(d, e):
    for n in _list(d, "nodes", e, "flow", 2, 5): _text({"t": n}, "t", e, "flow.nodes", 28)


def chart(d, e):
    series = _list(d, "series", e, "chart", 1, 2); n = None
    for s in series:
        pts = s.get("points") if isinstance(s, dict) else None
        if not isinstance(pts, list) or not 3 <= len(pts) <= 8 or not all(_num(p, 0, 1) for p in pts): e.append("chart.series points are 3 to 8 values between 0 and 1"); continue
        _text(s, "label", e, "chart.series", 18)
        if n not in (None, len(pts)): e.append("chart series need the same number of points")
        n = len(pts)
    if d.get("xlabels") is not None and (not isinstance(d["xlabels"], list) or any(not isinstance(x, str) or len(x) > 4 for x in d["xlabels"])): e.append("chart.xlabels are short texts (4 characters)")
    _figure(d, e, "chart")


def checklist(d, e):
    for i in _list(d, "items", e, "checklist", 1, 5): _text({"t": i}, "t", e, "checklist.items", 28)


def timeline(d, e):
    for s in _list(d, "steps", e, "timeline", 2, 5):
        if not isinstance(s, dict): e.append("timeline.steps need {head, sub}"); continue
        _text(s, "head", e, "timeline.steps", 14); _text(s, "sub", e, "timeline.steps", 34, False)


def ring(d, e):
    if not _num(d.get("value"), 0, 100): e.append("ring.value must be 0 to 100")
    _text(d, "label", e, "ring", 28); _figure(d, e, "ring")


def strike(d, e): _text(d, "wrong", e, "strike", 10); _text(d, "right", e, "strike", 9); _text(d, "rest", e, "strike", 36, False)


SCENES = {"hook": hook, "compare": compare, "bars": bars, "stat": stat, "chat": chat, "flow": flow, "chart": chart, "checklist": checklist, "timeline": timeline, "ring": ring, "strike": strike}


def validate(plan, channel, n_lines=0, strict=False):
    """Problems with a plan for this channel (a list; empty when it is usable). n_lines: how many lines the short has (an Aha-lorithm beat names one). strict: no sample data (a real short)."""
    STRICT[0] = strict
    try: return _validate(plan, channel, n_lines)
    finally: STRICT[0] = False


def _validate(plan, channel, n_lines):
    prof = PROFILES.get(channel)
    if prof is None: return [f"{channel!r} has no visual profile (inspiration and aha do)"]
    if not isinstance(plan, dict): return ["the plan must be an object"]
    errs, beats, cap = [], plan.get("beats") or [], plan.get("caption")
    if not beats and not cap: return ["the plan has neither beats nor a caption"]
    allowed = set(SCENES) if prof["scenes"] is None else prof["scenes"]
    if not isinstance(beats, list): return ["beats must be a list"]
    seen = set()
    for b in beats:
        if not isinstance(b, dict) or b.get("treatment") not in SCENES: errs.append(f"unknown scene treatment {b.get('treatment') if isinstance(b, dict) else b!r} (known: {', '.join(SCENES)})"); continue
        t = b["treatment"]
        if t not in allowed: errs.append(f"{channel} does not use the {t} treatment"); continue
        ln = b.get("line")
        if not isinstance(ln, int) or isinstance(ln, bool) or not 0 <= ln < max(1, n_lines): errs.append(f"{t}: line {ln!r} is not one of the {n_lines} lines"); continue
        if ln in seen: errs.append(f"line {ln} has two treatments"); continue
        seen.add(ln)
        d = b.get("data") or {}
        if not isinstance(d, dict): errs.append(f"{t}: data must be an object"); continue
        SCENES[t](d, errs)
    if cap is not None:
        if not isinstance(cap, dict) or cap.get("treatment") not in CAPTIONS: errs.append(f"unknown caption treatment {cap.get('treatment') if isinstance(cap, dict) else cap!r} (known: {', '.join(CAPTIONS)})")
        elif cap["treatment"] not in prof["captions"]: errs.append(f"{channel} does not use the {cap['treatment']} caption")
        else:
            if not all(isinstance(w, str) for w in cap.get("emph") or []): errs.append("caption.emph must be a list of words")
            if cap.get("amp") is not None and not (isinstance(cap["amp"], list) and all(_num(a, 0, 1) for a in cap["amp"])): errs.append("caption.amp must be values between 0 and 1")
    return errs


def picture_beats(plan, n_lines):
    """The lines that still need a generated picture. A beat shown by a scene treatment brings its own scene, so it needs none; the hook is drawn over its picture, and line 0 always keeps one (the thumbnail)."""
    own = {b["line"] for b in (plan or {}).get("beats") or [] if b.get("treatment") != "hook"} - {0}
    return [i for i in range(n_lines) if i not in own]


def _bare(w):
    """A word without the punctuation around it (Devanagari vowel signs are marks, not letters, so they are kept)."""
    return "".join(c for c in w if not unicodedata.category(c)[0] in "PSZ")


STOP = set("the a an and or but of to in on at for with from by is are was were be been it its this that these those as not no you your we our they their i me my he she him her his them".split())


def auto_caption(lines, look="auto"):
    """The calm caption plan for a narrated inspiration, chosen from its words when `look` is auto, else the treatment the brief names (plain: none, the captions stay as Lyrics draws them).
    Few lines with a strong word in each: hero (the strong words grow). Many lines: karaoke, one at a time. Otherwise rise. A closing line is set apart when there are three or more."""
    look = (look or "auto").strip().lower()
    if look == "plain" or not [l for l in lines if str(l).strip()]: return None
    if look not in CAPTIONS:
        look = None
    emph = []
    for l in lines:
        words = [w for w in (_bare(x) for x in str(l).split()) if w.lower() not in STOP and len(w) >= 6]
        if words: emph.append(max(words, key=len))
    if look is None: look = "hero" if len(lines) <= 4 and len(emph) >= max(2, len(lines) - 1) else "karaoke" if len(lines) >= 6 else "rise"
    plan = {"treatment": look, "closing": len(lines) >= 3}
    if look == "hero": plan["emph"] = emph
    return {"caption": plan}


def load(D, channel, n_lines=0):
    p = os.path.join(D, FILE)
    if not os.path.exists(p): return None
    try:
        with open(p, encoding="utf-8") as f: plan = json.load(f)
    except (OSError, ValueError) as e:
        L.event(LOG, "warning", "visuals_unreadable", file=p, error=str(e)); print(f"warning: {FILE} is unreadable ({e}); the short is made without it", flush=True); return None
    errs = validate(plan, channel, n_lines, strict=True)
    if errs:
        L.event(LOG, "warning", "visuals_invalid", file=p, problems=errs); print(f"warning: {FILE} is not usable ({'; '.join(errs)}); the short is made without it", flush=True); return None
    return plan


def main(slug):
    D = C.song_dir(slug); channel = C.item_type(C.item_load(slug, {}))
    p = os.path.join(D, FILE)
    if not os.path.exists(p): sys.exit(f"navaan: {slug} has no {FILE}")
    with open(p, encoding="utf-8") as f: plan = json.load(f)
    q = C.load_json(os.path.join(D, "quote.json")) if os.path.exists(os.path.join(D, "quote.json")) else {}
    errs = validate(plan, channel, len(q.get("lines") or []) or 99, strict=True)
    if errs: sys.exit("navaan: " + FILE + " is not usable: " + "; ".join(errs))
    print(f"{FILE} ok for {channel}: " + ", ".join([f"line {b['line']} {b['treatment']}" for b in plan.get("beats") or []] + ([f"captions {plan['caption']['treatment']}"] if plan.get("caption") else [])))


if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    main(sys.argv[1])
