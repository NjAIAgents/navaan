"""analytics_db.py  small database layer for the NAVAAN analytics collector.

Two backends, one SQL dialect. With NAVAAN_DATABASE_URL set the data lives in Postgres (schema "analytics", migrations in plugins/navaan-studio/db/migrations/analytics,
applied by db_migrate.py); without it, in the SQLite file below. The SQL in analytics_schema.sql and the upserts use only what both share
(ON CONFLICT ... DO UPDATE, excluded.col, composite keys), so the same statements run on either; only connect() differs.
Unsetting the variable is the rollback. NAVAAN_DB_SCHEMA_PER_PATH=1 (the Postgres test run) gives each explicit path its own throwaway schema.

SQLite database file: env NAVAAN_DB, else analytics.db_path in navaan.config.json, else ~/.local/share/navaan/analytics.db (outside the repo,
because it holds comment text and usernames).
"""
import os, re, sqlite3, datetime, hashlib
import navaan_log as L
LOG = L.get("analytics_db")

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "analytics_schema.sql")
SCHEMA_VERSION = 3
def _dsn():
    """NAVAAN_DATABASE_URL, else NAVAAN_PG_HOST and NAVAAN_PG_PASSWORD (environment, or KEY=VALUE lines in ~/.config/navaan/pg.env, the file Vault delivers). Empty means SQLite."""
    if os.environ.get("NAVAAN_DATABASE_URL"): return os.environ["NAVAAN_DATABASE_URL"]
    kv = {k: os.environ[k] for k in ("NAVAAN_PG_HOST", "NAVAAN_PG_PASSWORD") if os.environ.get(k)}
    try:
        with open(os.path.join(os.environ.get("NAVAAN_SECRETS_DIR") or os.path.expanduser("~/.config/navaan"), "pg.env"), encoding="utf-8") as f:
            for line in f:
                k, _, v = line.strip().partition("=")
                if k in ("NAVAAN_PG_HOST", "NAVAAN_PG_PASSWORD") and v and k not in kv: kv[k] = v.strip("'\"")
    except OSError as e: L.ignored(LOG, "no pg.env: Postgres is not switched on, SQLite stays", e)
    if "NAVAAN_PG_HOST" not in kv: return ""
    from urllib.parse import quote
    return f"postgresql://navaan:{quote(kv.get('NAVAAN_PG_PASSWORD', ''), safe='')}@{kv['NAVAAN_PG_HOST']}:5432/navaan"


DSN = _dsn()
PG = bool(DSN)
PH = "?"  # the placeholder in every statement. On Postgres the connection rewrites it to %s (see _qmark), so one SQL text runs on both.


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def db_path(override=None):
    if override:
        return os.path.expanduser(override)
    env = os.environ.get("NAVAAN_DB")
    if env:
        return os.path.expanduser(env)
    try:
        from navaan_common import cfg
        c = cfg("analytics.db_path")
    except SystemExit as _e:
        L.ignored(LOG, "db_path: SystemExit (optional or expected)", _e)
        c = None
    return os.path.expanduser(c) if c else os.path.expanduser("~/.local/share/navaan/analytics.db")


def _statements(sql):
    sql = re.sub(r"^\s*--.*$", "", sql, flags=re.M)
    return [s.strip() for s in sql.split(";") if s.strip()]


# Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS cannot add them to an existing database. (table, column, definition)
ADDED_COLUMNS = (("market_notes", "platform", "TEXT NOT NULL DEFAULT 'any'"),)


def pg_ddl(sql):
    """The SQLite schema as Postgres DDL: 64-bit integers, double precision, and the columns added later. plugins/navaan-studio/db/migrations/analytics/0001_analytics.sql is this output (a test keeps them equal)."""
    out = re.sub(r"\bREAL\b", "DOUBLE PRECISION", re.sub(r"\bINTEGER\b", "BIGINT", sql)).rstrip() + "\n"
    for table, col, ddl in ADDED_COLUMNS:
        out += f"\nALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {ddl};\n"
    return out


def ensure_columns(conn):
    for table, col, ddl in ADDED_COLUMNS:
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}   # SQLite only: Postgres uses information_schema.columns
        if col not in have:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")


def migrate(conn):
    for s in _statements(open(SCHEMA_FILE, encoding="utf-8").read()):
        conn.execute(s)
    ensure_columns(conn)
    conn.execute(f"INSERT INTO schema_version (version, applied_at) SELECT {PH}, {PH} "
                 f"WHERE NOT EXISTS (SELECT 1 FROM schema_version WHERE version = {PH})", (SCHEMA_VERSION, utcnow(), SCHEMA_VERSION))
    conn.commit()


def _qmark(sql):
    """? to %s outside quoted strings, and a literal % to %%, the way psycopg wants it when parameters are passed."""
    parts = re.split(r"('(?:[^']|'')*')", sql)
    return "".join(p if i % 2 else p.replace("%", "%%").replace("?", "%s") for i, p in enumerate(parts))


class Row(dict):
    """A result row: by column name like sqlite3.Row, and by position."""
    def __getitem__(self, k): return super().__getitem__(k) if isinstance(k, str) else list(self.values())[k]


def _row_factory(cursor):
    names = [c.name for c in cursor.description or []]
    return lambda values: Row(zip(names, values))


def _pg_schema(path):
    if path and os.environ.get("NAVAAN_DB_SCHEMA_PER_PATH") == "1":
        return "t_" + hashlib.md5(os.path.abspath(os.path.expanduser(path)).encode()).hexdigest()[:12]
    return "analytics"


def _connect_pg(path, readonly):
    import psycopg, db_migrate

    class Conn(psycopg.Connection):
        def execute(self, query, params=None, **kw):
            # A failed statement must not poison the transaction the way Postgres does by default; SQLite lets the code carry on (a missing optional table, a duplicate).
            # ponytail: a savepoint round trip per statement; fine at this volume, switch to autocommit batches if a collect run gets slow.
            q = _qmark(query) if params is not None and isinstance(query, str) else query
            super().execute("SAVEPOINT stmt")
            try: cur = super().execute(q, params, **kw)
            except Exception:
                super().execute("ROLLBACK TO SAVEPOINT stmt"); raise
            super().execute("RELEASE SAVEPOINT stmt")
            return cur
    class Num(psycopg.adapt.Loader):
        """SUM and AVG come back from Postgres as Decimal; SQLite gave int or float, and the portal turns rows into JSON."""
        def load(self, data):
            t = bytes(data).decode()
            return int(t) if t.lstrip("-").isdigit() else float(t)
    schema = _pg_schema(path)
    # ponytail: one connection per call, no pool; the collectors and the portal open a handful a minute. Add psycopg_pool if that changes.
    if not readonly:
        c = Conn.connect(DSN, row_factory=_row_factory); c.adapters.register_loader("numeric", Num)
        db_migrate.migrate(c, schema, source="analytics")
        c.execute(f'SET search_path TO "{schema}", public')
        c.execute(f"INSERT INTO schema_version (version, applied_at) SELECT {PH}, {PH} WHERE NOT EXISTS (SELECT 1 FROM schema_version WHERE version = {PH})", (SCHEMA_VERSION, utcnow(), SCHEMA_VERSION))
        c.commit()
    else:
        try: c = Conn.connect(DSN, row_factory=_row_factory); c.adapters.register_loader("numeric", Num)
        except psycopg.OperationalError:
            L.soft(LOG, "postgres_unreachable"); return None
        c.read_only = True
        if not c.execute(f'SET search_path TO "{schema}", public').connection.execute("SELECT to_regclass('accounts') IS NOT NULL AS ok").fetchone()["ok"]:
            c.close(); return None   # like a missing SQLite file: nothing has been collected yet
    c.execute(f'SET search_path TO "{schema}", public'); c.commit()
    return c


def connect(path=None, readonly=False):
    if PG: return _connect_pg(path, readonly)
    p = db_path(path)
    if readonly:
        if not os.path.exists(p):
            return None
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=10)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
        conn = sqlite3.connect(p, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    if not readonly:
        migrate(conn)
    return conn


def upsert(conn, table, row, key, keep=(), coalesce=()):
    """Insert row (dict) or update it when the key exists.
    keep: columns never changed after the first insert (first_seen_at, human or Claude tags).
    coalesce: columns updated only when the new value is not NULL (slug)."""
    cols = list(row)
    sets = []
    for c in cols:
        if c in key or c in keep:
            continue
        sets.append(f"{c} = COALESCE(excluded.{c}, {table}.{c})" if c in coalesce else f"{c} = excluded.{c}")
    sql = (f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join([PH] * len(cols))}) "
           f"ON CONFLICT ({', '.join(key)}) DO " + (f"UPDATE SET {', '.join(sets)}" if sets else "NOTHING"))
    conn.execute(sql, [row[c] for c in cols])


# Top level comments from other people that the account has not replied to yet.
UNREPLIED_COUNT_SQL = (
    "SELECT COUNT(*) AS n FROM comments c WHERE c.parent_id IS NULL AND c.is_own = 0 AND c.hidden = 0 "
    "AND c.media_id IN (SELECT media_id FROM media WHERE ig_user_id = " + PH + ") "
    "AND NOT EXISTS (SELECT 1 FROM comments r WHERE r.parent_id = c.comment_id AND r.is_own = 1)")


def rows(conn, sql, params=()):
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn, sql, params=()):
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None
