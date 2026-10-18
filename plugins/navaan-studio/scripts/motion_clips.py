#!/usr/bin/env python3
"""motion_clips.py <slug> [--force]  turn the song's pictures into short looping clips with a little real motion.

Reads songs/<slug>/motion.json (written by the motion-regions step, where the director marks what moves in each picture):
  {"pictures": {"images/pic_01.png": {"regions": {"steam": [[[x, y], ...]], "sway": [...], "flicker": [...], "foliage": [...], "water": [...], "sky": [...]}, "note": "..."}}}
and renders one loop per picture that is used in shots.json and has regions, into .cache/motion/<name>.mp4 (1920x1080, 24 fps).
shots_render.py plays the loop under the camera move instead of the still. No model and no credits: the cost is CPU.
The strength comes from Settings (motion: off, subtle, gentle). Pictures without regions stay still. A loop that fails is skipped
with a message, the still is used instead, and the step does not fail."""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import media_cfg

LOOP_SECONDS = 6
SIZE = (1920, 1080)
FPS = 24


def loop_path(D, rel):
    return os.path.join(D, ".cache", "motion", os.path.splitext(os.path.basename(rel))[0] + ".mp4")


def wanted(D):
    """The pictures that shots.json uses, in order, each once."""
    sj = C.load_json(os.path.join(D, "shots.json"), default={}) or {}
    seen, out = set(), []
    for s in sorted(sj.get("shots") or [], key=lambda s: float(s["start"])):
        if s["image"] not in seen: seen.add(s["image"]); out.append(s["image"])
    return out


def stale(D, rel, mj):
    out = loop_path(D, rel)
    return not os.path.exists(out) or os.path.getmtime(out) < max(os.path.getmtime(os.path.join(D, rel)), os.path.getmtime(mj))


def pending(D):
    """Pictures of the approved shot list that have regions but no fresh loop yet."""
    mj = os.path.join(D, "motion.json"); mo = C.load_json(mj, default=None)
    if not mo or not mo.get("pictures"): return []
    import motion_loop as M
    return [r for r in wanted(D) if M.clean_regions((mo["pictures"].get(r) or {}).get("regions")) and os.path.exists(os.path.join(D, r)) and stale(D, r, mj)]


COLORS = {"foliage": (60, 200, 60), "water": (220, 140, 40), "sky": (230, 200, 120), "sway": (60, 120, 240), "flicker": (40, 200, 240), "steam": (230, 230, 230)}


def check_or_preview(D, preview):
    """--check prints what is marked on each picture. --preview also draws the marked areas on a copy of each picture, so the director can look at them and correct the polygons."""
    import motion_loop as M
    mo = C.load_json(os.path.join(D, "motion.json"), default=None)
    if not mo or not isinstance(mo.get("pictures"), dict): sys.exit("navaan: motion.json is missing or has no pictures")
    pdir = os.path.join(D, ".cache", "motion_preview")
    if preview: os.makedirs(pdir, exist_ok=True)
    for rel, v in mo["pictures"].items():
        reg = M.clean_regions((v or {}).get("regions"))
        print("%s: %s" % (rel, ", ".join("%s x%d" % (k, len(p)) for k, p in reg.items()) or "still"))
        if preview and reg and os.path.exists(os.path.join(D, rel)):
            import cv2, numpy as np
            im = cv2.imread(os.path.join(D, rel)); H, W = im.shape[:2]; ov = im.copy()
            for kind, polys in reg.items():
                for poly in polys:
                    pts = np.round(np.array(poly, np.float32) * [W - 1, H - 1]).astype(np.int32)
                    cv2.fillPoly(ov, [pts], COLORS[kind]); cv2.polylines(im, [pts], True, COLORS[kind], 3)
                    cv2.putText(im, kind, tuple(int(x) for x in pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 1.0, COLORS[kind], 2)
            cv2.imwrite(os.path.join(pdir, os.path.splitext(os.path.basename(rel))[0] + ".jpg"), cv2.addWeighted(ov, 0.3, im, 0.7, 0))
    if preview: print("previews in .cache/motion_preview")
    return 0


def main(argv):
    if not argv or argv[0].startswith("-"): sys.exit("usage: motion_clips.py <slug> [--force | --check | --preview]")
    slug = argv[0]; D = C.song_dir(slug)
    if "--check" in argv or "--preview" in argv: return check_or_preview(D, "--preview" in argv)
    strength = media_cfg.load()["motion"]
    if strength == "off": print("motion is off in Settings, the pictures stay still."); return 0
    mj = os.path.join(D, "motion.json")
    mo = C.load_json(mj, default=None)
    if not mo or not mo.get("pictures"): print("no motion.json, the pictures stay still."); return 0
    import motion_loop as M
    made = skipped = 0
    todo = wanted(D)
    for k, rel in enumerate(todo, 1):
        C.progress(k - 1, len(todo), f"picture {k} of {len(todo)}")
        reg = M.clean_regions((mo["pictures"].get(rel) or {}).get("regions"))
        if not reg or not os.path.exists(os.path.join(D, rel)): skipped += 1; continue
        if "--force" not in argv and not stale(D, rel, mj): made += 1; continue
        out = loop_path(D, rel); os.makedirs(os.path.dirname(out), exist_ok=True); part = out + ".part.mp4"
        try:
            M.render(os.path.join(D, rel), part, reg, size=SIZE, seconds=LOOP_SECONDS, fps=FPS, strength=strength, ffmpeg=C.tool("ffmpeg"))
            os.replace(part, out); made += 1
            print("loop %s: %s" % (os.path.basename(rel), ", ".join(sorted(reg))), flush=True)
        except Exception as e:
            if os.path.exists(part): os.remove(part)
            skipped += 1; print("loop %s skipped, the still is used (%s)" % (os.path.basename(rel), str(e)[:120]))
    print("%d moving pictures, %d still" % (made, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
