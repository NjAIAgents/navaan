"""Shared helpers for the navaan-studio scripts.

Project root: env NAVAAN_ROOT, else the nearest parent of the current directory that holds a songs/ folder.
Tools: ffmpeg and ffprobe are found on PATH, with common macOS locations as fallback (env NAVAAN_FFMPEG, NAVAAN_FFPROBE override).
Font for captions: env NAVAAN_FONT (path[:index]), else a Devanagari capable system font.
"""
import os, re, shutil, subprocess, sys, json, time


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


def headless(): return os.environ.get("NAVAAN_HEADLESS", "0") == "1"  # the server: no local Chrome, so Chrome-driven steps run on the Mac


CLAUDE_STATE = {"problem": "", "at": 0}  # last Claude step outcome: "" ok, "rate_limited" or "expired"


def load_claude_env(conf_dir=None):
    """Pick up the Claude credential delivered from Vault (~/.config/navaan/claude.env: CLAUDE_CODE_OAUTH_TOKEN or ANTHROPIC_API_KEY).
    Read each time a Claude step starts, so a late or renewed token needs no restart. No file: the environment stays as it is."""
    try:
        for line in open(os.path.join(conf_dir or os.path.expanduser("~/.config/navaan"), "claude.env"), encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY") and v.strip(): os.environ[k] = v.strip().strip("\"'")
    except OSError: pass


def note_claude_result(ok, log_tail=""):
    """Remember why a Claude step failed so Settings can say rate limited or expired instead of a bare failure."""
    t = (log_tail or "").lower(); prob = ""
    if not ok:
        if re.search(r"rate.?limit|usage limit|limit reached|too many requests|overloaded|\b429\b", t): prob = "rate_limited"
        elif re.search(r"expired|invalid (api key|token|x-api-key)|authentication|not logged in|/login|\b401\b|unauthorized", t): prob = "expired"
    CLAUDE_STATE.update(problem=prob, at=int(time.time()) if prob else 0)


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


GATES = ("lyrics", "quote", "originality", "suno_download", "listen", "visuals_mode", "shots", "credits", "captions_setup", "media", "publish_youtube", "publish_short", "instagram_caption", "publish_instagram", "cloud_upload", "local_cleanup", "go_public")


CONTENT_TYPES = ("music", "inspiration", "explainer")  # every item has one; it picks the pipeline steps, prompts and checks
TYPE_PREFIX = {"music": "song", "inspiration": "insp", "explainer": "expl"}
TYPE_GATES = {"music": tuple(g for g in GATES if g not in ("quote", "originality")),
              "inspiration": ("quote", "originality", "credits", "media", "publish_youtube", "instagram_caption", "go_public", "publish_instagram", "cloud_upload", "local_cleanup")}


def item_type(m):
    """Content type from a meta dict. Older items have no type and are music."""
    return (m or {}).get("type") or "music"


def type_gates(t): return TYPE_GATES.get(t or "music", TYPE_GATES["music"])


def next_slug(ctype):
    import re
    pre = TYPE_PREFIX[ctype]; n = 0; root = songs_root()
    for d in (os.listdir(root) if os.path.isdir(root) else []):
        m = re.match(rf"^{pre}-(\d+)$", d)
        if m: n = max(n, int(m.group(1)))
    return f"{pre}-{n + 1:03d}"


def account(ctype):
    """Where a content type publishes. Music uses the default NAVAAN login files. Every other type needs its own account in
    navaan.config.json under accounts.<type> ({instagram_handle, youtube_channel, instagram_env, youtube_token, youtube_client_secret}),
    and its login files must differ from the NAVAAN ones, so nothing can land on the wrong channel."""
    home = os.path.expanduser("~/.config/navaan")
    if ctype == "music":
        return {"type": "music", "configured": True, "handle": cfg("publish.instagram_handle", ""), "youtube_channel": "", "ig_env": None, "yt_token": None, "yt_secret": None, "ig_ready": True, "yt_ready": True, "same_as_music": False}
    a = cfg("accounts." + ctype) or {}
    rp = lambda k: os.path.realpath(os.path.expanduser(a[k])) if a.get(k) else ""
    ig, yt, ys = rp("instagram_env"), rp("youtube_token"), rp("youtube_client_secret")
    same_ig = bool(ig) and ig == os.path.realpath(f"{home}/instagram.env"); same_yt = bool(yt) and yt == os.path.realpath(f"{home}/youtube_token.json")
    return {"type": ctype, "configured": bool(ig and yt), "handle": a.get("instagram_handle", ""), "youtube_channel": a.get("youtube_channel", ""),
            "ig_env": ig, "yt_token": yt, "yt_secret": ys or None, "ig_ready": bool(ig) and os.path.exists(ig) and not same_ig,
            "yt_ready": bool(yt) and os.path.exists(yt) and not same_yt, "same_as_music": same_ig or same_yt}


def meta_path(slug):
    return os.path.join(song_dir(slug), "meta.json")


def approved(slug, gate):
    return bool(load_json(meta_path(slug), default={}).get("approvals", {}).get(gate))


def require_approval(slug, gate):
    """Real publishing needs a human approval recorded by navaan.py approve or the web UI. An agent must not write it."""
    if not approved(slug, gate):
        sys.exit(f"navaan: gate '{gate}' is not approved for {slug}. The user approves with: navaan.py approve {slug} {gate}  (or the web UI).")
