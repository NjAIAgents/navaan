"""Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: seed a throwaway songs folder for the browser checks (NAV-20): songs waiting at the lyrics gate, an inspiration item at the quote gate, and a schedule with a missed and a blocked publish in the current month.

  python3 seed.py <root>      the folder is emptied first, so every run starts the same
"""
import datetime, json, os, shutil, sys

root = os.path.abspath(sys.argv[1])
shutil.rmtree(root, ignore_errors=True)
songs = os.path.join(root, "songs")


def item(slug, title, meta, files=()):
    d = os.path.join(songs, slug); os.makedirs(d)
    with open(os.path.join(d, "title.txt"), "w", encoding="utf-8") as f: f.write(title + "\n")
    for name, text in files:
        with open(os.path.join(d, name), "w", encoding="utf-8") as f: f.write(text)
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f: json.dump({"slug": slug, **meta}, f)


lyrics = [("lyrics.txt", "Tere hone se\nrang hai\nsab kuch hai\n"), ("style.txt", "warm hindi pop"), ("tags.json", '["pop"]')]
for slug, title in (("song-001", "Tere Hone Se"), ("song-004", "Pata Hi Na Chala")):   # one per browser project: each approves its own
    item(slug, title, {"type": "music", "state": "drafted", "history": []}, lyrics)
today = datetime.date.today(); d20 = today.replace(day=20); d27 = today.replace(day=27)
at = lambda d, h: f"{d.isoformat()}T{h:02d}:00:00Z"
item("song-002", "Chaand Banke", {"type": "music", "state": "approved", "approvals": {}, "schedule": {
    "youtube_at": at(d20, 12), "instagram_at": at(d20, 14), "created_at": at(today, 0), "attempts": {}, "missed": {"go_public": 1},
    "blocked": {"publish_instagram": "waiting for approval: instagram_caption"}, "done": False}})
item("insp-001", "Tired of being strong", {"type": "inspiration", "state": "drafted", "approvals": {}, "schedule": {
    "youtube_at": at(d27, 12), "instagram_at": at(d27, 14), "created_at": at(today, 0), "attempts": {}, "missed": {}, "blocked": {}, "done": False}},
     [("quote.json", '{"quote":"Tired of being strong","author":"NAVAAN"}')])
print("seeded", sorted(os.listdir(songs)))
