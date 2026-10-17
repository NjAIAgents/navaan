#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-17
Last updated: 2026-10-17
Description: clip-and-share: a short vertical video of a song (15 or 30 seconds) for a visitor to share to Instagram or WhatsApp, with the way back to the full song on it.

  make(slug, start, length)   the clip as a file in the cache: the cover, the title, "Hear the full song" and the site over a still picture, the song's audio from `start` with a short fade
  parse(token)                "<slug>-<start>-<length>" back into its parts (the token is the whole recipe, so a clip can be made again if the cache was emptied)

Only a song a visitor may play (published, licence confirmed) can be clipped, only the lengths in LENGTHS, only a start inside the song. The audio is cut in memory from the bucket copy.
"""
import os, re, io, subprocess, tempfile, threading
sys_path = os.path.dirname(os.path.abspath(__file__))
import sys; sys.path.insert(0, sys_path)
import navaan_common as C
import navaan_log as L
import catalog_store as K, media, objstore, poster as P
from PIL import Image, ImageDraw, ImageFilter
from make_cover import latin
LOG = L.get("clip_share")

LENGTHS = (15, 30)
MAX_START = 3600
W, H = 1080, 1920
_LOCK = threading.Lock()   # one clip is cut at a time: a clip is a few seconds of one core, and a crowd must not stack them up
TOKEN = re.compile(r"^([A-Za-z0-9_-]{1,40})-(\d{1,4})-(15|30)$")


def parse(token):
    m = TOKEN.match(token or "")
    if not m: raise ValueError("not a clip link")
    return m.group(1), int(m.group(2)), int(m.group(3))


def token(slug, start, length): return f"{slug}-{int(start)}-{int(length)}"


def cache_dir():
    d = os.path.join(os.environ.get("NAVAAN_CACHE_DIR") or os.path.join(tempfile.gettempdir(), "navaan-cache"), "clips"); os.makedirs(d, exist_ok=True); return d


def path_for(slug, start, length): return os.path.join(cache_dir(), token(slug, start, length) + ".mp4")


def check(slug, start, length):
    if length not in LENGTHS: raise ValueError("a clip is 15 or 30 seconds")
    if not 0 <= int(start) <= MAX_START: raise ValueError("the clip must start inside the song")
    if not K.play_key(slug, confirmed_only=True): raise LookupError("no such song to clip")


def frame(slug, title, artist):
    """The still picture of the clip: the cover blurred as the room, the cover itself, the title, the way back."""
    cov = media.variant(slug, 1280, "jpg"); art = Image.open(io.BytesIO(cov[0])).convert("RGB") if cov else Image.new("RGB", (1280, 1280), (23, 36, 58))
    bg = art.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40)); bg = Image.blend(bg, Image.new("RGB", (W, H), (11, 16, 32)), 0.55)
    side = 880; sq = art.resize((side, side), Image.LANCZOS); bg.paste(sq, ((W - side) // 2, 360))
    d = ImageDraw.Draw(bg)
    P._mark(bg, W // 2, 110, 120)
    f = P._fit(d, title, os.path.join(P.FONTS, P.STYLES["bold"][0]), 96, W - 160, 48)
    P._text(bg, (W // 2, 1400), title, f, (255, 246, 228), "ms")
    d.text((W // 2, 1470), artist.upper(), font=latin(34), fill=P.GOLD, anchor="ms")
    d.text((W // 2, 1640), "Hear the full song", font=latin(46), fill=(255, 246, 228), anchor="ms")
    d.text((W // 2, 1710), "navaan.online", font=latin(38), fill=P.GOLD, anchor="ms")
    return bg


def make(slug, start, length):
    """The clip's mp4 path (made now if it is not in the cache). Raises ValueError, LookupError, RuntimeError."""
    start, length = int(start), int(length); check(slug, start, length)
    out = path_for(slug, start, length)
    if os.path.isfile(out): return out
    with _LOCK:
        if os.path.isfile(out): return out
        t = K.track_view(slug) or {"title": slug}
        key = K.play_key(slug, confirmed_only=True)
        audio = objstore.get(key)
        with tempfile.TemporaryDirectory() as d:
            png = os.path.join(d, "f.png"); frame(slug, t["title"], C.cfg("artist.name") or "NAVAAN").save(png)
            src = os.path.join(d, "a.mp3")
            with open(src, "wb") as f: f.write(audio)
            pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", src], capture_output=True, timeout=60)
            try: whole = float(pr.stdout.decode().strip())
            except ValueError: raise RuntimeError("could not read the song's length") from None
            if start >= whole - 2: raise ValueError("the clip must start before the end of the song (%d seconds long)" % int(whole))
            tmp = out + f".{os.getpid()}.tmp.mp4"
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "25", "-i", png, "-ss", str(start), "-t", str(length), "-i", src,
                                "-map", "0:v:0", "-map", "1:a:0", "-vf", "format=yuv420p", "-af", f"afade=t=in:d=0.4,afade=t=out:st={length - 1.5}:d=1.5", "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
                                "-c:a", "aac", "-b:a", "128k", "-shortest", "-t", str(length), "-movflags", "+faststart", "-f", "mp4", tmp], capture_output=True, timeout=180)
            if r.returncode or not os.path.isfile(tmp) or os.path.getsize(tmp) < 2000:
                if os.path.isfile(tmp): os.remove(tmp)
                raise RuntimeError("could not make the clip: " + r.stderr.decode(errors="replace")[:200])
            os.replace(tmp, out)   # atomic: another request never reads half a file
        L.event(LOG, "info", "clip_made", item=slug, start=start, seconds=length)
    return out
