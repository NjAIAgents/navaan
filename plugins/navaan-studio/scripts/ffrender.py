#!/usr/bin/env python3
"""ffrender.py  the fast renderer for the Shots video (the 16:9 video and the vertical reel), plain ffmpeg, no browser.

render(D, props, out)  takes the same props the Remotion Shots composition takes (shots_render.py builds them) and writes out.
Each shot is cut as its own clip (a picture or a moving loop, with the same camera move), several at once, then one pass joins them with the
cross fades, the grade, the fade out, the channel mark and the audio. Remotion drew every frame in a headless browser and took 20 minutes or
more for a song; this takes a few. Anything that goes wrong raises, and shots_render.py then falls back to Remotion.
Set video.renderer to "remotion" in the profile to always use Remotion."""
import os, sys, json, subprocess, shutil
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

BASE = 1.16   # every picture is drawn a little larger than the frame, so a move never shows an edge (same as Shots.tsx)
SS = 2        # a picture is moved inside a copy this many times larger than the frame, so slow moves do not stutter


def coeffs(camera, focus):
    """(s0, s1, x0, x1, y0, y1): scale = s0 + s1*p, shift in percent of the frame = x0 + x1*p, y0 + y1*p, for progress p from 0 to 1. Mirrors move() in Shots.tsx."""
    fx, fy = focus; travel = (BASE - 1) * 50
    if camera == "push_in": return (BASE, 0.1, 0, (0.5 - fx) * 8, 0, (0.5 - fy) * 8)
    if camera == "pull_out": return (BASE + 0.1, -0.1, (0.5 - fx) * 8, -(0.5 - fx) * 8, (0.5 - fy) * 8, -(0.5 - fy) * 8)
    if camera == "pan_left": return (BASE, 0, travel, -2 * travel, 0, 0)
    if camera == "pan_right": return (BASE, 0, -travel, 2 * travel, 0, 0)
    if camera == "tilt_up": return (BASE, 0, 0, 0, travel, -2 * travel)
    if camera == "tilt_down": return (BASE, 0, 0, 0, -travel, 2 * travel)
    if camera == "drift": return (BASE + 0.03, 0, -travel * 0.6, 1.2 * travel, travel * 0.3, -0.6 * travel)
    return (BASE, 0, 0, 0, 0, 0)   # hold


def move(camera, p, focus):
    s0, s1, x0, x1, y0, y1 = coeffs(camera, focus)
    return s0 + s1 * p, x0 + x1 * p, y0 + y1 * p


def fit_scale(camera, p):
    """The small move of a picture shown whole (see moveFit in Shots.tsx)."""
    return {"push_in": 1 + 0.06 * p, "pull_out": 1.06 - 0.06 * p, "drift": 1.03}.get(camera, 1.0)


def _n(v): return ("%.6f" % v).rstrip("0").rstrip(".") or "0"


def zoompan(shot, W, H, fps, lead, length, fit=False):
    """The zoompan filter for one shot. The window is the frame divided by the scale; the shift is in percent of the frame, as in the browser version."""
    P = f"min(1,max(0,(on/{fps}-{_n(lead)})/{_n(max(0.1, length))}))"
    if fit:
        z = {"push_in": f"1+0.06*{P}", "pull_out": f"1.06-0.06*{P}", "drift": "1.03"}.get(shot.get("camera", "hold"), "1")
        return f"zoompan=z='{z}':x='(iw-iw/({z}))/2':y='(ih-ih/({z}))/2':d=1:s={W}x{H}:fps={fps}"
    s0, s1, x0, x1, y0, y1 = coeffs(shot.get("camera", "hold"), shot.get("focus") or [0.5, 0.5])
    z = f"{_n(s0)}+{_n(s1)}*{P}"
    x = f"(iw-iw/({z}))/2-({_n(x0)}+{_n(x1)}*{P})/100*{W * SS}/({z})"
    y = f"(ih-ih/({z}))/2-({_n(y0)}+{_n(y1)}*{P})/100*{H * SS}/({z})"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={fps}"


def _dims(path):
    j = json.loads(subprocess.check_output([C.tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", path]))
    s = j["streams"][0]; return int(s["width"]), int(s["height"])


def timeline(shots, fade, total):
    """[(from, lead, len)] for each shot: the clip starts `lead` seconds before the shot so its fade in overlaps the one before, the same rule as the browser version."""
    out = []
    for i, s in enumerate(shots):
        lead = 0.0 if i == 0 else fade
        frm = max(0.0, float(s["start"]) - lead)
        ln = max(0.2, float(s["end"]) - float(s["start"]))
        out.append((frm, float(s["start"]) - frm, ln))
    return out


def segment(D, shot, i, frm, lead, ln, W, H, fps, work):
    """Cut one shot to work/seg_i.mp4. Returns the path."""
    seg_len = lead + ln
    out = os.path.join(work, "seg_%03d.mp4" % i)
    media = os.path.join(D, shot["loop"] if shot.get("loop") else shot["image"])
    if not os.path.exists(media): raise FileNotFoundError(media)
    src = ["-stream_loop", "-1", "-t", _n(seg_len), "-i", media] if shot.get("loop") else ["-loop", "1", "-framerate", str(fps), "-t", _n(seg_len), "-i", media]
    pre = f"fps={fps}," if shot.get("loop") else ""
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "14", "-pix_fmt", "yuv420p", "-r", str(fps), "-an", out]
    if shot.get("fit"):
        bg = shot.get("bg")
        if not bg or not os.path.exists(os.path.join(D, bg)): raise ValueError("a fitted shot needs its blurred backdrop")
        w0, h0 = _dims(media)
        if w0 * H >= h0 * W: fw, fh = W, round(W * h0 / w0)
        else: fh, fw = H, round(H * w0 / h0)
        fw -= fw % 2; fh -= fh % 2
        fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1[b];"
              f"[1:v]{pre}scale={fw * SS}:{fh * SS}:flags=bicubic,{zoompan(shot, fw, fh, fps, lead, ln, fit=True)}[f];"
              f"[b][f]overlay=x=(W-w)/2:y=(H-h)/2,format=yuv420p,setsar=1[v]")
        cmd = [C.tool("ffmpeg"), "-y", "-v", "error", "-loop", "1", "-framerate", str(fps), "-t", _n(seg_len), "-i", os.path.join(D, bg), *src, "-filter_complex", fc, "-map", "[v]", *enc]
    else:
        fx, fy = (shot.get("focus") or [0.5, 0.5])
        vf = (f"{pre}scale={W * SS}:{H * SS}:force_original_aspect_ratio=increase:flags=bicubic,crop={W * SS}:{H * SS}:x='(iw-out_w)*{_n(fx)}':y='(ih-out_h)*{_n(fy)}',"
              f"{zoompan(shot, W, H, fps, lead, ln)},format=yuv420p,setsar=1")
        cmd = [C.tool("ffmpeg"), "-y", "-v", "error", *src, "-vf", vf, *enc]
    subprocess.run(cmd, check=True)
    return out


def vignette_layer(W, H, strength):
    """The same edge darkening as the Remotion grade: a CSS radial-gradient, transparent up to 55% of the way to the corner, then linear to `strength` black.
    Smooth, so it is computed on a small grid and scaled up (no numpy needed)."""
    from PIL import Image
    w, h = max(2, W // 8), max(2, H // 8)
    k = float(strength) * 255
    rx, ry = w / 2 * 2 ** 0.5, h / 2 * 2 ** 0.5
    px = []
    for j in range(h):
        dy = ((j + 0.5 - h / 2) / ry) ** 2
        for i in range(w):
            t = (dy + ((i + 0.5 - w / 2) / rx) ** 2) ** 0.5
            px.append(round(min(1.0, max(0.0, (t - 0.55) / 0.45)) * k))
    a = Image.new("L", (w, h)); a.putdata(px)
    a = a.resize((W, H), Image.BICUBIC)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.putalpha(a)
    return im


def watermark_png(text, W, H, path, vignette=0.0):
    """A transparent frame with the edge darkening and the channel mark: bottom right on a wide video, top left on a vertical one (clear of the app buttons)."""
    from PIL import Image, ImageDraw
    vertical = H > W
    size = round(min(W, H) * (0.034 if vertical else 0.03))
    im = vignette_layer(W, H, vignette) if vignette else Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if not text:
        im.save(path); return
    f = C.font_for(text, size); d = ImageDraw.Draw(im)   # Latin text needs a font with letters: the caption font is Devanagari
    l, t, r, b = d.textbbox((0, 0), text, font=f)
    tw, th = r - l, b - t
    x, y = (round(W * 0.045), round(H * 0.12)) if vertical else (W - tw - round(W * 0.025), H - th - round(H * 0.04))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); ImageDraw.Draw(sh).text((x + 1, y + 2), text, font=f, fill=(0, 0, 0, 165))
    from PIL import ImageFilter
    im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(2)))
    ImageDraw.Draw(im).text((x, y), text, font=f, fill=(255, 255, 255, 158))
    im.save(path)


def render(D, props, out):
    W, H, fps, dur = int(props["width"]), int(props["height"]), int(props["fps"]), float(props["duration"])
    fade = float(props.get("fade", 1.0)); shots = props["shots"]
    if not shots: raise ValueError("no shots")
    ff = C.tool("ffmpeg")
    work = os.path.join(D, ".cache", "ffseg"); shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
    try:
        tl = timeline(shots, fade, dur)
        workers = max(1, min(6, (os.cpu_count() or 2) // 2 or 1))
        print(f"fast render: {len(shots)} shots, {workers} at a time ...", flush=True)
        with ThreadPoolExecutor(workers) as ex:
            segs = list(ex.map(lambda a: segment(D, a[1], a[0], *tl[a[0]], W, H, fps, work), list(enumerate(shots))))
        ins = []
        for p in segs: ins += ["-i", p]
        n = len(segs); fc = []; last = "[0:v]"
        for i in range(1, n):
            frm, lead, _ = tl[i]
            fc.append(f"{last}[{i}:v]xfade=transition=fade:duration={_n(max(0.04, lead))}:offset={_n(frm)}[x{i}]"); last = f"[x{i}]"
        g = props.get("grade") or {}; dim = float(g.get("dim", 0)); vig = float(g.get("vignette", 0))
        post = []
        if dim: post.append(f"lutyuv=y='val*{_n(1 - dim)}':u='128+(val-128)*{_n(1 - dim)}':v='128+(val-128)*{_n(1 - dim)}'")
        fo = float(props.get("fadeOut", 0))
        if fo > 0: post.append(f"fade=t=out:st={_n(max(0, dur - fo))}:d={_n(fo)}")
        post.append("format=yuv420p")
        wm = props.get("watermark"); extra = []
        k = n
        if props.get("audio"): extra += ["-i", os.path.join(D, props["audio"])]; ai = k; k += 1
        else: ai = None
        chain = ",".join(post)
        if wm or vig:
            wp = os.path.join(work, "wm.png"); watermark_png(wm, W, H, wp, vig)
            extra = ["-loop", "1", "-framerate", str(fps), "-i", wp] + extra   # the mark is input n, so the audio index moves up by one
            if ai is not None: ai += 1
            fc.append(f"{last}{chain}[g];[g][{n}:v]overlay=0:0:format=auto,format=yuv420p[v]")
        else:
            fc.append(f"{last}{chain}[v]")
        cmd = [ff, "-y", "-v", "error", *ins, *extra, "-filter_complex", ";".join(fc), "-map", "[v]"]
        if ai is not None: cmd += ["-map", f"{ai}:a", "-c:a", "aac", "-b:a", "256k"]
        cmd += ["-t", _n(dur), "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", out]
        subprocess.run(cmd, check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)
