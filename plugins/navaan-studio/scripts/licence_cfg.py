#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-18
Last updated: 2026-10-18
Description: the owner's standing licence statement and whether songs they publish are licence-confirmed automatically.

Only a confirmed track is shown to listeners. Confirming is the owner's decision about rights, so it is never done by a sync on its own: it happens automatically only while this setting is
ON, which the owner switches on in Settings with a statement in their own words ("every song I publish is made on a paid Suno plan"). The statement is what each automatic confirmation
records as its reason, and the track's history says it was the setting that confirmed it. Off by default. Stored in <conf>/licence.json.

  load() -> {"auto", "statement", "plan", "set_by", "set_at"}     save(auto, statement, by) -> the new state     status() -> load() plus the suggested statement for the Settings page
"""
import os, json, datetime
import media_cfg

FILE = "licence.json"
SUGGESTED = "Every song I publish is made on a paid Suno plan and its audio is downloaded through Suno, so I hold the rights to publish it."
MAX_STATEMENT = 400


def _path(): return os.path.join(media_cfg.conf_dir(), FILE)


def load():
    raw = media_cfg._read_json(_path(), {})
    raw = raw if isinstance(raw, dict) else {}
    return {"auto": bool(raw.get("auto")) and bool(str(raw.get("statement") or "").strip()), "statement": str(raw.get("statement") or "").strip()[:MAX_STATEMENT],
            "plan": str(raw.get("plan") or "paid"), "set_by": str(raw.get("set_by") or ""), "set_at": str(raw.get("set_at") or "")}


def save(auto, statement, by):
    """Switch automatic confirmation on or off. Switching it on needs the statement. ValueError with a sentence when it is missing or too long."""
    statement = " ".join(str(statement or "").split())
    if len(statement) > MAX_STATEMENT: raise ValueError(f"The statement is over {MAX_STATEMENT} characters.")
    if auto and not statement: raise ValueError("Write the statement the licences rest on, in your own words, before switching this on.")
    cur = load()
    media_cfg._atomic_write(_path(), json.dumps({"auto": bool(auto), "statement": statement or cur["statement"], "plan": cur["plan"], "set_by": str(by), "set_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}, indent=1))
    return load()


def status():
    return {**load(), "suggested": SUGGESTED}
