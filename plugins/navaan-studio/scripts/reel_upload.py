#!/usr/bin/env python3
"""Author: Navjyot Nishant
Created: 2026-10-19
Last updated: 2026-10-19
Description: receive the footage of a reel as a raw request body, straight to disk in chunks (never in memory, never base64), so a large phone video can be uploaded. The ingest step then shrinks it.

  save(rfile, length, D, filename)   write D/.cache/raw.part, then rename it to raw.<ext> when every byte has arrived; returns the byte count
  Refused(code, message)             what the route sends back (413 too big, 507 no room, 409 already has footage, 400 bad file)

Limits (navaan.config.json): reel.max_upload_mb (default 2048). The free space on the data volume must cover the upload and its shrunk copy.
"""
import os, sys, glob, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import navaan_common as C
import reel_ingest as I

CHUNK = 1024 * 1024
MIN_FREE = 512 * 1024 * 1024   # kept free on top of the upload and its copy


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(message); self.code = code; self.message = message


def check(D, length, filename):
    """Everything that can be refused before a byte is read. Returns the extension."""
    ext = os.path.splitext(str(filename or ""))[1].lower()
    if ext not in I.VIDEO_EXT: raise Refused(400, "that is not a video file (" + ", ".join(I.VIDEO_EXT) + ")")
    if length <= 0: raise Refused(400, "the upload is empty")
    cap = int(C.cfg("reel.max_upload_mb", 2048)) * 1024 * 1024
    if length > cap: raise Refused(413, f"that video is {length // 1048576} MB; the limit is {cap // 1048576} MB")
    if os.path.exists(os.path.join(D, "source.mp4")): raise Refused(409, "this reel already has its footage. Redo the ingest step to start again with a different video.")
    os.makedirs(os.path.join(D, ".cache"), exist_ok=True)
    if shutil.disk_usage(os.path.join(D, ".cache")).free < 2 * length + MIN_FREE: raise Refused(507, "there is not enough free disk space for this video and its working copy")
    return ext


def save(rfile, length, D, filename):
    ext = check(D, length, filename)
    cache = os.path.join(D, ".cache"); part = os.path.join(cache, "raw.part"); got = 0
    try:
        with open(part, "wb") as f:
            while got < length:
                b = rfile.read(min(CHUNK, length - got))
                if not b: raise Refused(400, "the upload stopped before the end; try again")
                f.write(b); got += len(b)
    except Refused:
        if os.path.exists(part): os.remove(part)
        raise
    except OSError as e:
        if os.path.exists(part): os.remove(part)
        raise Refused(507, "could not write the video to disk: " + str(e)) from None
    for old in glob.glob(os.path.join(cache, "raw.*")):
        if old != part: os.remove(old)   # an earlier complete upload that was never shrunk
    os.replace(part, os.path.join(cache, "raw" + ext))
    return got
