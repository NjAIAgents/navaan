"""analytics_to_postgres.py  bring the old SQLite analytics history into Postgres, and prove it.

Author: Navjyot Nishant
Created: 2026-10-15
Last updated: 2026-10-15
Description: copy every table of the legacy SQLite analytics file into Postgres in ONE transaction, verified by row count and content checksum, committed only if all match.

Automatic: navaan.py serve calls auto() at start. It does nothing when there is no SQLite file, or Postgres already holds analytics data. Otherwise it copies; a failure raises
SystemExit, so the container never becomes healthy and the release pipeline rolls the image back (the SQLite file is never changed, so the old release still works).
After a good copy the file stays where it is as the rollback copy; delete it by hand once you no longer need it.

Manual:  python3 analytics_to_postgres.py [--sqlite FILE] [--replace] [--dry-run]     (--replace empties the target tables it fills; exit 0 only when every table matches)
Spec 002 SC-001.
"""
import os, sys, sqlite3, hashlib, argparse
import navaan_log as L
LOG = L.get("analytics_to_postgres")


def table_names(lite):
    return [r[0] for r in lite.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall() if r[0] != "schema_version"]


def checksum(rows):
    h = hashlib.sha256()
    for r in sorted(tuple("\x00" if v is None else repr(v) for v in row) for row in rows): h.update("\x1f".join(r).encode("utf-8", "surrogatepass") + b"\x1e")
    return h.hexdigest()[:16]


def pg_has_data(pg, tables):
    for t in tables:
        if pg.execute("SELECT to_regclass(?) IS NOT NULL AS ok", (t,)).fetchone()["ok"] and pg.execute(f"SELECT 1 FROM {t} LIMIT 1").fetchone(): return True
    return False


def copy(lite, pg, replace=False, dry_run=False):
    """Returns (report, ok). Commits only when ok and not dry_run; otherwise rolls everything back."""
    report, ok = [], True
    for t in table_names(lite):
        cols = [r[1] for r in lite.execute(f"PRAGMA table_info({t})").fetchall()]
        rows = lite.execute(f"SELECT {', '.join(cols)} FROM {t}").fetchall()
        if not pg.execute("SELECT to_regclass(?) IS NOT NULL AS ok", (t,)).fetchone()["ok"]:
            report.append((t, len(rows), None, "missing in Postgres")); ok = False; continue
        have = pg.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        if have and not replace and not dry_run: report.append((t, len(rows), have, "target not empty (use --replace)")); ok = False; continue
        if not dry_run:
            if replace: pg.execute(f"DELETE FROM {t}")
            with pg.cursor() as cur, cur.copy(f"COPY {t} ({', '.join(cols)}) FROM STDIN") as cp:
                for r in rows: cp.write_row(r)
        got = [tuple(r.values()) for r in pg.execute(f"SELECT {', '.join(cols)} FROM {t}").fetchall()]
        a, b = checksum(rows), checksum(got)
        match = len(rows) == len(got) and a == b
        ok &= match
        report.append((t, len(rows), len(got), "ok" if match else f"MISMATCH sqlite {a} postgres {b}"))
    if ok and not dry_run: pg.commit()
    else: pg.rollback()
    return report, ok


def show(report, ok):
    w = max([len(r[0]) for r in report] + [5])
    print(f"{'table':<{w}}  {'sqlite':>8}  {'postgres':>8}  result")
    for t, n, m, res in report: print(f"{t:<{w}}  {n:>8}  {'-' if m is None else m:>8}  {res}")
    print("ALL TABLES MATCH" if ok else "NOT VERIFIED: nothing was written")


def auto():
    """Called when the portal starts. Returns what it did: 'no sqlite file', 'already in postgres' or 'copied'. Raises SystemExit if the copy cannot be verified."""
    import analytics_db as db
    src = db.legacy_path()
    if not os.path.exists(src): return "no sqlite file"
    lite = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        tables = table_names(lite)
        try: pg = db.connect()
        except Exception as e:
            L.exc(LOG, "cutover_postgres_unreachable")
            raise SystemExit(f"analytics: there is an old SQLite history at {src} but Postgres is not reachable ({type(e).__name__}). On a dev machine: docker compose -f deploy/compose.dev.yml up -d")
        try:
            if pg_has_data(pg, tables): L.event(LOG, "info", "cutover_skipped", reason="postgres already holds analytics data", sqlite=src); return "already in postgres"
            L.event(LOG, "info", "cutover_started", sqlite=src, tables=len(tables))
            try: report, ok = copy(lite, pg)
            except Exception:   # a value Postgres refuses, a lost connection: the transaction is rolled back, nothing is half written
                pg.rollback(); L.exc(LOG, "cutover_copy_error"); report, ok = [("copy", 0, None, "error, see cutover_copy_error")], False
        finally:
            pg.close()
    finally:
        lite.close()
    if not ok:
        bad = [r for r in report if r[3] != "ok"]
        L.event(LOG, "error", "cutover_failed", tables=[r[0] for r in bad], detail=[r[3] for r in bad])
        raise SystemExit("analytics: the SQLite history could not be copied into Postgres and verified; nothing was written. See the log (cutover_failed). SQLite file untouched: " + src)
    L.event(LOG, "info", "cutover_done", rows=sum(r[1] for r in report), tables=len(report), sqlite=src)
    return "copied"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sqlite", help="SQLite file (default: where the portal kept it)")
    ap.add_argument("--replace", action="store_true", help="empty the target tables before copying")
    ap.add_argument("--dry-run", action="store_true", help="count and compare only, copy nothing")
    a = ap.parse_args(argv)
    L.setup(stdout=False)
    import analytics_db as db
    src = db.legacy_path(a.sqlite)
    if not os.path.exists(src): sys.exit(f"no SQLite file at {src}")
    lite = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    pg = db.connect()
    report, ok = copy(lite, pg, a.replace, a.dry_run)
    show(report, ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
