"""media.py  what listeners get of a track's files: cover pictures in several sizes, and a short audio preview.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: NAV-6 stage 2 (FR-009, FR-025). The original lives in the bucket (catalog.assets); a picture is resized on the first request, kept in a cache folder, and served with a long
cache lifetime and an ETag, so a browser asks once and a CDN can hold it. The preview is the first 30 seconds of the audio, cut once and stored back in the bucket as its own asset.

Rules
  only sizes in SIZES and formats in FORMATS exist, so a request cannot make the cache grow without bound
  a cached file is named by the asset id, its size in bytes, the size and the format: replacing the original (a new size in bytes) makes new names, old ones are never served for it
  the first resize also records the original's width, height and dominant colour on its asset row (the colour shows while the picture loads)
"""
import os, io, hashlib, subprocess, tempfile
import navaan_common as C
import navaan_log as L
import catalog_store as K
import objstore
LOG = L.get("media")

SIZES = (320, 640, 1280)
FORMATS = {"webp": ("WEBP", "image/webp", {"quality": 82, "method": 4}), "avif": ("AVIF", "image/avif", {"quality": 60}), "jpg": ("JPEG", "image/jpeg", {"quality": 85, "optimize": True})}
PREVIEW_S = 30


def cache_dir():
    d = os.path.join(os.environ.get("NAVAAN_CACHE_DIR") or os.path.join(tempfile.gettempdir(), "navaan-cache"), "img")
    os.makedirs(d, exist_ok=True)
    return d


def dominant_colour(im):
    """The average colour of the picture as #rrggbb: what the page paints first."""
    r, g, b = im.convert("RGB").resize((1, 1)).getpixel((0, 0))
    return f"#{r:02x}{g:02x}{b:02x}"


def _original(asset):
    """The picture file: the local copy while the studio still has it, else the bucket."""
    local = os.path.join(C.song_dir(asset["slug"]), os.path.basename(asset["storage_key"]))
    if os.path.isfile(local) and os.path.getsize(local) == asset["bytes"]:
        with open(local, "rb") as f: return f.read()
    return objstore.get(asset["storage_key"])


def variant(slug, size, fmt):
    """(bytes, etag, mime) of a cover in one size and format, or None when there is no such cover. Raises ValueError for a size or format that does not exist."""
    if size not in SIZES or fmt not in FORMATS: raise ValueError("no such size or format")
    a = K.cover_asset(slug)
    if not a: return None
    name = f"{a['id']}-{a['bytes']}-{size}.{fmt}"; path = os.path.join(cache_dir(), name)
    etag = '"' + hashlib.sha1(name.encode()).hexdigest()[:20] + '"'
    mime = FORMATS[fmt][1]
    if os.path.isfile(path):
        with open(path, "rb") as f: return f.read(), etag, mime
    from PIL import Image
    im = Image.open(io.BytesIO(_original(a)))
    im.load()
    if not a.get("dominant_colour"): K.set_cover_facts(a["id"], im.width, im.height, dominant_colour(im))
    out = im.convert("RGB"); out.thumbnail((size, size), Image.LANCZOS)
    pil, _, opts = FORMATS[fmt]; buf = io.BytesIO(); out.save(buf, pil, **opts)
    data = buf.getvalue(); tmp = path + f".{os.getpid()}.tmp"
    with open(tmp, "wb") as f: f.write(data)
    os.replace(tmp, path)   # atomic: another request never reads half a file
    return data, etag, mime


def cut_preview(audio, seconds=PREVIEW_S):
    """The first `seconds` of an audio file as a 96 kbit mp3 with a short fade out. Audio only: the cover picture and tags a song's mp3 carries are left out (they doubled the size)."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-map", "0:a:0", "-vn", "-map_metadata", "-1", "-t", str(seconds), "-af", f"afade=t=out:st={seconds - 3}:d=3", "-c:a", "libmp3lame", "-b:a", "96k", "-f", "mp3", "pipe:1"],
                       input=audio, capture_output=True, timeout=120)
    if p.returncode or not p.stdout: raise RuntimeError("ffmpeg could not cut the preview: " + p.stderr.decode(errors="replace")[:200])
    return p.stdout


def ensure_preview(slug):
    """The storage key of the track's 30 second preview, cutting and storing it first if it does not exist yet."""
    have = K.preview_asset(slug)
    if have: return have["storage_key"]
    a = K.audio_asset(slug)
    if not a: raise LookupError("this track has no audio in the bucket")
    key = a["storage_key"].rsplit("/", 1)[0] + "/derived/preview-30s.mp3"
    data = cut_preview(objstore.get(a["storage_key"]))
    objstore.put(key, data, "audio/mpeg")
    K.add_preview_asset(a["id"], a["owner_id"], key, len(data))
    L.event(LOG, "info", "preview_made", item=slug, bytes=len(data))
    return key
