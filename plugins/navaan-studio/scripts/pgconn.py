"""pgconn.py  one connection per thread to one schema, and a transaction helper: what each of the store modules needs and used to copy.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: make("billing") returns (conn, tx). A songs folder under the system temp directory (tests) gets its own throwaway schema, so tests never touch real data.
"""
import os, tempfile, threading
import navaan_common as C
import analytics_db as db


def make(base):
    local = threading.local()

    def conn():
        root = C.songs_root()
        c = getattr(local, "conn", None)
        if c is not None and not c.closed and getattr(local, "root", None) == root and c.info.transaction_status != 3: return c
        if c is not None and not c.closed: c.close()
        tmp = os.path.realpath(tempfile.gettempdir())
        local.conn = db.connect(root, base=base, isolate=os.path.realpath(root).startswith(tmp + os.sep)); local.root = root
        return local.conn

    def tx(fn):
        c = conn()
        try: r = fn(c); c.commit(); return r
        except Exception:
            c.rollback(); raise

    def close():
        c = getattr(local, "conn", None)
        if c is not None and not c.closed: c.close()
        local.conn = None
    tx.close = close
    return conn, tx
