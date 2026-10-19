#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: the hands of the reel pipeline: executes the approved edit plan (edl.json) on the footage with plain ffmpeg and Pillow, no browser and no extra install.

  reel_render.py <slug>

Reads edl.json (checked by reel_edl.validate first), source.mp4, quote.json (the on-screen words), voiceover.* and voiceover.srt (when the quote is narrated), music from the
NAVAAN library (reel_music.resolve) or the owner's own upload (music_src.*). Writes final_reel_9x16.mp4 (1080x1920, 30 fps, h264 + aac), thumb_9x16.jpg and render_report.json.
One ffmpeg pass: each kept part is cut, framed to 9:16 (centre and slow zoom from the plan), joined, graded, then the quote and text are laid on as Pillow pictures
(so no drawtext or libass is needed), and the sound is mixed: footage sound by policy, voice, music ducked under the voice, normalised to -16 LUFS.
"""
import os, sys, re, json, glob, shutil, tempfile, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
import reel_edl as E, reel_music as RM
LOG = L.get("reel_render")

OUT, THUMB = "final_reel_9x16.mp4", "thumb_9x16.jpg"
W, H, FPS = E.W, E.H, E.FPS
BAND = {"top": 0.17, "mid": 0.42, "low": 0.68}   # block centre as a share of the height; the bottom fifth is left free for the app's own buttons
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac")


def grade_filters(g):
    f = [f"eq=brightness={g['brightness']:.3f}:contrast={g['contrast']:.3f}:saturation={g['saturation']:.3f}:gamma={g['gamma']:.3f}"]
    look = g["look"]
    if look == "warm": f.append("colorbalance=rs=0.06:gs=0.01:bs=-0.07:rm=0.04:bm=-0.05")
    elif look == "cool": f.append("colorbalance=rs=-0.05:bs=0.07:rm=-0.03:bm=0.05")
    elif look == "cinematic": f += ["curves=all='0/0 0.25/0.2 0.5/0.5 0.75/0.8 1/1'", "colorbalance=rs=0.05:bs=-0.06:rh=0.04:bh=-0.04"]
    elif look == "vivid": f.append("hue=s=1.2")
    elif look == "mono": f.append("hue=s=0")
    if g["vignette"]: f.append("vignette=PI/5")
    f.append("unsharp=5:5:0.4:5:5:0.0")
    return f


def segment_chain(i, s):
    d = s["end"] - s["start"]
    f = [f"trim=start={s['start']:.3f}:end={s['end']:.3f}", "setpts=PTS-STARTPTS",
         f"crop=w='trunc(min(iw,ih*9/16)/2)*2':h='trunc(min(ih,iw*16/9)/2)*2':x='(iw-ow)*{s['crop_x']:.3f}':y='(ih-oh)*{s['crop_y']:.3f}'",
         f"scale={W}:{H}:flags=lanczos", "setsar=1"]
    if s["zoom"] != 1.0 or s["zoom_to"] != 1.0:   # a slow punch in or out, steady because the scale is recomputed for every frame
        z = f"({s['zoom']:.3f}+({s['zoom_to']:.3f}-{s['zoom']:.3f})*t/{d:.3f})"
        f += [f"scale=w='trunc({W}*{z}/2)*2':h='trunc({H}*{z}/2)*2':eval=frame:flags=bilinear", f"crop={W}:{H}:'(iw-{W})/2':'(ih-{H})/2'"]
    return f"[s{i}]" + ",".join(f) + f",fps={FPS},format=yuv420p[v{i}]"


# ---------- text pictures ----------
def wrap(draw, text, font, maxw):
    out, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= maxw or not cur: cur = t
        else: out.append(cur); cur = w
    return out + ([cur] if cur else [])


def text_png(text, pos, path, face="serif", author=""):
    from PIL import Image, ImageDraw
    import inspire_render as R
    R.FACE["font"] = face
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); dev = R.has_dev(text); maxw = W - 2 * 110
    size = 88 if not dev else 78
    while True:
        f = R.pil_font(size, dev); lines = wrap(d, text, f, maxw)
        if (len(lines) <= 5 and max(d.textlength(l, font=f) for l in lines) <= maxw) or size <= 40: break
        size -= 4
    lh = int(size * 1.35); top = int(H * BAND[pos] - lh * len(lines) / 2)
    for k, l in enumerate(lines): R.draw_text(im, (W // 2, top + k * lh + lh // 2), l, f, (255, 255, 255, 255))
    if author:
        af = R.pil_font(max(30, int(size * 0.45)), R.has_dev(author)); R.draw_text(im, (W // 2, top + lh * len(lines) + int(size * 0.55)), author, af, (255, 255, 255, 225))
    im.save(path)


def scrim_png(path):
    """A soft dark wash over the top and the middle band so white words stay readable on any footage."""
    from PIL import Image
    col = Image.new("RGBA", (1, H)); px = col.load()
    for y in range(H):
        v = y / H; a = 0.0
        for c in BAND.values(): a = max(a, 1 - min(1.0, abs(v - c) / 0.2))
        px[0, y] = (0, 0, 0, int(105 * a))
    col.resize((W, H)).save(path)


def parse_srt(path):
    cues = []
    for blk in re.split(r"\n\s*\n", open(path, encoding="utf-8").read().strip()):
        ls = [l for l in blk.splitlines() if l.strip()]
        m = next((re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", l) for l in ls if "-->" in l), None)
        if not m: continue
        g = [int(x) for x in m.groups()]
        cues.append({"start": g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, "end": g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000, "text": " ".join(l for l in ls if "-->" not in l and not l.strip().isdigit())})
    return cues


def quote_cues(D, edl):
    """[(text, start, end)] of the quote's lines in reel time: with the voice, where each line is spoken; without it, spread evenly from quote.start."""
    q = C.load_json(os.path.join(D, "quote.json"), default=None) or {}
    lines = [C.plain(l).strip() for l in (q.get("lines") or []) if str(l).strip()] or ([C.plain(q.get("text") or "").strip()] if str(q.get("text") or "").strip() else [])
    if not lines: return [], ""
    total = edl["seconds"]; vo0 = edl["audio"]["vo_start"]; srt = os.path.join(D, "voiceover.srt")
    cues = parse_srt(srt) if os.path.exists(srt) and find_voice(D) else []
    if cues and len(cues) == len(lines):
        out = [(t, min(total - 0.3, c["start"] + vo0), min(total, c["end"] + vo0 + 0.35)) for t, c in zip(lines, cues)]
    else:
        t0 = min(edl["quote"]["start"], max(0.0, total - 2.0)); span = max(1.0, total - 0.6 - t0); per = span / len(lines)
        out = [(t, t0 + i * per, t0 + (i + 1) * per) for i, t in enumerate(lines)]
    return [(t, round(a, 2), round(max(b, a + 0.8), 2)) for t, a, b in out if a < total], str(q.get("author") or "").strip()


def find_voice(D):
    return next((p for e in AUDIO_EXT for p in glob.glob(os.path.join(D, "voiceover" + e))), None)


def find_music(slug, D, edl):
    own = next(iter(sorted(glob.glob(os.path.join(D, "music_src.*")))), None)   # the owner's own upload wins
    if own: return own, {"slug": "", "file": os.path.basename(own), "start": 0.0, "level": (edl["audio"]["music"] or {}).get("level", 0.35), "fade_in": 1.0, "fade_out": 1.5}, "owner upload"
    m = edl["audio"]["music"]
    if not m: return None, None, ""
    p = RM.resolve(m["slug"], m["file"])
    if not p: raise ValueError(f"the music {m['slug']}/{m['file']} is not in the NAVAAN library (only published songs of this machine can be used)")
    return p, m, f"{m['slug']}/{m['file']}"


def build(slug, D, edl, tmp, ffmpeg):
    """The ffmpeg command for the whole reel."""
    pr = C.load_json(os.path.join(D, "probe.json"), default={}) or {}; total = edl["seconds"]; segs = edl["segments"]; n = len(segs)
    cmd = [ffmpeg, "-y", "-v", "error", "-i", os.path.join(D, "source.mp4")]
    g = [f"[0:v]split={n}" + "".join(f"[s{i}]" for i in range(n)) if n > 1 else "[0:v]null[s0]"]
    g += [segment_chain(i, s) for i, s in enumerate(segs)]
    g.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vc]" if n > 1 else "[v0]null[vc]")
    g.append("[vc]" + ",".join(grade_filters(edl["grade"])) + "[vg]")
    # text pictures: a scrim, the quote lines, the other text
    cues, author = quote_cues(D, edl)
    layers = []   # (png, start, end)
    if cues or edl["text"]:
        sp = os.path.join(tmp, "scrim.png"); scrim_png(sp); layers.append((sp, 0.0, total, False))
    for i, (t, a, b) in enumerate(cues):
        p = os.path.join(tmp, f"q{i}.png"); text_png(t, edl["quote"]["pos"], p, edl["quote"]["font"], author if i == len(cues) - 1 else ""); layers.append((p, a, b, True))
    for i, x in enumerate(edl["text"]):
        p = os.path.join(tmp, f"t{i}.png"); text_png(x["text"], x["pos"], p, edl["quote"]["font"]); layers.append((p, x["start"], x["end"], True))
    k = 1; cur = "vg"
    for j, (p, a, b, fade) in enumerate(layers):
        cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{total:.2f}", "-i", p]
        if fade:
            fi, fo = 0.35, 0.35
            g.append(f"[{k}:v]format=rgba,fade=t=in:st={a:.2f}:d={fi}:alpha=1,fade=t=out:st={max(a + fi, b - fo):.2f}:d={fo}:alpha=1[l{j}]")
        else:
            g.append(f"[{k}:v]format=rgba[l{j}]")
        g.append(f"[{cur}][l{j}]overlay=0:0:format=auto[o{j}]"); cur = f"o{j}"; k += 1
    g.append(f"[{cur}]fade=t=in:st=0:d=0.3,fade=t=out:st={total - 0.4:.2f}:d=0.4[vout]")
    # sound
    a = edl["audio"]; mix = []
    if pr.get("has_audio") and a["policy"] != "mute":
        g.append(f"[0:a]asplit={n}" + "".join(f"[as{i}]" for i in range(n)) if n > 1 else "[0:a]anull[as0]")
        for i, s in enumerate(segs): g.append(f"[as{i}]atrim=start={s['start']:.3f}:end={s['end']:.3f},asetpts=PTS-STARTPTS[a{i}]")
        g.append("".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[ac]" if n > 1 else "[a0]anull[ac]")
        lvl = 1.0 if a["policy"] == "keep" else a["ambient_level"]
        g.append("[ac]" + ("afftdn=nr=12," if a["policy"] == "denoise" else "") + f"volume={lvl:.2f}[amb]"); mix.append("amb")
    vo = find_voice(D)
    if vo:
        cmd += ["-i", vo]; vi = k; k += 1; ms = int(a["vo_start"] * 1000)
        g.append(f"[{vi}:a]adelay={ms}|{ms},volume={a['voice_level']:.2f},atrim=0:{total:.2f}[vo]")
    mp, mm, mlabel = find_music(slug, D, edl)
    if mp:
        cmd += ["-i", mp]; mi = k; k += 1
        g.append(f"[{mi}:a]atrim=start={mm['start']:.2f}:duration={total + 0.5:.2f},asetpts=PTS-STARTPTS,afade=t=in:d={mm['fade_in']:.2f},afade=t=out:st={max(0.0, total - mm['fade_out']):.2f}:d={mm['fade_out']:.2f},volume={mm['level']:.2f}[mu]")
        if vo:   # the music steps back while the voice speaks
            g.append("[vo]asplit=2[vo1][vo2]"); g.append("[mu][vo2]sidechaincompress=threshold=0.04:ratio=8:attack=20:release=500[mud]"); mix += ["mud", "vo1"]
        else: mix.append("mu")
    elif vo: mix.append("vo")
    if mix:
        g.append("".join(f"[{x}]" for x in mix) + f"amix=inputs={len(mix)}:duration=longest:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,atrim=0:{total:.2f}[aout]")
    cmd += ["-filter_complex", ";".join(g), "-map", "[vout]"] + (["-map", "[aout]", "-c:a", "aac", "-b:a", "192k", "-ar", "44100"] if mix else ["-an"])
    cmd += ["-t", f"{total:.2f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-maxrate", "10M", "-bufsize", "20M", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    return cmd, {"music": mlabel, "voice": bool(vo), "quote_lines": len(cues), "layers": len(layers)}


def validate_out(info):
    errs, warns = [], []
    if (info["width"], info["height"]) != (W, H): errs.append(f"size is {info['width']}x{info['height']}, need {W}x{H}")
    if info["codec"] != "h264": errs.append(f"codec is {info['codec']}, need h264")
    if info["duration"] < E.MIN_OUT - 0.3: errs.append(f"{info['duration']} s is shorter than {E.MIN_OUT} s")
    if info["duration"] > E.MAX_OUT + 0.3: errs.append(f"{info['duration']} s is longer than {E.MAX_OUT} s")
    if not info["has_audio"]: warns.append("no audio track")
    if info["bytes"] > 90 * 1024 * 1024: warns.append("file is over 90 MB")
    return errs, warns


def main(slug):
    D = C.song_dir(slug)
    if not os.path.exists(os.path.join(D, "source.mp4")): sys.exit("navaan: source.mp4 is missing. Run the ingest step first.")
    pr = C.load_json(os.path.join(D, "probe.json"), default={}) or {}
    try: edl = E.validate(C.load_json(os.path.join(D, "edl.json")), float(pr.get("duration") or 0))
    except ValueError as e: sys.exit("navaan: edl.json is not usable: " + str(e))
    ff = C.tool("ffmpeg"); tmp = tempfile.mkdtemp(prefix="reel_", dir=os.path.join(D, ".cache") if os.path.isdir(os.path.join(D, ".cache")) else None)
    out = os.path.join(D, OUT); part = out + ".part.mp4"
    try:
        try: cmd, used = build(slug, D, edl, tmp, ff)
        except ValueError as e: sys.exit("navaan: " + str(e))
        print(f"rendering {edl['seconds']:.1f} s from {len(edl['segments'])} part(s) ...", flush=True)
        try: C.run_ffmpeg(cmd + [part], edl["seconds"], "Rendering the reel")
        except subprocess.CalledProcessError as e:
            if os.path.exists(part): os.remove(part)
            sys.exit(f"navaan: ffmpeg failed ({e.returncode}). The log of this step has the command's error.")
        import inspire_render as R
        info = R.probe(part); errs, warns = validate_out(info)
        for w in warns: print("warning:", w)
        if errs:
            os.remove(part); sys.exit("navaan: render failed checks: " + "; ".join(errs))
        os.replace(part, out)
        t = min(edl["thumb_t"], max(0.0, info["duration"] - 0.3))
        C.run([ff, "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", out, "-frames:v", "1", "-q:v", "2", os.path.join(D, THUMB)])
        json.dump({"checks": "passed" if not warns else "passed with warnings", "warnings": warns, **info, **used, "policy": edl["audio"]["policy"]}, open(os.path.join(D, "render_report.json"), "w"), indent=2)
        print(f"done: {OUT} {info['width']}x{info['height']} {info['duration']}s {info['bytes'] // 1024} KB")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1])
