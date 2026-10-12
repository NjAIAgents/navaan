#!/usr/bin/env python3
"""setup_profile.py  interactive artist profile setup for NAVAAN Studio.

  python3 setup_profile.py                 ask every question in the terminal, write navaan.config.json
  python3 setup_profile.py --edit          same, with current answers as defaults (press Enter to keep)
  python3 setup_profile.py --questions     print the question list as JSON (for agents that ask in chat)
  python3 setup_profile.py --from FILE     write the config from a JSON answers file (flat or nested)
  python3 setup_profile.py --show          print the current config
  python3 setup_profile.py --check         exit 1 if required answers are missing
  python3 setup_profile.py --verify [--write]  check the local folder and the cloud location (--write also puts and deletes a tiny test object)

Writes navaan.config.json in the workspace folder and regenerates style-notes.md from it.
Never store passwords, cookies or API keys here. The publish approval rule cannot be turned off.
"""
import json, os, sys, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import find_root
import storage


def _default_local():
    d = os.environ.get("NAVAAN_ROOT") or os.getcwd()
    return d if not any(l == "error" for l, _ in storage.check_local(d)) else ""

# key, label, help, kind (text|list|choice|bool|int), default, choices, required
Q = [
 ("storage.local_dir", "Local folder for songs and exports", "Songs are created and exported here while you work. Must be outside the plugin folder and outside its repository. The folder you started your workspace in works well.", "path", _default_local(), None, True),
 ("storage.cloud_provider", "Cloud storage for finished songs", "none keeps everything local. Finished songs are uploaded here only after you approve.", "choice", "none", ["none", "oci", "s3", "gcs"], False),
 ("storage.cloud_bucket", "Cloud bucket name", "Leave empty when the provider is none.", "text", "", None, False),
 ("storage.cloud_prefix", "Cloud folder prefix", "Songs go to <bucket>/<prefix>/<slug>/.", "text", "navaan/songs", None, False),
 ("storage.cloud_region", "Cloud region (optional)", "For S3 for example us-east-2. Leave empty otherwise.", "text", "", None, False),
 ("artist.name", "Artist or channel name", "Shown on every release and in ID3 tags.", "text", "NAVAAN", None, True),
 ("artist.tagline", "One line tagline or bio", "Used in descriptions. Example: Lo-fi love songs in Hindi and Maithili.", "text", "", None, False),
 ("artist.album_artist", "Album artist", "Usually the same as the artist name.", "text", "", None, False),
 ("artist.label", "Label", "Use Independent if you have none.", "text", "Independent", None, False),
 ("artist.copyright_owner", "Copyright owner", "Your legal or stage name for the copyright line.", "text", "", None, True),
 ("artist.country", "Country or home region", "Helps with language and release timing.", "text", "", None, False),
 ("music.languages", "Languages you sing in", "Comma separated. Example: Hindi, Maithili, English, Hinglish.", "list", ["Hindi", "Maithili", "English"], None, True),
 ("music.default_language", "Default language", "Used when a brief does not say.", "text", "Hindi", None, True),
 ("music.genres", "Genres", "Comma separated. Example: Lo-fi, Indie acoustic, Pop, Hip hop.", "list", ["Lo-fi", "Pop"], None, True),
 ("music.moods", "Moods and themes", "Comma separated. Example: love, longing, monsoon, nostalgia.", "list", [], None, False),
 ("music.voice", "Preferred vocals", "Who sings by default.", "choice", "mixed", ["male", "female", "duet", "mixed"], False),
 ("music.avoid", "Words, topics or styles to avoid", "Comma separated. The lyricist will not use these.", "list", [], None, False),
 ("music.reference_feel", "Reference feel (no artist names)", "Describe the sound in words. Example: warm vinyl crackle, soft tabla, breathy vocal.", "text", "", None, False),
 ("suno.model", "Suno model", "Version shown in the Suno model picker.", "text", "v6", None, False),
 ("suno.credit_policy", "Suno credit policy", "ask means confirm before every Create.", "choice", "ask", ["ask", "auto_within_budget"], False),
 ("visual.palette", "Visual palette", "Example: warm amber, deep indigo, soft gold.", "text", "", None, False),
 ("visual.motifs", "Recurring motifs", "Optional recurring hints, comma separated. Each song still picks its own main image from its lyrics.", "list", [], None, False),
 ("visual.mode", "Video style", "story = a music video with characters, places and a shot for each part of the lyrics (needs many Flow credits). loop = one or two abstract clips that repeat (cheap).", "choice", "story", ["story", "loop"], False),
 ("visual.scene_count", "Flow clips per song (loop mode)", "Number of scenes to generate in loop mode. One short clip is enough when it loops. Story mode plans its own shots.", "int", 1, None, False),
 ("visual.look", "Visual look", "Example: modern, minimal, cinematic, neon, soft film. The clip matches the lyrics in this look.", "text", "modern, cinematic", None, False),
 ("visual.flow_model", "Flow video model", "lite is cheapest (10 credits per clip), fast costs 20, quality costs 100. Checked against Flow before each run.", "choice", "lite", ["lite", "fast", "quality"], False),
 ("visual.flow_credit_budget", "Flow credits to spend per song", "Hard cap for one song. 10 buys one short Lite clip for a loop. A story video of a 3 minute song needs roughly 300 to 400 Lite credits, less when chorus shots are reused.", "int", 10, None, False),
 ("captions.enabled", "Burn lyric captions into videos", "Off by default. Timing needs a one time 700 MB download and the render is slow.", "bool", False, None, False),
 ("captions.font_path", "Caption font file (optional)", "Leave empty to auto detect a Devanagari capable font.", "text", "", None, False),
 ("publish.youtube_handle", "YouTube channel handle or URL", "Example: @navaan. Used for links, never for login.", "text", "", None, False),
 ("publish.instagram_handle", "Instagram handle", "Example: @navaan.music. Used for links, never for login.", "text", "", None, False),
 ("publish.playlists", "Playlists by language", "Comma separated language=playlist pairs. Example: Maithili=Maithili Romantic Songs.", "list", [], None, False),
 ("publish.default_hashtags", "Default hashtags", "Comma separated, without #. Example: NAVAAN, LofiMusic.", "list", ["NAVAAN"], None, False),
 ("publish.ai_disclosure", "Mark content as AI generated or altered", "Platforms ask for this when music is AI made. Recommended yes.", "bool", True, None, False),
 ("publish.made_for_kids", "Made for kids", "Almost always no for love songs.", "bool", False, None, False),
 ("publish.credit_text", "Credit text for descriptions", "Example: Lyrics and music by NAVAAN, created with AI assistance (Claude, Suno).", "text", "Lyrics and music by NAVAAN with AI assistance.", None, True),
 ("shorts.default_window_seconds", "Default Short length in seconds", "Keep at 60 or less so YouTube treats it as a Short.", "int", 58, None, False),
]
KINDS = {k: (l, h, t, d, c, r) for k, l, h, t, d, c, r in Q}
LOCKED = {"policy.explicit_approval_for_publish": True, "policy.explicit_approval_for_delete": True, "policy.explicit_approval_for_credits": True}


def get(d, key, default=None):
    for p in key.split("."):
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return d


def put(d, key, val):
    ps = key.split("."); 
    for p in ps[:-1]:
        d = d.setdefault(p, {})
    d[ps[-1]] = val


def path():
    return os.path.join(find_root(), "navaan.config.json")


def load():
    p = path()
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def coerce(kind, raw, choices):
    if kind == "list":
        return raw if isinstance(raw, list) else [x.strip() for x in str(raw).split(",") if x.strip()]
    if kind == "bool":
        if isinstance(raw, bool): return raw
        return str(raw).strip().lower() in ("y", "yes", "true", "1", "on")
    if kind == "int":
        return int(raw)
    if kind == "path":
        return os.path.abspath(os.path.expanduser(str(raw).strip()))
    if kind == "choice":
        v = str(raw).strip().lower()
        if v not in choices: raise ValueError(f"choose one of {choices}")
        return v
    return str(raw).strip()


def show_default(kind, v):
    if kind == "list": return ", ".join(v)
    if kind == "bool": return "yes" if v else "no"
    return "" if v is None else str(v)


def build(answers, base=None):
    cfg = json.loads(json.dumps(base or {}))
    for k, (label, hint, kind, default, choices, req) in KINDS.items():
        flat = answers.get(k, get(answers, k))
        if flat is None:
            if get(cfg, k) is None: put(cfg, k, default)
            continue
        put(cfg, k, coerce(kind, flat, choices))
    if not get(cfg, "artist.album_artist"): put(cfg, "artist.album_artist", get(cfg, "artist.name"))
    for k, v in LOCKED.items(): put(cfg, k, v)
    cfg["version"] = 1
    cfg["updated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return cfg


def missing(cfg):
    return [k for k, (l, h, t, d, c, r) in KINDS.items() if r and get(cfg, k) in (None, "", [])]


def style_notes(cfg):
    g = lambda k: get(cfg, k, "")
    j = lambda k: ", ".join(get(cfg, k, []) or [])
    return f"""# {g('artist.name')} channel defaults

Generated from navaan.config.json. Edit the config (run setup_profile.py --edit), not this file.

- Artist name: {g('artist.name')}
- Tagline: {g('artist.tagline')}
- Album artist: {g('artist.album_artist')}
- Label: {g('artist.label')}
- Copyright owner: {g('artist.copyright_owner')}
- Languages: {j('music.languages')} (default {g('music.default_language')})
- Genres: {j('music.genres')}
- Moods and themes: {j('music.moods')}
- Vocals: {g('music.voice')}
- Reference feel: {g('music.reference_feel')}
- Words and topics to avoid: {j('music.avoid')}
- Visual palette: {g('visual.palette')}
- Motifs: {j('visual.motifs')}
- Video style: {g('visual.mode')}
- Credit text: {g('publish.credit_text')}
"""


def save(cfg):
    p = path()
    json.dump(cfg, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False); open(p, "a").write("\n")
    open(os.path.join(os.path.dirname(p), "style-notes.md"), "w", encoding="utf-8").write(style_notes(cfg))
    return p


def verify(cfg, write=False, create=True):
    """Check the local folder and the cloud location. Returns (ok, lines)."""
    lines, ok = [], True
    for lvl, msg in storage.check_local(get(cfg, "storage.local_dir"), create=create):
        lines.append(f"[{lvl}] local: {msg}"); ok &= lvl != "error"
    for lvl, msg in storage.check_cloud(get(cfg, "storage.cloud_provider", "none"), get(cfg, "storage.cloud_bucket", ""), get(cfg, "storage.cloud_prefix", ""), get(cfg, "storage.cloud_region", ""), write=write):
        lines.append(f"[{lvl}] cloud: {msg}"); ok &= lvl != "error"
    return ok, lines


CLOUD_KEYS = ["storage.cloud_provider", "storage.cloud_bucket", "storage.cloud_prefix", "storage.cloud_region"]


def ask(k, base):
    label, hint, kind, default, choices, req = KINDS[k]
    cur = get(base, k, default)
    while True:
        opt = f" ({'/'.join(choices)})" if choices else ""
        raw = input(f"{label}{opt}{' *' if req else ''}\n  {hint}\n  [{show_default(kind, cur)}]: ").strip()
        if raw == "": val = cur
        elif raw == "-": val = [] if kind == "list" else ("" if kind == "text" else cur)
        else:
            try: val = coerce(kind, raw, choices)
            except ValueError as e: print("  ", e); continue
        if req and val in (None, "", []): print("   required"); continue
        return val


def interactive(base):
    print("NAVAAN Studio artist profile. Press Enter to accept the value in brackets. Type - to clear an optional answer.\n")
    ans = {}
    for k in KINDS:
        if k in CLOUD_KEYS: continue
        while True:
            val = ask(k, base)
            if k != "storage.local_dir": break
            res = storage.check_local(val)
            for lvl, msg in res: print(f"   [{lvl}] {msg}")
            if not any(l == "error" for l, _ in res): break
            print("   Choose another folder.\n"); base = {**base}; put(base, k, "")
        ans[k] = val; print()
        if k == "storage.local_dir":
            while True:  # cloud group, verified with your own CLI login
                for ck in CLOUD_KEYS: ans[ck] = ask(ck, base)
                if ans["storage.cloud_provider"] == "none": print(); break
                print("\nChecking the cloud location ...")
                res = storage.check_cloud(ans["storage.cloud_provider"], ans["storage.cloud_bucket"], ans["storage.cloud_prefix"], ans["storage.cloud_region"])
                for lvl, msg in res: print(f"   [{lvl}] {msg}")
                if not any(l == "error" for l, _ in res): print(); break
                c = input("Retry these answers (r), keep anyway (k) or turn cloud off (o)? [r]: ").strip().lower() or "r"
                if c == "k": print(); break
                if c == "o": ans["storage.cloud_provider"] = "none"; print(); break
                for ck in CLOUD_KEYS: put(base, ck, ans[ck])
    return ans


def main(argv):
    if "--questions" in argv:
        print(json.dumps([{"key": k, "label": l, "help": h, "kind": t, "default": d, "choices": c, "required": r} for k, l, h, t, d, c, r in Q], ensure_ascii=False, indent=2)); return 0
    if "--show" in argv:
        print(json.dumps(load(), ensure_ascii=False, indent=2)); return 0
    if "--verify" in argv:
        ok, lines = verify(load(), write="--write" in argv, create=False); print("\n".join(lines)); return 0 if ok else 1
    if "--check" in argv:
        m = missing(load()); print("missing:", ", ".join(m) if m else "none"); return 1 if m else 0
    if "--from" in argv:
        f = argv[argv.index("--from") + 1]
        cfg = build(json.load(open(f, encoding="utf-8")), load() if "--edit" in argv or os.path.exists(path()) else None)
        m = missing(cfg)
        if m: print("missing required:", ", ".join(m)); return 1
        ok, lines = verify(cfg, write="--verify-write" in argv, create=True)
        print("\n".join(lines))
        if not ok and "--skip-verify" not in argv: print("Not saved. Fix the errors above or pass --skip-verify."); return 1
        print("wrote", save(cfg)); return 0
    if not sys.stdin.isatty():
        print("No terminal. Use --questions to read the list and --from answers.json to write the config."); return 2
    base = load() if ("--edit" in argv or os.path.exists(path())) else {}
    cfg = build(interactive(base), base)
    ok, lines = verify(cfg, create=True); print("\n".join(lines))
    print("wrote", save(cfg)); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
