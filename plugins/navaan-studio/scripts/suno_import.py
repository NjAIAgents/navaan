#!/usr/bin/env python3
"""suno_import.py  bring a song that already exists on Suno into the NAVAAN pipeline. Standard library plus ffmpeg.

  suno_import.py init <suno-url-or-id> [slug]     create the song folder (slug defaults to the next song-NNN), record the Suno link, mark it as an import
  suno_import.py fetch <slug>                     read title, lyrics, style, model, duration and cover from Suno's public song data, no browser (public songs only)
  suno_import.py ingest <slug> --audio FILE [--title T] [--lyrics-file F] [--style-file F] [--model v5] [--cover FILE] [--suno-id ID]
         [--theme T] [--mood M] [--genre G] [--language L]   (fill brief.md)
                                                  copy the browser-collected pieces into the song folder; audio is converted to final.mp3

For a public song, fetch reads the text pieces and the cover over plain HTTPS. The browser part that remains (downloading the audio with the
user's own signed in account, and reading the pieces of a private song) is done by the suno-import skill. This script holds the parts that can be checked: link parsing, folder layout, ffmpeg conversion, meta.json.
Importing spends no Suno credits. The orchestrator then continues with visuals, captions, video and publishing.
"""
import os, re, sys, json, shutil, subprocess, datetime, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import songs_root, song_dir, tool, duration, load_json, cfg

UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SHORT = re.compile(r"^https?://(www\.)?suno\.(com|ai)/s/([A-Za-z0-9_-]{6,40})/?(\?.*)?$")
LONG = re.compile(r"^https?://(www\.)?suno\.(com|ai)/song/")


def resolve_short(url):
    """Best effort: follow the share link redirect and read the song id from the final address. Returns None if Suno blocks it."""
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            m = UUID.search(r.geturl())
            return m.group(0).lower() if m else None
    except Exception:
        return None


def parse_ref(text):
    """Return (song_id or None, canonical_url). Accepts /song/<id> links, a bare id, or a short /s/<code> share link."""
    text = (text or "").strip()
    if SHORT.match(text):
        sid = resolve_short(text.split("?")[0])
        return sid, (f"https://suno.com/song/{sid}" if sid else text.split("?")[0])
    m = UUID.search(text)
    if not m:
        sys.exit("navaan: no Suno song found. Pass a link like https://suno.com/song/<id> or https://suno.com/s/<code>, or the id itself.")
    if "/" in text and not LONG.match(text):
        sys.exit("navaan: that link is not a suno.com song link")
    sid = m.group(0).lower()
    return sid, f"https://suno.com/song/{sid}"


def next_slug():
    root = songs_root(); n = 1
    if os.path.isdir(root):
        nums = [int(m.group(1)) for d in os.listdir(root) if (m := re.match(r"^song-(\d+)$", d))]
        n = max(nums, default=0) + 1
    return f"song-{n:03d}"


def save(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False); open(path, "a").write("\n")


def init(src, slug=None):
    sid, url = parse_ref(src); slug = slug or next_slug()
    if not os.path.isdir(os.path.join(songs_root(), slug)):
        rc = subprocess.call([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "new_song.py"), slug])
        if rc: sys.exit(rc)
    D = song_dir(slug); mp = os.path.join(D, "meta.json"); m = load_json(mp, default={})
    m.update({"source": "suno_import", "suno_url": url, "state": m.get("state") or "draft"})
    if sid: m.setdefault("suno", {})["id"] = sid
    m.setdefault("history", []).append(f"{now()} import started from Suno {sid or url}")
    save(mp, m)
    try: fetch(slug)  # a public song needs no browser for its text and cover
    except Exception as e: print(f"fetch skipped: {e}")
    print(slug)  # last line is the slug so callers can capture it
    return slug


def script_language(text):
    """Best effort language guess from the script of the lyrics, used only when the agent did not pass --language."""
    dev = sum(1 for c in text if "\u0900" <= c <= "\u097f"); lat = sum(1 for c in text if c.isascii() and c.isalpha())
    if dev > lat: return "Devanagari script (Hindi, Maithili or similar), confirm which"
    return "English" if lat else ""


def write_brief(D, m, a):
    """Fill brief.md from what was collected. A brief the user already wrote by hand is left alone."""
    bp = os.path.join(D, "brief.md"); old = open(bp, encoding="utf-8").read() if os.path.exists(bp) else ""
    filled = [l for l in old.splitlines() if ":" in l and l.split(":", 1)[1].strip() and "options:" not in l.split(":", 1)[1] and l.lstrip("- ").split(":")[0] != "Suno model"]
    if filled: return
    rd = lambda n: open(os.path.join(D, n), encoding="utf-8").read().strip() if os.path.exists(os.path.join(D, n)) else ""
    lyrics, style = rd("lyrics.txt"), rd("style.txt")
    model = m.get("suno_model") or ""
    lines = ["# Brief", "", "Imported from Suno, collected automatically." + (f" Source: {m['suno_url']}" if m.get("suno_url") else ""), "",
             f"- Theme or story: {a.theme or ''}", f"- Mood: {a.mood or ''}", f"- Genre: {a.genre or m.get('suno', {}).get('display_tags') or style}",
             f"- Language: {a.language or script_language(lyrics)}", "- References (style only, no copying): ", f"- Suno model: {model}"]
    open(bp, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    if not (a.theme and a.mood): print("note: brief.md has no theme or mood. Add them with --theme and --mood, read from the lyrics, and run ingest again.")


def short_language(text):
    """One word language for the ID3 tag, or empty when unknown."""
    t = (text or "").split("(")[0].split(",")[0].strip()
    return t if t and len(t) < 20 and "confirm" not in t.lower() else ""


def write_tags(D, a, m=None):
    """Fill the blank fields of tags.json from the imported song and the artist profile. Values already set are kept."""
    import datetime
    tp = os.path.join(D, "tags.json"); t = load_json(tp, default={}) if os.path.exists(tp) else {}
    rd = lambda n: open(os.path.join(D, n), encoding="utf-8").read().strip() if os.path.exists(os.path.join(D, n)) else ""
    title = rd("title.txt").splitlines()[0] if rd("title.txt") else ""
    artist = cfg("artist.name") or "NAVAAN"
    genre = a.genre or ((m or {}).get("suno", {}).get("display_tags") or rd("style.txt").split(",")[0]).strip()[:60]
    lang = short_language(a.language) or short_language(script_language(rd("lyrics.txt")))
    want = {"title": title, "artist": artist, "album": title, "album_artist": cfg("artist.album_artist") or artist, "track": "1/1",
            "genre": genre, "label": cfg("artist.label") or "", "year": str(datetime.date.today().year), "language": lang,
            "copyright": cfg("artist.copyright_owner") or "", "comment": cfg("publish.credit_text") or "AI-generated music"}
    for k in ("composer", "lyricist", "isrc"): want.setdefault(k, "")
    for k, v in want.items():
        if not t.get(k): t[k] = v
    json.dump(t, open(tp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


API = "https://studio-api.prod.suno.com/api/clip/"


def clean_title(t):
    """Drop the wrapping quotes and trailing emoji or symbols that Suno titles often carry, keep the words in every script."""
    import unicodedata
    t = "".join(c for c in (t or "") if unicodedata.category(c) not in ("So", "Sk", "Cf") and c != "\ufe0f")
    t = t.replace("\u201c", "").replace("\u201d", "").replace('"', "").strip()
    return re.sub(r"\s+", " ", t)


def fetch(slug, dest=None):
    """Write title.txt, lyrics.txt, style.txt, cover_suno.jpeg and the model into the song folder from Suno's public clip data.
    Returns True when the song is public and the text was collected, False when the agent must read the page in the browser."""
    import urllib.request, urllib.error
    D = dest or song_dir(slug); mp = os.path.join(D, "meta.json"); m = load_json(mp, default={}); sid = m.get("suno", {}).get("id")
    if not sid: print("fetch: no Suno song id in meta.json, the agent reads the page instead"); return False
    try:
        req = urllib.request.Request(API + sid, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r: c = json.load(r)
    except (urllib.error.URLError, ValueError, OSError) as e:
        print(f"fetch: Suno did not return public data ({e}). The song may be private, the agent reads the page instead."); return False
    md = c.get("metadata") or {}; lyrics, style = (md.get("prompt") or "").strip(), (md.get("tags") or "").strip()
    if not c.get("title") or not lyrics:
        print("fetch: the data had no title or lyrics, the agent reads the page instead."); return False
    open(os.path.join(D, "title.txt"), "w", encoding="utf-8").write(clean_title(c["title"]) + "\n")
    open(os.path.join(D, "lyrics.txt"), "w", encoding="utf-8").write(lyrics + "\n")
    open(os.path.join(D, "style.txt"), "w", encoding="utf-8").write(style + "\n")
    img = c.get("image_large_url") or c.get("image_url")
    if img:
        try:
            with urllib.request.urlopen(urllib.request.Request(img, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as r, open(os.path.join(D, "cover_suno.jpeg"), "wb") as f: shutil.copyfileobj(r, f)
        except OSError as e: print(f"fetch: cover not saved ({e})")
    m["suno_model"] = c.get("major_model_version") or c.get("model_name") or ""
    su = m.setdefault("suno", {}); su.update({"duration": round(float(md.get("duration") or c.get("duration")), 1) if (md.get("duration") or c.get("duration")) else su.get("duration"),
                                              "display_tags": c.get("display_tags") or "", "creator": c.get("display_name") or "", "fetched_at": now()})
    m.setdefault("history", []).append(f"{now()} suno text and cover fetched without a browser (model {m['suno_model']})")
    save(mp, m)
    print(f"fetched from Suno: title, lyrics ({len(lyrics)} chars), style ({len(style)} chars), model {m['suno_model']}, cover. Only the audio is left.")
    return True


def ingest(slug, a):
    D = song_dir(slug); mp = os.path.join(D, "meta.json"); m = load_json(mp)
    if m.get("source") != "suno_import":
        sys.exit("navaan: this song was not started with suno_import.py init")
    if not os.path.isfile(a.audio): sys.exit(f"navaan: audio file not found: {a.audio}")
    out = os.path.join(D, "final.mp3"); os.makedirs(os.path.join(D, "takes"), exist_ok=True)
    keep = os.path.join(D, "takes", "imported" + os.path.splitext(a.audio)[1].lower())
    if os.path.abspath(a.audio) != os.path.abspath(keep): shutil.copy2(a.audio, keep)
    if a.audio.lower().endswith(".mp3"): shutil.copy2(a.audio, out)
    else:
        r = subprocess.run([tool("ffmpeg"), "-y", "-v", "error", "-i", a.audio, "-codec:a", "libmp3lame", "-q:a", "2", out])
        if r.returncode: sys.exit("navaan: ffmpeg conversion failed")
    dur = duration(out)
    if dur < 10: sys.exit(f"navaan: audio is only {dur:.1f}s, not a full song. Download again.")
    if a.title: open(os.path.join(D, "title.txt"), "w", encoding="utf-8").write(a.title.strip() + "\n")
    if a.lyrics_file: shutil.copy2(a.lyrics_file, os.path.join(D, "lyrics.txt"))
    if a.style_file: shutil.copy2(a.style_file, os.path.join(D, "style.txt"))
    if a.cover: shutil.copy2(a.cover, os.path.join(D, "cover_suno" + (os.path.splitext(a.cover)[1].lower() or ".jpeg")))
    for need in ("title.txt", "lyrics.txt", "style.txt"):
        if not os.path.exists(os.path.join(D, need)):
            open(os.path.join(D, need), "w", encoding="utf-8").write("")
            print(f"warning: {need} was not collected, it is empty. Fill it in before captions and publishing.")
    if a.model: m["suno_model"] = a.model
    write_brief(D, m, a); write_tags(D, a, m)
    if a.suno_id:
        m["suno_url"] = f"https://suno.com/song/{parse_ref(a.suno_id)[0]}"; m.setdefault("suno", {})["id"] = parse_ref(a.suno_id)[0]
    m.setdefault("suno", {}).update({"duration": round(dur, 1), "imported_at": now()})
    m["sung_lyrics"] = "lyrics.txt"; m["state"] = "generated"
    m.setdefault("history", []).append(f"{now()} imported from Suno: final.mp3 {dur:.1f}s")
    save(mp, m)
    print(f"ingested {slug}: final.mp3 {dur:.1f}s. Next: the listen gate, then visuals.")


def main(argv):
    if len(argv) < 2 or argv[0] not in ("init", "ingest", "fetch"): print(__doc__); return 2
    if argv[0] == "init": init(argv[1], argv[2] if len(argv) > 2 else None); return 0
    if argv[0] == "fetch": return 0 if fetch(argv[1]) else 1
    p = argparse.ArgumentParser(); p.add_argument("slug"); p.add_argument("--audio", required=True)
    for k in ("title", "lyrics-file", "style-file", "model", "cover", "suno-id", "theme", "mood", "genre", "language"): p.add_argument("--" + k)
    ingest(argv[1], p.parse_args(argv[1:])); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
