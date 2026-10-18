#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: the "send this to someone who..." line at the end of a Reel: one short line that names who the song or quote is for, drawn on the last seconds of the finished video.

The line is written to send_line.txt by the quote step (inspirations) or the shot-list step (songs) when the owner has put the "reason to send it" recommendation to work
(a standing rule). If there is no file, nothing is drawn and the video is exactly what it was. It is drawn as a last pass over the finished video, so it works the same whichever
engine rendered it, and the sound is copied, not re-encoded.

  send_line.py <video.mp4> <slug> [--y 0.78] [--seconds 3.2]   draw it on that video in place (does nothing without send_line.txt)
"""
import os, sys, shutil, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C

FILE = "send_line.txt"
MAX_CHARS = 70


def read(D):
    """The line to draw, cleaned to one short line, or "" when there is none."""
    p = os.path.join(D, FILE)
    if not os.path.isfile(p): return ""
    t = " ".join(open(p, encoding="utf-8", errors="ignore").read().split()).strip("\"'“”‘’ ")
    return t[:MAX_CHARS].rstrip(" ,;:-") if t else ""


def make_png(text, W, H, path, y_frac=0.78):
    """A transparent frame with the line centred at y_frac of the height, in the right font for its script, wrapped to two lines when it is long, with a soft shadow so it reads on any picture."""
    from PIL import Image, ImageDraw, ImageFilter
    import caption_clips as CC
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    lines, size = CC.fit_lines(text, 62, W, lambda t, s: d.textlength(t, font=C.font_for(t, s)), limit=0.84)
    lh = round(size * 1.3); y0 = int(H * y_frac) - (len(lines) - 1) * lh // 2
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    for k, ln in enumerate(lines):
        f = C.font_for(ln, size); x = (W - d.textlength(ln, font=f)) / 2; sd.text((x, y0 + k * lh), ln, font=f, fill=(0, 0, 0, 230))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)))
    for k, ln in enumerate(lines):
        f = C.font_for(ln, size); d.text(((W - d.textlength(ln, font=f)) / 2, y0 + k * lh), ln, font=f, fill=(255, 238, 205, 255))
    im.save(path)


def apply(video, D, y_frac=0.78, seconds=3.2):
    """Draw send_line.txt on the last `seconds` of `video`, in place. Returns the line drawn, or "" when there is none (the video is not touched). Raises RuntimeError if the overlay fails, leaving the video as it was."""
    text = read(D)
    if not text: return ""
    import json, subprocess
    pr = subprocess.run([C.tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", video], capture_output=True, text=True)
    j = json.loads(pr.stdout or "{}"); st = (j.get("streams") or [{}])[0]; W, H = int(st.get("width") or 1080), int(st.get("height") or 1920); dur = float((j.get("format") or {}).get("duration") or 0)
    if dur < 3.0: return ""
    start = max(0.5, dur - seconds); tmp = tempfile.mkdtemp(prefix="send_line_")
    try:
        png = os.path.join(tmp, "send.png"); make_png(text, W, H, png, y_frac); out = os.path.join(tmp, "out.mp4")
        fc = f"[1:v]format=rgba,fade=t=in:st={start:.2f}:d=0.6:alpha=1,fade=t=out:st={dur - 0.5:.2f}:d=0.4:alpha=1[s];[0:v][s]overlay=0:0:format=auto,format=yuv420p[v]"
        cmd = [C.tool("ffmpeg"), "-y", "-v", "error", "-i", video, "-loop", "1", "-framerate", "30", "-t", f"{dur:.2f}", "-i", png, "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
               "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", "-t", f"{dur:.2f}", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode or not os.path.getsize(out): raise RuntimeError("the send line could not be drawn: " + (r.stderr.strip().splitlines() or ["ffmpeg failed"])[-1][:160])
        shutil.move(out, video)
    finally: shutil.rmtree(tmp, ignore_errors=True)
    return text


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2: sys.exit(__doc__)
    opt = lambda n, d: float(a[a.index(n) + 1]) if n in a else d
    try: print("drawn:", apply(a[0], C.song_dir(a[1]), opt("--y", 0.78), opt("--seconds", 3.2)) or "no send_line.txt, nothing drawn")
    except RuntimeError as e: sys.exit("navaan: " + str(e))
