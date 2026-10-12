#!/usr/bin/env python3
"""suno_import.py  bring a song that already exists on Suno into the NAVAAN pipeline. Standard library plus ffmpeg.

  suno_import.py init <suno-url-or-id> [slug]     create the song folder (slug defaults to the next song-NNN), record the Suno link, mark it as an import
  suno_import.py ingest <slug> --audio FILE [--title T] [--lyrics-file F] [--style-file F] [--model v5] [--cover FILE] [--duration SEC]
                                                  copy the browser-collected pieces into the song folder; audio is converted to final.mp3

The browser part (opening the Suno song page, reading title, lyrics, style prompt and model, downloading audio and cover) is done by the
suno-import skill. This script holds the parts that can be checked: link parsing, folder layout, ffmpeg conversion, meta.json.
Importing spends no Suno credits. The orchestrator then continues with visuals, captions, video and publishing.
"""
import os, re, sys, json, shutil, subprocess, datetime, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from navaan_common import songs_root, song_dir, tool, duration, load_json

UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
now = lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_id(text):
    m = UUID.search(text or "")
    if not m:
        sys.exit("navaan: no Suno song id found. Pass a link like https://suno.com/song/<id> or the id itself.")
    if "/" in text and not re.search(r"(^|//)(www\.)?suno\.(com|ai)/", text):
        sys.exit("navaan: that link is not on suno.com")
    return m.group(0).lower()


def next_slug():
    root = songs_root(); n = 1
    if os.path.isdir(root):
        nums = [int(m.group(1)) for d in os.listdir(root) if (m := re.match(r"^song-(\d+)$", d))]
        n = max(nums, default=0) + 1
    return f"song-{n:03d}"


def save(path, obj):
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False); open(path, "a").write("\n")


def init(src, slug=None):
    sid = parse_id(src); slug = slug or next_slug()
    if not os.path.isdir(os.path.join(songs_root(), slug)):
        rc = subprocess.call([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "new_song.py"), slug])
        if rc: sys.exit(rc)
    D = song_dir(slug); mp = os.path.join(D, "meta.json"); m = load_json(mp, default={})
    m.update({"source": "suno_import", "suno_url": f"https://suno.com/song/{sid}", "state": m.get("state") or "draft"})
    m.setdefault("suno", {})["id"] = sid
    m.setdefault("history", []).append(f"{now()} import started from Suno song {sid}")
    save(mp, m)
    print(slug)  # last line is the slug so callers can capture it
    return slug


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
    m.setdefault("suno", {}).update({"duration": round(dur, 1), "imported_at": now()})
    m["sung_lyrics"] = "lyrics.txt"; m["state"] = "generated"
    m.setdefault("history", []).append(f"{now()} imported from Suno: final.mp3 {dur:.1f}s")
    save(mp, m)
    print(f"ingested {slug}: final.mp3 {dur:.1f}s. Next: the listen gate, then visuals.")


def main(argv):
    if len(argv) < 2 or argv[0] not in ("init", "ingest"): print(__doc__); return 2
    if argv[0] == "init": init(argv[1], argv[2] if len(argv) > 2 else None); return 0
    p = argparse.ArgumentParser(); p.add_argument("slug"); p.add_argument("--audio", required=True)
    for k in ("title", "lyrics-file", "style-file", "model", "cover"): p.add_argument("--" + k)
    ingest(argv[1], p.parse_args(argv[1:])); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
