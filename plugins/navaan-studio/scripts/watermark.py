#!/usr/bin/env python3
"""watermark.py  the small channel mark burned into every video we make.

text(D)        what to write: video.watermark in the profile when set ("off" turns it off), else the site's address, navaan.online.
drawtext_vf()  an ffmpeg drawtext filter for the paths that do not go through Remotion (a held cover picture, Flow clips), or "" when
               this ffmpeg has no drawtext or no font can be found."""
import os, sys, re, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import navaan_log as L
LOG = L.get("watermark")
DEFAULT = "navaan.online"

FONTS = ("/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf")


def text(D=None):
    v = C.cfg("video.watermark")
    if isinstance(v, str) and v.strip():
        return None if v.strip().lower() in ("off", "none", "no") else v.strip()
    if v is False: return None
    return DEFAULT


def drawtext_vf(D, vertical=False):
    t = text(D)
    if not t: return ""
    font = next((f for f in FONTS if os.path.exists(f)), "")
    if not font: return ""
    try:
        have = subprocess.run([C.tool("ffmpeg"), "-hide_banner", "-filters"], capture_output=True, text=True, timeout=20).stdout
    except Exception as _e:
        L.soft(LOG, "drawtext_vf_error")
        return ""
    if not re.search(r"\bdrawtext\b", have): return ""
    t = t.replace("\\", "").replace(":", "").replace("'", "")
    pos = "x=w*0.045:y=h*0.12" if vertical else "x=w-tw-w*0.025:y=h-th-h*0.04"
    size = "h*0.034*0.5625" if vertical else "h*0.03"   # a vertical frame is 1920 high, but the mark should be as wide as on 16:9
    return f"drawtext=fontfile='{font}':text='{t}':fontcolor=white@0.62:fontsize={size}:shadowcolor=black@0.6:shadowx=1:shadowy=1:{pos}"
