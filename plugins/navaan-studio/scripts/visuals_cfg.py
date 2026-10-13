#!/usr/bin/env python3
"""visuals_cfg.py  the visuals choice for a music item: its own pictures (default) or Google Flow clips.

songs/<slug>/visuals.json
  {"mode": "own" | "flow",
   "layout": "static" | "video",     own pictures only. static = one cover picture held for the whole song, video = 4 or more pictures stitched by the director's shot list
   "images": ["images/cover.jpg", ...],
   "camera": "",                      optional override for the camera style ("slow pushes, handheld feel")
   "scene": ""}                       optional override for the look of the scenes ("monsoon night, warm lamps")

CLI:  visuals_cfg.py <slug> --mode own|flow [--layout static|video]     (the portal normally writes the file)
      visuals_cfg.py <slug> --check                                      print what is missing
The pictures live in songs/<slug>/images/. The portal uploads them there; from a terminal just copy them in."""
import os, sys, json, re, base64
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp")
MIN_VIDEO = 4
MAX_IMAGES = 24
MAX_BYTES = 25 * 1024 * 1024


def vpath(D): return os.path.join(D, "visuals.json")


def load(D): return C.load_json(vpath(D), default={}) or {}


def own_images(D):
    d = os.path.join(D, "images")
    return sorted(f"images/{f}" for f in os.listdir(d) if f.lower().endswith(IMG_EXT) and not f.startswith(".")) if os.path.isdir(d) else []


def safe_name(name):
    base = os.path.basename(str(name or "")).strip()
    stem, ext = os.path.splitext(base)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_")[:60] or "image"
    ext = ext.lower()
    if ext not in IMG_EXT: raise ValueError("pictures must be jpg, png or webp")
    return stem + ext


def add_image(D, name, data_b64):
    """Save one uploaded picture (base64 body) into images/. Returns its relative path."""
    raw = base64.b64decode(data_b64.split(",", 1)[-1])
    if len(raw) > MAX_BYTES: raise ValueError("picture is over 25 MB")
    if len(own_images(D)) >= MAX_IMAGES: raise ValueError(f"at most {MAX_IMAGES} pictures")
    os.makedirs(os.path.join(D, "images"), exist_ok=True)
    fn = safe_name(name); p = os.path.join(D, "images", fn); n = 1
    while os.path.exists(p):
        stem, ext = os.path.splitext(fn); p = os.path.join(D, "images", f"{stem}_{n}{ext}"); n += 1
    open(p, "wb").write(raw)
    return "images/" + os.path.basename(p)


def remove_image(D, rel):
    rel = str(rel)
    if rel not in own_images(D): raise ValueError("no such picture")
    os.remove(os.path.join(D, rel))


def problems(D, v=None):
    """What is missing before the visuals can be built. Empty list when ready."""
    v = v or load(D)
    if v.get("mode") != "own": return []
    imgs = own_images(D)
    need = 1 if v.get("layout") == "static" else MIN_VIDEO
    out = []
    if len(imgs) < need: out.append(f"{'a cover picture' if need == 1 else f'at least {MIN_VIDEO} pictures'} needed, {len(imgs)} found in images/")
    return out


def save(D, mode, layout=None, camera="", scene=""):
    if mode not in ("own", "flow"): raise ValueError("mode must be own or flow")
    v = {"mode": mode}
    if mode == "own":
        if layout not in ("static", "video"): raise ValueError("layout must be static or video")
        v.update({"layout": layout, "images": own_images(D), "camera": str(camera or "").strip()[:600], "scene": str(scene or "").strip()[:600]})
        pr = problems(D, v)
        if pr: raise ValueError(pr[0])
    import datetime
    v["chosen_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(v, open(vpath(D), "w", encoding="utf-8"), indent=2, ensure_ascii=False); open(vpath(D), "a").write("\n")
    return v


def main(a):
    if not a or a[0] in ("-h", "--help"): sys.exit(__doc__)
    D = C.song_dir(a[0])
    def opt(n, d=""): return a[a.index(n) + 1] if n in a and a.index(n) + 1 < len(a) else d
    if "--check" in a:
        v = load(D); print(json.dumps({"visuals": v, "images": own_images(D), "problems": problems(D, v)}, indent=2)); return 0
    if "--mode" in a:
        try: v = save(D, opt("--mode"), opt("--layout") or None, opt("--camera"), opt("--scene"))
        except ValueError as e: sys.exit(f"navaan: {e}")
        print("saved", json.dumps(v)); return 0
    if not os.path.exists(vpath(D)):
        sys.exit("navaan: choose the visuals first (portal song page, or: visuals_cfg.py <slug> --mode own --layout video)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
