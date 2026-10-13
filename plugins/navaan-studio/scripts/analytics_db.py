"""analytics_db.py  small database layer for the NAVAAN analytics collector.

SQLite today. The SQL in analytics_schema.sql and the upserts below use only features Postgres shares (ON CONFLICT ... DO UPDATE,
excluded.col, composite keys), so moving to Postgres later means swapping connect() and the "?" placeholder in PH.

Database file: env NAVAAN_DB, else analytics.db_path in navaan.config.json, else ~/.local/share/navaan/analytics.db (outside the repo,
because it holds comment text and usernames).
"""
import os, re, sqlite3, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "analytics_schema.sql")
SCHEMA_VERSION = 3
PH = "?"  # DB-API placeholder. Postgres drivers use %s.


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
    except SystemExit:
        c = None
    return os.path.expanduser(c) if c else os.path.expanduser("~/.local/share/navaan/analytics.db")


def _statements(sql):
    sql = re.sub(r"^\s*--.*$", "", sql, flags=re.M)
    return [s.strip() for s in sql.split(";") if s.strip()]


# Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS cannot add them to an existing database. (table, column, definition)
ADDED_COLUMNS = (("market_notes", "platform", "TEXT NOT NULL DEFAULT 'any'"),)


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


def connect(path=None, readonly=False):
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
