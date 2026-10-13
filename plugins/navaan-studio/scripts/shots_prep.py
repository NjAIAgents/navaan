#!/usr/bin/env python3
"""shots_prep.py <slug> [--draft]

Builds what the director needs from the lyrics: sections with estimated start and end times, the song length, the pictures
and the user's camera and scene overrides. Writes shots_context.json. With --draft it also writes a first shots.json
(one shot per lyric section, pictures and camera moves assigned in turn); the director skill then improves that draft by looking at the pictures.

Timing comes from caption_cues.json when the song has it, otherwise the lyric lines are spread over the song by line count.
It is only an estimate. The user checks and edits the times when approving the shot list.
shots.json: {"duration": s, "shots": [{"id", "label", "start", "end", "image", "camera", "focus": [x, y], "scene", "lyric"}], "notes": ""}
camera: push_in, pull_out, pan_left, pan_right, tilt_up, tilt_down, drift, hold"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import visuals_cfg as V

CAMERAS = ("push_in", "pull_out", "pan_left", "pan_right", "tilt_up", "tilt_down", "drift", "hold")
CYCLE = ("push_in", "pan_right", "pull_out", "drift", "pan_left", "push_in", "tilt_up", "pull_out")
MIN_SHOT = 6.0
MAX_SHOT = 22.0


def sections(text):
    """[(label, [lines])] from lyrics with [Verse 1] style headers. Text before any header becomes an Intro."""
    out, cur = [], None
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln: continue
        m = re.match(r"^\[(.+?)\]$|^\((.+?)\)$", ln) if (ln.startswith("[") or ln.startswith("(")) and len(ln) < 40 else None
        plain = re.match(r"^(intro|verse|chorus|pre-?chorus|hook|bridge|rap|refrain|interlude|outro|instrumental|break|drop)\b[\s\d:.-]*$", ln, re.I)
        if m or plain:
            cur = [(m.group(1) or m.group(2)) if m else ln.rstrip(":. "), []]; out.append(cur); continue
        if cur is None: cur = ["Intro", []]; out.append(cur)
        cur[1].append(ln)
    return [(l, ls) for l, ls in out if ls]


def build_context(D):
    mp3 = next((os.path.join(D, n) for n in ("final.mp3", "final_tagged.mp3") if os.path.exists(os.path.join(D, n))), None)
    if not mp3: sys.exit("navaan: final.mp3 is missing")
    dur = round(C.duration(mp3), 2)
    lt = open(os.path.join(D, "lyrics.txt"), encoding="utf-8").read() if os.path.exists(os.path.join(D, "lyrics.txt")) else ""
    secs = sections(lt) or [("Song", ["(instrumental)"])]
    total = sum(len(ls) for _, ls in secs)
    cues = C.load_json(os.path.join(D, "caption_cues.json"), default=[]) or []
    out, acc = [], 0
    for label, ls in secs:
        a, b = acc, acc + len(ls); acc = b
        if cues:
            ia = min(len(cues) - 1, int(a * len(cues) / total)); ib = min(len(cues), max(ia + 1, int(round(b * len(cues) / total))))
            st = float(cues[ia][0]); en = float(cues[ib - 1][1])
        else:
            st, en = dur * a / total, dur * b / total
        out.append({"label": label, "lines": ls, "start": st, "end": en})
    # sections tile the song: the first starts at 0, each ends where the next one starts, the last ends at the song end
    starts = [0.0] + [s["start"] for s in out[1:]]
    for i, s in enumerate(out):
        s["start"] = starts[i]
        s["end"] = starts[i + 1] if i + 1 < len(out) else dur
    for s in out: s["start"], s["end"] = round(s["start"], 2), round(s["end"], 2)
    v = V.load(D)
    imgs = []
    for rel in V.own_images(D):
        w = h = None
        try:
            import subprocess
            j = json.loads(subprocess.check_output([C.tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", os.path.join(D, rel)]))
            w, h = j["streams"][0]["width"], j["streams"][0]["height"]
        except Exception: pass
        imgs.append({"file": rel, "width": w, "height": h})
    return {"duration": dur, "sections": out, "images": imgs, "layout": v.get("layout", "video"), "camera_override": v.get("camera", ""), "scene_override": v.get("scene", ""),
            "title": (open(os.path.join(D, "title.txt"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(D, "title.txt")) else ""),
            "style": (open(os.path.join(D, "style.txt"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(D, "style.txt")) else ""),
            "cameras": list(CAMERAS), "timing_source": "caption_cues.json" if cues else "estimated from line counts"}


def draft(ctx):
    imgs = [i["file"] for i in ctx["images"]]
    if not imgs: sys.exit("navaan: no pictures in images/")
    shots = [dict(label=s["label"], start=s["start"], end=s["end"], lyric=" / ".join(s["lines"][:2])) for s in ctx["sections"]]
    # split long shots, and add shots until every picture can appear at least once (each shot stays at least MIN_SHOT long)
    def longest(): return max(range(len(shots)), key=lambda i: shots[i]["end"] - shots[i]["start"])
    while True:
        i = longest(); L = shots[i]["end"] - shots[i]["start"]
        if (L > MAX_SHOT or len(shots) < len(imgs)) and L / 2 >= MIN_SHOT:
            mid = round(shots[i]["start"] + L / 2, 2); a = dict(shots[i], end=mid); b = dict(shots[i], start=mid)
            shots[i:i + 1] = [a, b]
        else: break
    out = []
    for k, s in enumerate(shots):
        out.append({"id": k + 1, "label": s["label"], "start": round(s["start"], 2), "end": round(s["end"], 2), "image": imgs[k % len(imgs)],
                    "camera": CYCLE[k % len(CYCLE)], "focus": [0.5, 0.5], "scene": "", "lyric": s["lyric"]})
    return {"duration": ctx["duration"], "shots": out, "notes": "first draft: one shot per lyric section, pictures and moves assigned in turn"}


def main(a):
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    D = C.song_dir(a[0]); ctx = build_context(D)
    json.dump(ctx, open(os.path.join(D, "shots_context.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"shots_context.json: {len(ctx['sections'])} sections, {len(ctx['images'])} pictures, {ctx['duration']} s ({ctx['timing_source']})")
    if "--draft" in a:
        d = draft(ctx)
        json.dump(d, open(os.path.join(D, "shots.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False); open(os.path.join(D, "shots.json"), "a").write("\n")
        print(f"shots.json draft: {len(d['shots'])} shots")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
