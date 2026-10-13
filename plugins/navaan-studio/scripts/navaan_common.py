"""Shared helpers for the navaan-studio scripts.

Project root: env NAVAAN_ROOT, else the nearest parent of the current directory that holds a songs/ folder.
Tools: ffmpeg and ffprobe are found on PATH, with common macOS locations as fallback (env NAVAAN_FFMPEG, NAVAAN_FFPROBE override).
Font for captions: env NAVAAN_FONT (path[:index]), else a Devanagari capable system font.
"""
import os, shutil, subprocess, sys, json


def find_root():
    """Workspace folder: env NAVAAN_ROOT, else the nearest parent of the current folder holding navaan.config.json
    (or, for older projects, a songs/ folder), else the current folder."""
    r = os.environ.get("NAVAAN_ROOT")
    if r:
        return os.path.abspath(r)
    start = os.getcwd()
    for marker in ("navaan.config.json", "songs"):
        d = start
        while True:
            if os.path.exists(os.path.join(d, marker)):
                return d
            p = os.path.dirname(d)
            if p == d:
                break
            d = p
    return start


def plugin_dir():
    return os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def plugin_repo_root():
    """Root of the repository that ships this plugin (nearest parent with .git or a marketplace file), or the plugin dir."""
    d = plugin_dir()
    while True:
        if os.path.exists(os.path.join(d, ".git")) or os.path.exists(os.path.join(d, ".claude-plugin", "marketplace.json")):
            return d
        p = os.path.dirname(d)
        if p == d:
            return plugin_dir()
        d = p


def songs_root():
    """Where songs live and are exported: storage.local_dir from the profile (outside the plugin and its repo), else <workspace>/songs."""
    ld = cfg("storage.local_dir")
    return os.path.join(os.path.expanduser(ld), "songs") if ld else os.path.join(find_root(), "songs")


def tool(name):
    env = os.environ.get("NAVAAN_" + name.upper())
    if env:
        return env
    p = shutil.which(name)
    if p:
        return p
    for d in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        if os.path.exists(f"{d}/{name}"):
            return f"{d}/{name}"
    sys.exit(f"navaan: {name} not found. Install ffmpeg or set NAVAAN_{name.upper()}.")


def song_dir(slug):
    d = os.path.join(songs_root(), slug)
    if not os.path.isdir(d):
        sys.exit(f"navaan: no such song folder: {d}")
    return d


def duration(path):
    return float(subprocess.check_output([tool("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                                          "-of", "csv=p=0", path]).strip())


FONT_CANDIDATES = [
    ("/System/Library/Fonts/Kohinoor.ttc", 2),
    ("/System/Library/Fonts/Supplemental/DevanagariMT.ttc", 0),
    ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", 0),
    ("/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf", 0),
    ("C:/Windows/Fonts/Nirmala.ttf", 0),
]


def font(size):
    from PIL import ImageFont
    e = os.environ.get("NAVAAN_FONT") or cfg("captions.font_path") or None
    if e:
        path, _, idx = e.partition(":")
        return ImageFont.truetype(path, size, index=int(idx or 0))
    for path, idx in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size, index=idx)
    sys.exit("navaan: no Devanagari font found. Set NAVAAN_FONT to a .ttf or .ttc file (optionally path:index).")


def run(cmd):
    subprocess.run(cmd, check=True)


def load_json(path, default=None):
    if not os.path.exists(path):
        if default is not None:
            return default
        sys.exit(f"navaan: missing {path}")
    return json.load(open(path, encoding="utf-8"))


def profile():
    """Return navaan.config.json as a dict (empty dict if the artist profile is not set up yet)."""
    p = os.path.join(find_root(), "navaan.config.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def cfg(key, default=None):
    d = profile()
    for part in key.split("."):
        if not isinstance(d, dict) or part not in d:
            return default
        d = d[part]
    return d


GATES = ("lyrics", "suno_download", "listen", "credits", "captions_setup", "media", "publish_youtube", "publish_short", "instagram_caption", "publish_instagram", "cloud_upload", "local_cleanup")


def meta_path(slug):
    return os.path.join(song_dir(slug), "meta.json")


def approved(slug, gate):
    return bool(load_json(meta_path(slug), default={}).get("approvals", {}).get(gate))


def require_approval(slug, gate):
    """Real publishing needs a human approval recorded by navaan.py approve or the web UI. An agent must not write it."""
    if not approved(slug, gate):
        sys.exit(f"navaan: gate '{gate}' is not approved for {slug}. The user approves with: navaan.py approve {slug} {gate}  (or the web UI).")
