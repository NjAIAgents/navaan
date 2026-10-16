"""Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: seed a throwaway songs folder for the browser checks (NAV-20): songs waiting at the lyrics gate, an inspiration item at the quote gate, and a schedule with a missed and a blocked publish in the current month.

  python3 seed.py <root>      the folder is emptied first, so every run starts the same
"""
import datetime, json, os, shutil, sys

root = os.path.abspath(sys.argv[1])
shutil.rmtree(root, ignore_errors=True)
# The portal keeps this folder's data in schemas of its own in Postgres (named from the folder's path). Wiping the folder alone would leave rows that point at files that are gone,
# so a run on a developer's database starts from nothing too. On a fresh database (CI) there is nothing to drop.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
import analytics_db as _db
try:
    import psycopg
    _c = psycopg.connect(_db._dsn(), autocommit=True)
    os.environ["NAVAAN_ROOT"] = root; import navaan_common as _C   # the stores hash the songs folder's path, so ask the same function
    _names = [_db._pg_schema(_C.songs_root(), _b, True) for _b in ("analytics", "studio", "core", "catalog", "billing", "library")]
    for _n in _names: _c.execute(f'DROP SCHEMA IF EXISTS "{_n}" CASCADE')
    try: _c.execute("DELETE FROM core.schema_migrations WHERE schema_name = ANY(%s)", (_names,))   # the migration record lives in the real core schema; forget what was dropped
    except psycopg.errors.UndefinedTable: pass   # expected: a database that has never been migrated has no record yet
    _c.close()
except Exception as _e: print("could not reset the database schemas:", _e, file=sys.stderr)
songs = os.path.join(root, "songs")


def item(slug, title, meta, files=()):
    d = os.path.join(songs, slug); os.makedirs(d)
    with open(os.path.join(d, "title.txt"), "w", encoding="utf-8") as f: f.write(title + "\n")
    for name, text in files:
        with open(os.path.join(d, name), "w", encoding="utf-8") as f: f.write(text)
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f: json.dump({"slug": slug, **meta}, f)


lyrics = [("lyrics.txt", "Tere hone se\nrang hai\nsab kuch hai\n"), ("style.txt", "warm hindi pop"), ("tags.json", '["pop"]')]
for slug, title in (("song-001", "Draft One"), ("song-004", "Draft Two")):   # one per browser project: each approves its own
    item(slug, title, {"type": "music", "state": "drafted", "history": []}, lyrics)
today = datetime.date.today(); d20 = today.replace(day=20); d27 = today.replace(day=27)
at = lambda d, h: f"{d.isoformat()}T{h:02d}:00:00Z"
item("song-002", "Chaand Banke", {"type": "music", "state": "approved", "approvals": {}, "schedule": {
    "youtube_at": at(d20, 12), "instagram_at": at(d20, 14), "created_at": at(today, 0), "attempts": {}, "missed": {"go_public": 1},
    "blocked": {"publish_instagram": "waiting for approval: instagram_caption"}, "done": False}})
item("insp-001", "Tired of being strong", {"type": "inspiration", "state": "drafted", "approvals": {}, "schedule": {
    "youtube_at": at(d27, 12), "instagram_at": at(d27, 14), "created_at": at(today, 0), "attempts": {}, "missed": {}, "blocked": {}, "done": False}},
     [("quote.json", '{"quote":"Tired of being strong","author":"NAVAAN"}')])

# Published songs with real files in a local folder that stands in for the bucket (NAVAAN_OBJSTORE_DIR): a cover, 20 seconds of audio and timed lyrics. Two have a confirmed licence, one does not.
import subprocess
from PIL import Image, ImageDraw
bucket = os.path.join(root, "bucket"); here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "..", "scripts"))
os.environ.setdefault("NAVAAN_ROOT", root)
LIVE = [("song-010", "Tere Hone Se", "Hindi", "Hindi Romantic", "First Light", True), ("song-011", "Pata Hi Na Chala", "Hindi", "Indie pop", "First Light", True), ("song-012", "From Then to Forever", "English", "Acoustic ballad", None, False)]
mp3 = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=330", "-t", "20", "-c:a", "libmp3lame", "-b:a", "32k", "-f", "mp3", "pipe:1"], capture_output=True, check=True).stdout
for slug, title, lang, genre, album, _ok in LIVE:
    pre = f"navaan/songs/{slug}/"; os.makedirs(os.path.join(bucket, pre))
    im = Image.new("RGB", (900, 900), (23, 36, 58)); d = ImageDraw.Draw(im)
    for i in range(0, 900, 60): d.ellipse((i / 2, i / 3, 450 + i / 2, 450 + i / 3), outline=(214, 180, 119), width=5)
    im.save(os.path.join(bucket, pre, "cover_1x1.png"))
    with open(os.path.join(bucket, pre, "final.mp3"), "wb") as f: f.write(mp3)
    with open(os.path.join(bucket, pre, "caption_timing.json"), "w", encoding="utf-8") as f: json.dump([[1, f"{title}, line one"], [6, f"{title}, line two"], [11, f"{title}, line three"]], f, ensure_ascii=False)
    sizes = {n: os.path.getsize(os.path.join(bucket, pre, n)) for n in ("cover_1x1.png", "final.mp3", "caption_timing.json")}
    item(slug, title, {"type": "music", "state": "published", **({"album": album} if album else {}), "cloud": {"verified": True, "uploaded_at": "2026-10-01T10:00:00Z", "prefix": pre, "objects": {n: {"size": z} for n, z in sizes.items()}}},
         [("lyrics.txt", f"{title}, line one\n{title}, line two\n{title}, line three\n"), ("tags.json", json.dumps({"genre": genre, "language": lang}))])
import catalog_store as K
for slug, *_rest, ok in LIVE:
    K.sync_item(slug)
    if ok: K.set_license(slug, "confirmed", "e2e", "seeded for the browser checks", plan="paid")
open(os.path.join(root, ".seeded"), "w").close()   # the second portal waits for this
print("seeded", sorted(os.listdir(songs)))
