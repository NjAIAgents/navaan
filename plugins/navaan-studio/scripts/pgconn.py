"""pgconn.py  one connection per thread to one schema, and a transaction helper: what each of the store modules needs and used to copy.

Author: Navjyot Nishant
Created: 2026-10-16
Last updated: 2026-10-16
Description: make("billing") returns (conn, tx). A songs folder under the system temp directory (tests) gets its own throwaway schema, so tests never touch real data.
"""
import os, tempfile, threading
import navaan_common as C
import analytics_db as db
import navaan_log as L
LOG = L.get("pgconn")


_LOCALS = []   # every thread-local that holds a connection, so a request thread can let go of all of them


def register(local):
    """Add a threading.local with a .conn to the set release_thread() closes (the other stores use their own, not made by make())."""
    if local not in _LOCALS: _LOCALS.append(local)
    return local


def release_thread():
    """Close this thread's database connections. The portal runs one thread per request: without this each request leaves its connections open until the garbage collector finds them,
    and a few busy seconds (a page load is six requests at once) can use up the database's connection limit."""
    for local in _LOCALS:
        c = getattr(local, "conn", None)
        if c is not None:
            local.conn = None
            try:
                if not c.closed: c.close()
            except Exception: L.exc(LOG, "connection_close_failed")   # a connection that cannot be closed is already gone


def make(base):
    local = register(threading.local())

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
