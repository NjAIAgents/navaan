"""db_migrate.py  numbered SQL migrations for Postgres.

Author: Navjyot Nishant
Created: 2026-10-15
Last updated: 2026-10-15
Description: apply plugins/navaan-studio/db/migrations/<source>/NNNN_name.sql once each, in order, and record them in core.schema_migrations.

Rules (constitution XIII, plan.md): a migration must work with the previous release's code too, because deploy-run.sh rolls the image back but not the schema.
Destructive changes (drop, rename, tighten) ship one release after the code stops using the old shape. Files are never edited after release; add a new one.
A schema (analytics, later core, catalog ...) has its own folder. Objects in the file are unqualified: the runner sets the search path to the target schema.
"""
import os, re, glob
import navaan_log as L
LOG = L.get("db_migrate")

HERE = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS = os.environ.get("NAVAAN_MIGRATIONS_DIR") or os.path.join(HERE, "..", "db", "migrations")   # plugins/navaan-studio/db/migrations, shipped with the plugin


def migrate(conn, schema, source=None):
    """Apply what is missing for `schema` from the folder `source` (default: the schema's own name). Safe to call concurrently."""
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema): raise ValueError(f"bad schema name {schema!r}")
    folder = os.path.join(MIGRATIONS, source or schema)
    files = sorted(glob.glob(os.path.join(folder, "[0-9][0-9][0-9][0-9]_*.sql")))
    if not files: raise FileNotFoundError(f"no migrations in {folder}")
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('navaan-migrate'))")
    conn.execute("CREATE SCHEMA IF NOT EXISTS core")
    conn.execute("CREATE TABLE IF NOT EXISTS core.schema_migrations (schema_name text NOT NULL, version integer NOT NULL, name text NOT NULL, "
                 "applied_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (schema_name, version))")
    conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    # the schema name was checked above, so it is safe to put in the text; no parameters keeps the runner independent of the connection's placeholder style
    done = {r[0] for r in conn.execute(f"SELECT version FROM core.schema_migrations WHERE schema_name = '{schema}'").fetchall()}
    applied = []
    for f in files:
        name = os.path.basename(f); version = int(name[:4])
        if version in done: continue
        conn.execute(f'SET LOCAL search_path TO "{schema}", public')
        with open(f, encoding="utf-8") as fh: conn.execute(fh.read())
        conn.execute(f"INSERT INTO core.schema_migrations (schema_name, version, name) VALUES ('{schema}', {version}, '{name.replace(chr(39), '')}')")
        applied.append(name)
    conn.commit()
    if applied: L.event(LOG, "info", "migrations_applied", schema=schema, files=applied)
    return applied
