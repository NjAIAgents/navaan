#!/usr/bin/env python3
"""inspire_render.py <slug> [--engine auto|remotion|ffmpeg]  render the vertical inspiration video from timing.json.

Output: final_reel_9x16.mp4 (1080x1920, 30 fps, h264 + aac, 7 to 15 s without a voice), thumb_9x16.jpg, render_report.json.

Engines:
  remotion  React typography and transitions rendered in headless Chrome. Best text, handles Hindi shaping. Needs `npm install` in the plugin's remotion folder.
  ffmpeg    background camera move with ffmpeg, text drawn with Pillow. No install beyond ffmpeg. Basic but predictable.
  auto      remotion when it is installed, else ffmpeg.
No generation credits are used by either engine.
"""
import os, sys, re, json, subprocess, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
LOG = L.get("inspire_render")

OUT, THUMB = "final_reel_9x16.mp4", "thumb_9x16.jpg"
W, H = 1080, 1920
LATIN_FONTS = [("/System/Library/Fonts/Supplemental/Georgia.ttf", 0), ("/System/Library/Fonts/Supplemental/Baskerville.ttc", 0), ("/Library/Fonts/Georgia.ttf", 0),
               ("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 0), ("/usr/share/fonts/opentype/inter/InterDisplay-Medium.otf", 0)]


SANS_FONTS = [("/usr/share/fonts/opentype/inter/InterDisplay-Medium.otf", 0), ("/System/Library/Fonts/Avenir Next.ttc", 0), ("/System/Library/Fonts/HelveticaNeue.ttc", 0),
              ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 0)]   # a channel whose look is sans (style.font), e.g. The Aha-lorithm
FACE = {"font": "serif"}   # set from timing.json's style when a render starts


def has_dev(t): return bool(re.search(r"[ऀ-ॿ]", t))


def pil_font(size, dev):
    from PIL import ImageFont
    if dev: return C.font(size)   # (the Latin list below is this screen's own serif choice; C.font_for is the plain one)
    e = os.environ.get("NAVAAN_FONT_LATIN")
    cands = ([(e.partition(":")[0], int(e.partition(":")[2] or 0))] if e else []) + (SANS_FONTS if FACE["font"] == "sans" else LATIN_FONTS)
    for p, i in cands:
        if os.path.exists(p): return ImageFont.truetype(p, size, index=i)
    return C.font(size)


def raqm():
    try:
        from PIL import features
        return bool(features.check("raqm"))
    except Exception as _e: L.soft(LOG, "raqm_error"); return False


def remotion_dir(): return os.path.join(C.plugin_dir(), "remotion")
def remotion_ready(): return os.path.isdir(os.path.join(remotion_dir(), "node_modules", "remotion")) and bool(shutil.which("node"))


# ---------- ffmpeg engine ----------
def layout(T):
    """Fit the text block: pick a font size so the longest line fits, then centre the block. Returns (font, lines with y, author y)."""
    from PIL import Image, ImageDraw
    lines = [l["text"] for l in T["lines"]]
    dev = any(has_dev(t) for t in lines)
    maxw = W - 2 * 96
    size = 104 if not dev else 92
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    while size > 40:
        f = pil_font(size, dev)
        if max(d.textlength(t, font=f) for t in lines) <= maxw: break
        size -= 4
    lh = int(size * 1.42)
    block = lh * len(lines)
    top = int(H * 0.44 - block / 2)
    return f, size, lh, top, dev


def draw_text(img, xy, text, font, fill, shadow=True, anchor="mm"):
    from PIL import Image, ImageDraw, ImageFilter
    if shadow:
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); ImageDraw.Draw(lay).text((xy[0], xy[1] + 6), text, font=font, fill=(0, 0, 0, 200), anchor=anchor)
        img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(img).text(xy, text, font=font, fill=fill, anchor=anchor)


def make_pngs(D, T, tmp):
    from PIL import Image, ImageDraw
    f, size, lh, top, dev = layout(T)
    white = (255, 255, 255, 255)
    # scrim: darken the picture so the words stay readable on any background
    col = Image.new("RGBA", (1, H)); px = col.load()
    base = int(255 * T["style"].get("dim", 0.45))
    for y in range(H):
        px[0, y] = (0, 0, 0, max(0, min(235, int(base * (0.55 + 0.75 * (1 - abs((y / H) - 0.45) * 1.6))))))
    sc = col.resize((W, H))
    sc.save(os.path.join(tmp, "scrim.png"))
    paths = []
    for i, ln in enumerate(T["lines"]):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_text(im, (W // 2, top + i * lh + lh // 2), ln["text"], f, white)
        p = os.path.join(tmp, f"line{i}.png"); im.save(p); paths.append(p)
    ap = None
    if T.get("author"):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        y = top + lh * len(T["lines"]) + 70
        acc = tuple(int(T["style"]["accent"].lstrip("#")[k:k + 2], 16) for k in (0, 2, 4)) + (255,)
        d.rectangle((W // 2 - 40, y - 34, W // 2 + 40, y - 30), fill=acc)
        draw_text(im, (W // 2, y + 20), T["author"]["text"], pil_font(int(size * 0.5), has_dev(T["author"]["text"])), (255, 255, 255, 235))
        ap = os.path.join(tmp, "author.png"); im.save(ap)
    wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wf = pil_font(42, False)
    draw_text(wm, (W // 2, H - 490), (" ".join(T.get("watermark", "NAVAAN").upper()) if not T.get("watermark", "").startswith("@") else T["watermark"]), wf, (255, 255, 255, 225), shadow=False)
    wp = os.path.join(tmp, "wm.png"); wm.save(wp)
    bp = None
    if T.get("brand"):
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        txt = T["brand"]["text"]; bs = min(76, int((W - 260) / (len(txt) * 0.62)))
        yy = int(H * 0.44)
        acc = tuple(int(T["style"]["accent"].lstrip("#")[k:k + 2], 16) for k in (0, 2, 4)) + (255,)
        d.rectangle((W // 2 - 45, yy - bs // 2 - 40, W // 2 + 45, yy - bs // 2 - 36), fill=acc)
        bf = pil_font(bs, has_dev(txt)); tw = int(d.textlength(txt, font=bf))
        if T["brand"].get("icon") == "instagram":
            ic = int(bs * 0.95); gap = int(bs * 0.38); x0 = (W - (ic + gap + tw)) // 2; cy = yy + 10
            lw = max(3, ic // 12)
            d.rounded_rectangle((x0, cy - ic // 2, x0 + ic, cy + ic // 2), radius=int(ic * 0.28), outline=(255, 255, 255, 255), width=lw)
            r = int(ic * 0.22); cx = x0 + ic // 2
            d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 255, 255, 255), width=lw)
            dr = max(2, ic // 20); dx, dy = x0 + int(ic * 0.72), cy - int(ic * 0.28)
            d.ellipse((dx - dr, dy - dr, dx + dr, dy + dr), fill=(255, 255, 255, 255))
            draw_text(im, (x0 + ic + gap + tw // 2, cy), txt, bf, (255, 255, 255, 255))
        elif T["brand"].get("icon") == "youtube":   # a rounded play button beside the handle
            ic = int(bs * 0.95); gap = int(bs * 0.38); x0 = (W - (ic + gap + tw)) // 2; cy = yy + 10; lw = max(3, ic // 12)
            d.rounded_rectangle((x0, cy - int(ic * 0.36), x0 + ic, cy + int(ic * 0.36)), radius=int(ic * 0.2), outline=(255, 255, 255, 255), width=lw)
            tx = x0 + int(ic * 0.42); d.polygon([(tx, cy - int(ic * 0.14)), (tx, cy + int(ic * 0.14)), (tx + int(ic * 0.24), cy)], fill=(255, 255, 255, 255))
            draw_text(im, (x0 + ic + gap + tw // 2, cy), txt, bf, (255, 255, 255, 255))
        else:
            draw_text(im, (W // 2, yy + 10), txt, bf, (255, 255, 255, 255))
        bp = os.path.join(tmp, "brand.png"); im.save(bp)
    return os.path.join(tmp, "scrim.png"), paths, ap, wp, bp


def cam_exprs(T):
    F = int(round(T["duration"] * T["fps"]))
    p = f"(on/{F})"; e = f"({p}*{p}*(3-2*{p}))"  # smooth start and stop
    cx, cy = "iw/2-iw/zoom/2", "ih/2-ih/zoom/2"
    c = T["camera"]
    if c == "push_in": z, x, y = f"1.0+0.14*{e}", cx, cy
    elif c == "pull_out": z, x, y = f"1.14-0.14*{e}", cx, cy
    elif c == "pan_left": z, x, y = "1.12", f"(iw-iw/zoom)*(1-{e})", cy
    elif c == "pan_right": z, x, y = "1.12", f"(iw-iw/zoom)*{e}", cy
    else: z, x, y = f"1.06+0.04*sin(PI*{p})", f"{cx}+iw*0.02*sin(2*PI*{p})", f"{cy}+ih*0.015*sin(2*PI*{p}+1)"
    return z, x, y, F


def render_ffmpeg(D, T, out):
    import tempfile
    ff = C.tool("ffmpeg"); tmp = tempfile.mkdtemp(prefix="inspire_")
    try:
        scrim, lines, ap, wp, bp = make_pngs(D, T, tmp)
        z, x, y, F = cam_exprs(T); fps = T["fps"]; dur = T["duration"]; hold = T["hold_until"]
        cmd = [ff, "-y", "-v", "error", "-i", os.path.join(D, T["background"])]
        n = 1
        extra = [scrim] + lines + ([ap] if ap else []) + [wp] + ([bp] if bp else [])
        for p in extra: cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{dur:.2f}", "-i", p]
        ai = []
        if T.get("music"): cmd += ["-i", os.path.join(D, T["music"])]; ai.append("m")
        if T.get("voiceover"): cmd += ["-i", os.path.join(D, T["voiceover"])]; ai.append("v")
        g = [f"[0:v]scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,setsar=1,zoompan=z='{z}':x='{x}':y='{y}':d={F}:s={W}x{H}:fps={fps},format=yuv420p[bg]",
             f"[bg][1:v]overlay=0:0:format=auto[v0]"]
        k = 2; cur = "v0"
        def layer(idx, start, end, name, rise):
            fi, fo = 0.7, 0.6
            g.append(f"[{idx}:v]format=rgba,fade=t=in:st={start:.2f}:d={fi}:alpha=1,fade=t=out:st={max(start + fi, end - fo):.2f}:d={fo}:alpha=1[{name}l]")
            ypos = f"'if(lt(t,{start:.2f}+{fi}),44*pow(1-(t-{start:.2f})/{fi},2),0)'" if rise else "0"
            return f"[{{cur}}][{name}l]overlay=x=0:y={ypos}:format=auto[{name}]"
        for i, ln in enumerate(T["lines"]):
            s = layer(k, ln["start"], hold, f"t{i}", T["transition"] == "rise"); g.append(s.format(cur=cur)); cur = f"t{i}"; k += 1
        if ap:
            a = T["author"]; s = layer(k, a["start"], hold, "au", T["transition"] == "rise"); g.append(s.format(cur=cur)); cur = "au"; k += 1
        if not T.get("brand"):  # with an end card the handle is shown there, not all the way through
            s = layer(k, 0.4, dur - 0.1, "wm", False); g.append(s.format(cur=cur)); cur = "wm"
        k += 1
        if bp:
            b = T["brand"]; s = layer(k, b["start"], dur - 0.1, "br", T["transition"] == "rise"); g.append(s.format(cur=cur)); cur = "br"; k += 1
        g.append(f"[{cur}]fade=t=in:st=0:d=0.5,fade=t=out:st={dur - 0.6:.2f}:d=0.6[vout]")
        ib = k
        if len(ai) == 2: g.append(f"[{ib}:a]volume=0.35[m];[{ib + 1}:a]volume=1.0[vo];[m][vo]amix=inputs=2:duration=longest:dropout_transition=0,volume=1.9[aout]")
        elif ai == ["m"]: g.append(f"[{ib}:a]volume=0.9[aout]")
        elif ai == ["v"]: g.append(f"[{ib}:a]volume=1.0[aout]")
        cmd += ["-filter_complex", ";".join(g), "-map", "[vout]"] + (["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-ar", "44100"] if ai else ["-an"])
        cmd += ["-t", f"{dur:.2f}", "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
        C.run(cmd)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- remotion engine ----------
def render_remotion(D, T, out):
    rd = remotion_dir()
    comp, props = "Quote", os.path.join(D, "timing.json")
    if T.get("narration"):  # a voiced quote: one line at a time, in step with the narration, then the end card
        br = T.get("brand") or {}
        np_ = {"width": W, "height": H, "fps": T.get("fps", 30), "duration": T["duration"], "bg": T["background"], "bg_is_image": True, "audio": T.get("voiceover"),
               "cues": [{"text": l["text"], "start": l["start"], "end": l["end"]} for l in T["lines"]], "title": "", "hook": "",
               "handle": ({"text": br["text"], "icon": br.get("icon", "instagram"), "start": br["start"]} if br else None),
               "style": T.get("style") or {"color": "#FFFFFF", "accent": "#FF4D7E", "dim": 0.4}, "mode": "reel",
               "acts": [{"kind": "calm", "from": 0, "to": T["duration"]}], "textY": 0.36}
        props = os.path.join(D, "narration_props.json"); json.dump(np_, open(props, "w", encoding="utf-8"), ensure_ascii=False, indent=2); comp = "Lyrics"
    cmd = ["npx", "--no-install", "remotion", "render", "src/index.ts", comp, out, f"--props={props}", f"--public-dir={D}",
           "--codec=h264", "--crf=18", "--pixel-format=yuv420p", "--log=error", "--overwrite"]
    chrome = os.environ.get("NAVAAN_CHROME") or next((c for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/usr/bin/google-chrome", "/usr/bin/chromium") if os.path.exists(c)), "")
    if chrome: cmd += [f"--browser-executable={chrome}", "--chrome-mode=chrome-for-testing"]  # the downloaded headless shell can crash on some Macs, a normal Chrome is steadier
    env = dict(os.environ); env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env.get("PATH", "")
    subprocess.run(cmd, cwd=rd, check=True, env=env)


# ---------- checks ----------
def probe(path):
    ffp = C.tool("ffprobe")
    j = json.loads(subprocess.check_output([ffp, "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration,size", "-of", "json", path]))
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), {}); a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    return {"width": v.get("width"), "height": v.get("height"), "codec": v.get("codec_name"), "has_audio": bool(a), "duration": round(float(j["format"]["duration"]), 2), "bytes": int(j["format"]["size"])}


def validate(info, T, max_s=60):
    errs, warns = [], []
    if (info["width"], info["height"]) != (W, H): errs.append(f"size is {info['width']}x{info['height']}, need {W}x{H}")
    if info["codec"] != "h264": errs.append(f"codec is {info['codec']}, need h264")
    if info["duration"] < 9.5: errs.append(f"{info['duration']}s is shorter than the 10 s minimum")
    if info["duration"] > max_s: errs.append(f"{info['duration']}s is too long (limit {max_s} s)")
    elif info["duration"] > 30.5: warns.append(f"{info['duration']}s is over the 30 s target")
    if not info["has_audio"]: warns.append("no audio track")
    if abs(info["duration"] - T["duration"]) > 0.6: warns.append(f"length {info['duration']}s differs from the plan {T['duration']}s")
    if info["bytes"] > 90 * 1024 * 1024: warns.append("file is over 90 MB")
    return errs, warns


def main(slug, engine="auto"):
    D = C.song_dir(slug); T = C.load_json(os.path.join(D, "timing.json")); FACE["font"] = (T.get("style") or {}).get("font") or "serif"
    for k in ("background", "music", "voiceover"):
        if T.get(k) and not os.path.exists(os.path.join(D, T[k])): sys.exit(f"navaan: timing.json points at {T[k]} but it is missing. Run the typography step again.")
    dev = any(has_dev(l["text"]) for l in T["lines"])
    if engine == "auto": engine = "remotion" if remotion_ready() else "ffmpeg"
    if engine == "remotion" and not remotion_ready(): sys.exit(f"navaan: remotion is not installed. Run: cd {remotion_dir()} && npm install  (or use --engine ffmpeg)")
    if engine == "ffmpeg" and dev and not raqm(): print("warning: this Pillow has no raqm, Devanagari conjuncts may look wrong with the ffmpeg engine. Install the remotion engine for exact Hindi text.", flush=True)
    out = os.path.join(D, OUT); part = out + ".part.mp4"
    if os.path.exists(part): os.remove(part)
    print(f"rendering {T['duration']}s with {engine} ...", flush=True)
    (render_remotion if engine == "remotion" else render_ffmpeg)(D, T, part)
    import send_line
    try:
        said = send_line.apply(part, D, y_frac=0.56)   # the "send this to someone who..." line under the end card, when there is one
        if said: print(f"send line drawn: {said}", flush=True)
    except RuntimeError as e: print("warning:", e, flush=True)   # the video stays as rendered, without the line
    info = probe(part); errs, warns = validate(info, T)
    for w in warns: print("warning:", w)
    if errs:
        os.remove(part); sys.exit("navaan: render failed checks: " + "; ".join(errs))
    os.replace(part, out)
    t = min(T["duration"] - 0.5, (T["lines"][-1]["start"] + 1.8)) if T["lines"] else 2.0
    C.run([C.tool("ffmpeg"), "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", out, "-frames:v", "1", "-q:v", "2", os.path.join(D, THUMB)])
    json.dump({"engine": engine, "checks": "passed" if not warns else "passed with warnings", "warnings": warns, **info}, open(os.path.join(D, "render_report.json"), "w"), indent=2)
    print(f"done: {OUT} {info['width']}x{info['height']} {info['duration']}s {info['bytes'] // 1024} KB ({engine})")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    main(a[0], a[a.index("--engine") + 1] if "--engine" in a else "auto")
