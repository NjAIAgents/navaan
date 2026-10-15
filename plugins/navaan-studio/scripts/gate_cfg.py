#!/usr/bin/env python3
"""gate_cfg.py  which approval gates ask you and which approve themselves.

Every gate is ON by default: the pipeline stops and waits for your click. Switching a gate OFF in Settings, Gates, makes the pipeline
approve it by itself when it gets there (the approval is recorded as "auto", so the history shows it). Stored in <conf>/gates.json.
load() -> set of gate ids that are switched off.  save({gate: on}) changes the given gates.  status() -> the list for the Settings page."""
import os, json
import media_cfg
import navaan_common as C

FILE = "gates.json"


def _path(): return os.path.join(media_cfg.conf_dir(), FILE)


def load():
    raw = media_cfg._read_json(_path(), {})
    off = raw.get("off") if isinstance(raw, dict) else []
    return {g for g in (off or []) if g in C.GATES}


def save(updates):
    if not isinstance(updates, dict): raise ValueError("send an object of gate switches")
    off = load()
    for g, on in updates.items():
        if g not in C.GATES: raise ValueError("unknown gate: " + str(g))
        if on: off.discard(g)
        else: off.add(g)
    media_cfg._atomic_write(_path(), json.dumps({"off": [g for g in C.GATES if g in off]}, indent=1))
    return status()


def status():
    off = load()
    return {"gates": [{"id": g, "on": g not in off, "types": [t for t in C.CONTENT_TYPES if g in C.type_gates(t)]} for g in C.GATES]}
