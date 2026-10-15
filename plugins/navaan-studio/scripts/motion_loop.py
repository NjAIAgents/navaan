#!/usr/bin/env python3
"""motion_loop.py  turn one picture into a calm looping clip: the tree sways, the river flows, leaves fall, clouds drift.

Only the regions named in `regions` move. Everything else stays exactly as drawn. Every motion is periodic over the loop,
so the clip repeats with no jump. No model and no credits: the cost is a minute of CPU.

regions (all points are fractions of the picture, x then y, 0 to 1):
  {"foliage": [[[x,y],...]], "water": [[[x,y],...]], "sky": [[[x,y],...]]}   each a list of polygons, any may be missing
  foliage: sways; inside the polygon only saturated leaf pixels move, so branches and sky stay put. Falling leaves start under it.
  water:   flows left to right with the current (faster near the bottom of the polygon), ripples and glints travel with it,
           a few leaves float on it.
  sky:     clouds drift slowly.
  sway:    cloth, curtains, washing lines, hair: the area bends sideways, most at its free (lower) end.
  flicker: a flame, a lamp, a screen glow: the area gets slightly brighter and darker in an uneven rhythm.
  steam:   a cup, a pot, a chimney: soft pale wisps rise through the area and fade.
render(image, out, regions, size=(1080, 1920), seconds=8, fps=24, strength="subtle", crop="center")
iter_frames(...) yields the frames (BGR arrays) so a test or another step can use them without ffmpeg.
strength: off (no motion), subtle (default), gentle (about 1.6 times as much). Needs numpy and opencv (cv2).
"""
import os, sys, math, json, argparse, subprocess

STRENGTH = {"off": 0.0, "subtle": 1.0, "gentle": 1.6}
KINDS = ("foliage", "water", "sky", "sway", "flicker", "steam")


def clean_regions(reg):
    """Keep only known kinds and polygons with at least 3 points, points clamped to 0..1. Whatever the director wrote, the engine gets safe input."""
    out = {}
    for kind in KINDS:
        polys = []
        for poly in (reg or {}).get(kind) or []:
            try:
                pts = [[min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y)))] for x, y in poly]
            except (TypeError, ValueError):
                continue
            if len(pts) >= 3: polys.append(pts)
        if polys: out[kind] = polys
    return out


def _cv():
    import numpy as np, cv2
    return np, cv2


def poly_mask(shape, polys, blur):
    np, cv2 = _cv()
    H, W = shape
    m = np.zeros((H, W), np.uint8)
    for poly in polys or []:
        cv2.fillPoly(m, [np.round(np.array(poly, np.float32) * [W - 1, H - 1]).astype(np.int32)], 255)
    m = m.astype(np.float32) / 255
    s = max(1.0, blur * W / 1024)
    return cv2.GaussianBlur(m, (0, 0), s) if m.any() else m


def foliage_mask(img, polys):
    """Leaf pixels inside the polygon: saturated, not too dark, with the edge softened."""
    np, cv2 = _cv()
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    sat, val = hsv[..., 1] / 255, hsv[..., 2] / 255
    inside = poly_mask(img.shape[:2], polys, 0) > 0.5
    leaf = (inside & (sat > 0.45) & (val > 0.28)).astype(np.float32)
    k = max(3, int(9 * img.shape[1] / 1024) | 1)
    leaf = cv2.morphologyEx(leaf, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8))
    return cv2.GaussianBlur(leaf, (0, 0), max(1.0, 6 * img.shape[1] / 1024))


def _poly(cx, cy, sx, sy, ang):
    np, _ = _cv()
    pts = np.array([[0, -1.0], [0.55, -0.35], [0.9, -0.2], [0.45, 0.2], [0.55, 0.75], [0, 0.45], [-0.55, 0.75], [-0.45, 0.2], [-0.9, -0.2], [-0.55, -0.35]]) * [sx, sy]
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    return pts @ np.array([[c, -s], [s, c]]).T + [cx, cy]


def _ell(cx, cy, sx, sy):
    np, _ = _cv()
    th = np.linspace(0, 2 * np.pi, 14, endpoint=False)
    return np.stack([cx + sx * np.cos(th), cy + sy * np.sin(th)], 1)


def _stamp(img, pts, col, alpha, blur):
    np, cv2 = _cv()
    H, W = img.shape[:2]
    x0, y0 = np.floor(pts.min(0) - 4).astype(int)
    x1, y1 = np.ceil(pts.max(0) + 4).astype(int)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if x1 <= x0 or y1 <= y0:
        return
    lay = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.fillPoly(lay, [np.round((pts - [x0, y0]) * 16).astype(np.int32)], 255, cv2.LINE_AA, shift=4)
    m = cv2.GaussianBlur(lay.astype(np.float32) / 255, (0, 0), blur) * alpha
    roi = img[y0:y1, x0:x1].astype(np.float32)
    for c in range(3):
        roi[..., c] = roi[..., c] * (1 - m) + col[c] * m
    img[y0:y1, x0:x1] = roi.astype(np.uint8)


def iter_frames(image, regions, size=(1080, 1920), seconds=8, fps=24, strength="subtle", crop="center", seed=11):
    np, cv2 = _cv()
    im = image if hasattr(image, "shape") else cv2.imread(image)
    if im is None:
        raise ValueError("cannot read the picture")
    H, W = im.shape[:2]
    k = STRENGTH[strength]
    sc = W / 1024.0
    N = max(2, int(seconds * fps))
    regions = regions or {}
    foliage = foliage_mask(im, regions.get("foliage")) if regions.get("foliage") else np.zeros((H, W), np.float32)
    water = poly_mask((H, W), regions.get("water"), 5)
    sky = poly_mask((H, W), regions.get("sky"), 25) * (1 - foliage)
    sway = poly_mask((H, W), regions.get("sway"), 6)
    flick = poly_mask((H, W), regions.get("flicker"), 10)
    sy_ = np.where(sway > 0.05)[0]
    swtop, swbot = (int(sy_.min()), int(sy_.max())) if len(sy_) else (0, 1)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # output window: the target aspect, cut from the picture (center, left or right)
    ow = min(W, int(round(H * size[0] / size[1])))
    ox = {"left": 0, "right": W - ow}.get(crop, (W - ow) // 2)
    wy = np.where(water > 0.05)[0]
    top, bot = (int(wy.min()), int(wy.max())) if len(wy) else (0, 1)
    depth = np.clip((yy - top) / max(1, bot - top), 0, 1)
    flowD = (10 + 38 * depth ** 1.2) * sc * k
    phi = 2 * np.pi * (xx / (420 * sc) + yy / (760 * sc))
    ampx = np.clip(xx / (500 * sc), 0.25, 1.0)
    rng = np.random.RandomState(seed)
    pal = im[foliage > 0.9]
    def pick():
        return tuple(int(c) for c in (pal[rng.randint(len(pal))] if len(pal) else (40, 110, 220)))
    fy = np.where(foliage > 0.3)[0]
    f_top = int(fy.min()) if len(fy) else int(H * 0.15)
    ground = int(H * 0.78) if not len(wy) else top - int(0.02 * H)
    falling = []
    if foliage.any() and k > 0:
        fx = np.where(foliage > 0.3)[1]
        for _ in range(15):
            falling.append(dict(x0=rng.uniform(fx.min(), fx.max()), y0=rng.uniform(0, 1), size=rng.uniform(8, 17) * sc, a0=rng.uniform(0, 360), k=int(rng.choice([1, 2, -1])),
                                sw=rng.uniform(14, 34) * sc, sph=rng.uniform(0, 6.28), col=pick(), blur=rng.uniform(0.4, 1.4)))
    floating = []
    if water.any() and k > 0:
        for _ in range(8):
            floating.append(dict(x0=rng.uniform(0, W * 0.9), y=rng.uniform(top + 0.2 * (bot - top), bot - 0.1 * (bot - top)), size=rng.uniform(9, 15) * sc, a0=rng.uniform(-20, 20), col=pick(), ph=rng.uniform(0, 1)))
    wisps = []
    if k > 0:
        for poly in regions.get("steam") or []:
            P = np.array(poly, np.float32) * [W - 1, H - 1]
            px0, py0 = P.min(0)
            px1, py1 = P.max(0)
            for _ in range(7):
                wisps.append(dict(x0=rng.uniform(px0, px1), y0=py1, rise=max(40 * sc, py1 - py0), sw=rng.uniform(6, 18) * sc, ph=rng.uniform(0, 1),
                                  sx=max(8 * sc, (px1 - px0) * 0.22), col=(226, 228, 230), alpha=0.11 * min(1.0, k)))
    ycut = f_top + int(0.2 * H)
    for n in range(N):
        t = n / N
        a = 2 * np.pi * t
        out = im
        if k > 0:
            dx = foliage * ampx * (4.6 * np.sin(a + phi) + 1.6 * np.sin(2 * a + 1.7 * phi)) * sc * k
            dy = foliage * 1.8 * np.sin(a + phi + 1.1) * sc * k
            if sway.any():
                hang = 0.35 + 0.65 * np.clip((yy - swtop) / max(1, swbot - swtop), 0, 1)
                dx = dx + sway * hang * (5.0 * np.sin(a + yy / (260 * sc)) + 1.8 * np.sin(2 * a + yy / (140 * sc))) * sc * k
                dy = dy + sway * hang * 0.8 * np.sin(a + yy / (200 * sc) + 0.9) * sc * k
            out = cv2.remap(im, xx + dx, yy + dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            if water.any():
                def smp(p):
                    return cv2.remap(im, xx - flowD * (p - 0.5), yy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
                p0, p1 = t, (t + 0.5) % 1.0
                w0 = 1 - abs(2 * p0 - 1)
                cur = smp(p0) * w0 + smp(p1) * (1 - w0)
                kk = 2 * np.pi / ((70 - 35 * depth) * sc)
                ph = kk * xx * 0.9 - 3 * a + yy / (11 * sc)
                cur = cv2.remap(cur, xx + 1.2 * k * sc * np.sin(ph) * (0.5 + depth), yy + 1.6 * k * sc * np.sin(ph + 1.3) * (0.5 + depth), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
                cur = np.clip(cur * (1 + k * (0.07 * np.sin(ph * 1.3) * (0.4 + depth) + 0.04 * np.sin(2 * a - xx / (90 * sc))))[..., None], 0, 255)
                out = out.astype(np.float32) * (1 - water[..., None]) + cur * water[..., None]
            if sky.any():
                cl = cv2.remap(im, xx - 14 * sc * k * math.sin(a), yy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT).astype(np.float32)
                out = out.astype(np.float32) * (1 - sky[..., None]) + cl * sky[..., None]
            if flick.any():
                g = 1 + k * 0.16 * (0.5 * math.sin(3 * a + 0.3) + 0.3 * math.sin(5 * a + 1.7) + 0.2 * math.sin(8 * a + 4.1))
                out = out.astype(np.float32) * (1 + (g - 1) * flick[..., None])
            out = np.clip(out, 0, 255).astype(np.uint8)
            if out is im:
                out = im.copy()
            for L in falling:
                prog = (L["y0"] + t) % 1.0
                cy = ycut + prog * max(10, ground - ycut)
                cx = L["x0"] + L["sw"] * math.sin(2 * math.pi * (t * 2 + L["sph"] / 6.28)) + 40 * sc * prog
                fade = min(1.0, prog / 0.08, (1 - prog) / 0.1)
                sx = L["size"] * (0.75 + 0.25 * abs(math.cos(math.radians(360 * L["k"] * t * 0.5 + L["a0"]))))
                _stamp(out, _poly(cx, cy, sx, L["size"], L["a0"] + 360 * L["k"] * t), L["col"], 0.8 * fade, L["blur"])
            for L in floating:
                prog = (L["ph"] + t) % 1.0
                cx = L["x0"] + (40 + 70 * float(depth[min(H - 1, int(L["y"])), 0])) * sc * prog
                fade = min(1.0, prog / 0.15, (1 - prog) / 0.15)
                _stamp(out, _poly(cx, L["y"] + 1.2 * sc * math.sin(2 * a + L["ph"] * 6.28), L["size"], L["size"] * 0.3, L["a0"] + 6 * math.sin(a + L["ph"] * 6.28)), L["col"], 0.75 * fade, 0.6)
            for L in wisps:
                prog = (L["ph"] + t) % 1.0
                cy = L["y0"] - prog * L["rise"]
                cx = L["x0"] + L["sw"] * math.sin(2 * math.pi * (t + L["ph"]))
                fade = min(1.0, prog / 0.2, (1 - prog) / 0.35)
                grow = 0.7 + 0.9 * prog
                _stamp(out, _ell(cx, cy, L["sx"] * grow, L["sx"] * 1.3 * grow), L["col"], L["alpha"] * fade, 9 * sc)
        yield cv2.resize(out[:, ox:ox + ow], tuple(size), interpolation=cv2.INTER_LANCZOS4)


def render(image, out, regions, size=(1080, 1920), seconds=8, fps=24, strength="subtle", crop="center", ffmpeg="ffmpeg"):
    if strength not in STRENGTH:
        raise ValueError("strength must be off, subtle or gentle")
    cmd = [ffmpeg, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "%dx%d" % tuple(size), "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for fr in iter_frames(image, regions, size, seconds, fps, strength, crop):
            p.stdin.write(fr.tobytes())
    finally:
        p.stdin.close()
        p.wait()
    if p.returncode != 0:
        raise RuntimeError("ffmpeg could not write the clip")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("out")
    ap.add_argument("--regions", required=True, help="JSON file: foliage, water, sky polygons as fractions")
    ap.add_argument("--seconds", type=float, default=8)
    ap.add_argument("--strength", default="subtle", choices=list(STRENGTH))
    ap.add_argument("--crop", default="center", choices=["left", "center", "right"])
    a = ap.parse_args()
    with open(a.regions, encoding="utf-8") as f:
        reg = json.load(f)
    print(render(a.image, a.out, reg, seconds=a.seconds, strength=a.strength, crop=a.crop))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as e:
        sys.exit(str(e))
