"""Shared helpers for the navaan-studio scripts.

Project root: env NAVAAN_ROOT, else the nearest parent of the current directory that holds a songs/ folder.
Tools: ffmpeg and ffprobe are found on PATH, with common macOS locations as fallback (env NAVAAN_FFMPEG, NAVAAN_FFPROBE override).
Font for captions: env NAVAAN_FONT (path[:index]), else a Devanagari capable system font.
"""
import os, re, shutil, subprocess, sys, json, time
import navaan_log as L
LOG = L.get("navaan_common")


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
    except OSError as _e: L.ignored(LOG, "load_claude_env: OSError (optional or expected)", _e); pass


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


def lyric_lines(D):
    """The sung lines saved for a song: lyrics.txt without blank lines and [Section] labels. Empty when the song has none (an imported song often has none)."""
    p = os.path.join(D, "lyrics.txt")
    if not os.path.isfile(p): return []
    with open(p, encoding="utf-8", errors="ignore") as f:
        return [l.strip() for l in f if l.strip() and not l.strip().startswith("[")]


NO_LYRICS = "this song has no lyrics saved, so there is nothing to work from. Add the lyrics on the Content tab, then run this step again."


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


# A font with the Latin letters, for text that has no Devanagari: the Devanagari fonts above have digits and punctuation but no a-z, so English text drawn with them
# comes out as boxes (a watermark "@navaan_p5l" showed as boxes, an underscore and a 5). Bold first: small marks and captions need weight.
LATIN_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0), ("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf", 0), ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 0),
    ("/System/Library/Fonts/Helvetica.ttc", 1), ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 0), ("/Library/Fonts/Arial.ttf", 0), ("C:/Windows/Fonts/arialbd.ttf", 0),
]


def has_devanagari(text):
    return any("\u0900" <= ch <= "\u097f" for ch in str(text or ""))


def font_for(text, size):
    """The font for this text: a Devanagari font when the text has Devanagari (it also covers digits and punctuation), else one that has the Latin letters.
    NAVAAN_FONT (or captions.font_path) still wins for everything, as before. Falls back to the Devanagari font when no Latin font is found."""
    from PIL import ImageFont
    if has_devanagari(text) or os.environ.get("NAVAAN_FONT") or cfg("captions.font_path"): return font(size)
    for path, idx in LATIN_FONT_CANDIDATES:
        if os.path.exists(path):
            try: return ImageFont.truetype(path, size, index=idx)
            except OSError: continue   # expected: a font collection without that face, so the next font is tried
    return font(size)


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


SITE = "https://navaan.online"


def with_site_link(text, slug=None, plain=False):
    """A YouTube description or an Instagram caption with the site's address at the end, unless navaan.online is already in it. With a slug it is that song's page on the site
    (a song, which anyone can open once its licence is confirmed); without one, the site itself (an inspiration has no page of its own). plain drops https://, because Instagram does not link a caption."""
    t = str(text or "").rstrip()
    if "navaan.online" in t.lower(): return t
    url = f"{SITE}/app/song/{slug}" if slug else SITE
    line = "Hear the full song free: " + (url.replace("https://", "") if plain else url)
    return (t + "\n\n" if t else "") + line


def published_links(m):
    """Where an item is published, from its meta: [{"where", "url", "privacy", "step"}] for the YouTube video, the Short and the Instagram Reel. `step` is the pipeline step that made it."""
    pub = (m or {}).get("published") or {}; out = []
    for it in pub.get("youtube_items") or []:
        f = os.path.basename(str(it.get("file") or ""))
        short = f.startswith("final_reel") or "short" in f or "/shorts/" in str(it.get("url") or "")
        out.append({"where": "YouTube Short" if short else "YouTube video", "url": it.get("url") or "", "privacy": it.get("privacy") or "", "step": "youtube_short" if short else "publish_youtube"})
    ys = pub.get("youtube_short")
    if isinstance(ys, dict) and ys.get("id"): out.append({"where": "YouTube Short", "url": ys.get("url") or f"https://youtube.com/shorts/{ys['id']}", "privacy": ys.get("privacy") or "", "step": "youtube_short"})
    ig = pub.get("instagram")
    if ig: out.append({"where": "Instagram Reel", "url": ig if str(ig).startswith("http") else "", "privacy": "", "step": "publish_instagram"})
    return out


def write_published(slug):
    """published.json in the item's folder: every place it is published with its link and privacy, rebuilt from meta after each publish step so the stage has a file of its own to show and archive. None when nothing is published."""
    import datetime
    items = published_links(item_load(slug, {}) or {})
    if not items: return None
    p = os.path.join(song_dir(slug), "published.json"); tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump({"updated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "items": [{k: v for k, v in i.items() if k != "step"} for i in items]}, f, indent=2); f.write("\n")
    os.replace(tmp, p); return p


def progress(done, total, label=""):
    """Tell the pipeline how far a long step has got: one line, `PROGRESS done/total label`, that the runner turns into the step's progress bar."""
    print(f"PROGRESS {int(done)}/{int(total)} {label}".rstrip(), flush=True)


def run_ffmpeg(cmd, seconds, label="", base=0, span=100):
    """subprocess.run(cmd, check=True) for an ffmpeg command that reports how far its output has got, as a share of `seconds` of output.
    The share is mapped into the part of the step's bar from base to base+span (out of 100)."""
    p = subprocess.Popen([cmd[0], "-progress", "pipe:1", "-nostats", *cmd[1:]], stdout=subprocess.PIPE, text=True)
    last = -1
    for line in p.stdout:
        if line.startswith("out_time_us=") and seconds > 0:
            try: t = int(line.split("=", 1)[1]) / 1e6
            except ValueError: continue   # expected: ffmpeg prints N/A before the first frame
            pct = base + int(span * min(0.99, max(0.0, t / seconds)))
            if pct != last: last = pct; progress(pct, 100, label)
    rc = p.wait()
    if rc: raise subprocess.CalledProcessError(rc, cmd)


_NO_DEFAULT = object()


def load_json(path, default=_NO_DEFAULT):
    """The parsed file. A missing file exits with a message unless a default is given, and default=None means "return None" (it used to mean
    "no default", so callers that asked for None, like prompt_pack.load and the reel start lookup, exited on a missing file)."""
    if not os.path.exists(path):
        if default is not _NO_DEFAULT:
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


CONTENT_TYPES = ("music", "inspiration", "aha", "explainer")  # every item has one; it picks the pipeline steps, prompts and checks
TYPE_PREFIX = {"music": "song", "inspiration": "insp", "aha": "aha", "explainer": "expl"}
SHORT_TYPES = ("inspiration", "aha")   # short vertical videos made from a few spoken lines over one picture (the inspiration pipeline)
NO_INSTAGRAM = ("aha",)   # The Aha-lorithm (NAV-67) posts YouTube Shorts only


def is_short(t): return t in SHORT_TYPES
def plain(s): return str(s).replace("*", "")   # a script line without its *highlight* marks: what is spoken and timed
TYPE_GATES = {"music": tuple(g for g in GATES if g not in ("quote", "originality")),
              "inspiration": ("quote", "originality", "credits", "media", "publish_youtube", "instagram_caption", "go_public", "publish_instagram", "cloud_upload", "local_cleanup"),
              "aha": ("quote", "originality", "credits", "media", "publish_youtube", "go_public", "cloud_upload", "local_cleanup")}


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
    # a YouTube-only channel (NO_INSTAGRAM) needs only its YouTube login to be configured
    return {"type": ctype, "configured": bool(yt) if ctype in NO_INSTAGRAM else bool(ig and yt), "handle": a.get("instagram_handle", ""), "youtube_channel": a.get("youtube_channel", ""),
            "ig_env": ig, "yt_token": yt, "yt_secret": ys or None, "ig_ready": bool(ig) and os.path.exists(ig) and not same_ig,
            "yt_ready": bool(yt) and os.path.exists(yt) and not same_yt, "same_as_music": same_ig or same_yt}


def meta_path(slug):
    """The write-through export of an item's state. The state itself lives in Postgres (studio_store); read and write it with item_load, item_update, item_save."""
    return os.path.join(song_dir(slug), "meta.json")


def item_load(slug, default=None):
    import studio_store
    return studio_store.load(slug, default)


def item_save(slug, m):
    import studio_store
    studio_store.save(slug, m)


def item_update(slug, fn):
    """Read-modify-write under a row lock: fn(doc) changes the document in place. Use this when a step writes while the web page or the scheduler may too."""
    import studio_store
    return studio_store.update(slug, fn)


def item_exists(slug):
    import studio_store
    return studio_store.exists(slug)


def approved(slug, gate):
    return bool((item_load(slug, {}) or {}).get("approvals", {}).get(gate))


def require_approval(slug, gate):
    """Real publishing needs a human approval recorded by navaan.py approve or the web UI. An agent must not write it."""
    if not approved(slug, gate):
        sys.exit(f"navaan: gate '{gate}' is not approved for {slug}. The user approves with: navaan.py approve {slug} {gate}  (or the web UI).")
