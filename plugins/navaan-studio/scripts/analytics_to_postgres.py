"""analytics_to_postgres.py  copy the SQLite analytics database into Postgres and prove the copy.

Author: Navjyot Nishant
Created: 2026-10-15
Last updated: 2026-10-15
Description: one-time (repeatable) SQLite to Postgres copy with a per-table row count and content checksum report. Changes nothing in the SQLite file.

  NAVAAN_DATABASE_URL=postgresql://... python3 analytics_to_postgres.py [--sqlite FILE] [--replace] [--dry-run]

The target tables must be empty unless --replace, which empties the tables it is about to fill (and only those). Exit code 0 only when every table's
row count and checksum match, so a cutover script can rely on it. Spec 002 SC-001.
"""
import os, sys, sqlite3, hashlib, argparse, json
import navaan_log as L
LOG = L.get("analytics_to_postgres")


def table_names(lite):
    return [r[0] for r in lite.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]


def checksum(rows):
    h = hashlib.sha256()
    for r in sorted((tuple("\x00" if v is None else repr(v) for v in row) for row in rows)): h.update("\x1f".join(r).encode("utf-8", "surrogatepass") + b"\x1e")
    return h.hexdigest()[:16]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sqlite", help="SQLite file (default: the portal's analytics database)")
    ap.add_argument("--replace", action="store_true", help="empty the target tables before copying")
    ap.add_argument("--dry-run", action="store_true", help="count and compare only, copy nothing")
    a = ap.parse_args(argv)
    if not os.environ.get("NAVAAN_DATABASE_URL"): sys.exit("NAVAAN_DATABASE_URL is not set: nothing to copy into")
    L.setup(stdout=False)
    import analytics_db as db   # imported after the check so it picks Postgres
    src = db.db_path(a.sqlite)
    if not os.path.exists(src): sys.exit(f"no SQLite file at {src}")
    lite = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    pg = db.connect()
    report, ok = [], True
    for t in table_names(lite):
        if t == "schema_version": continue   # the Postgres side writes its own
        cols = [r[1] for r in lite.execute(f"PRAGMA table_info({t})").fetchall()]
        rows = lite.execute(f"SELECT {', '.join(cols)} FROM {t}").fetchall()
        exists = pg.execute("SELECT to_regclass(?) IS NOT NULL AS ok", (t,)).fetchone()["ok"]
        if not exists: report.append((t, len(rows), None, "missing in Postgres")); ok = False; continue
        have = pg.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        if have and not a.replace and not a.dry_run: report.append((t, len(rows), have, "target not empty (use --replace)")); ok = False; continue
        if not a.dry_run:
            if a.replace: pg.execute(f"DELETE FROM {t}")
            with pg.cursor() as cur, cur.copy(f"COPY {t} ({', '.join(cols)}) FROM STDIN") as cp:
                for r in rows: cp.write_row(r)
            pg.commit()
        got = pg.execute(f"SELECT {', '.join(cols)} FROM {t}").fetchall()
        got = [tuple(v for v in (r.values() if hasattr(r, "values") else r)) for r in got]
        a_sum, b_sum = checksum(rows), checksum(got)
        match = len(rows) == len(got) and a_sum == b_sum
        ok &= match
        report.append((t, len(rows), len(got), "ok" if match else f"MISMATCH sqlite {a_sum} postgres {b_sum}"))
    w = max([len(r[0]) for r in report] + [5])
    print(f"{'table':<{w}}  {'sqlite':>8}  {'postgres':>8}  result")
    for t, n, m, res in report: print(f"{t:<{w}}  {n:>8}  {'-' if m is None else m:>8}  {res}")
    L.event(LOG, "info" if ok else "error", "copy_finished", ok=ok, tables=len(report), dry_run=a.dry_run)
    print("ALL TABLES MATCH" if ok else "NOT VERIFIED: see above")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
