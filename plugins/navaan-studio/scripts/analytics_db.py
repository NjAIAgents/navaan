"""analytics_db.py  small database layer for the NAVAAN analytics collector.

Postgres only (spec 002, constitution III): schema "analytics" in the project's own container, migrations in
plugins/navaan-studio/db/migrations/analytics applied by db_migrate.py on connect. The statements are written with "?" placeholders; the connection rewrites them to %s.

Where it connects: see _dsn (NAVAAN_DATABASE_URL, NAVAAN_PG_* or the "database" section of navaan.config.json, as the dedicated role navaan_app). In the container
compose.yml sets the host, user and password file. On a dev machine `docker compose -f deploy/compose.dev.yml up -d` gives the defaults.
The older SQLite file (legacy_path) is only read once, by analytics_to_postgres.auto, to bring its history across.
NAVAAN_DB_SCHEMA_PER_PATH=1 (the tests) gives each explicit path its own throwaway schema.
"""
import os, re, datetime, hashlib
import navaan_log as L
LOG = L.get("analytics_db")

SCHEMA_VERSION = 3
PH = "?"  # the placeholder in every statement; the connection rewrites it (see _qmark)


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _setting(env, key, default=""):
    """Environment first, then the "database" section of navaan.config.json, then the default."""
    if os.environ.get(env): return os.environ[env]
    try:
        from navaan_common import cfg
        v = cfg("database." + key)
    except SystemExit as _e:   # no config file yet
        L.ignored(LOG, "no navaan.config.json: database settings come from the environment and defaults", _e); v = None
    return str(v) if v not in (None, "") else default


def _dsn():
    """NAVAAN_DATABASE_URL wins. Otherwise host, port, name, user and password_file come from NAVAAN_PG_* or the "database" section of navaan.config.json:
        "database": {"host": "navaan-postgres", "port": 5432, "name": "navaan", "user": "navaan_app", "password_file": "/pgsecret/pg_app_password"}
    The config holds the path of the password file, never the password. NAVAAN_PG_PASSWORD (env only) is for a dev machine."""
    if os.environ.get("NAVAAN_DATABASE_URL"): return os.environ["NAVAAN_DATABASE_URL"]
    from urllib.parse import quote
    pw = os.environ.get("NAVAAN_PG_PASSWORD", "")
    pf = _setting("NAVAAN_PG_PASSWORD_FILE", "password_file")
    if not pw and pf:
        try:
            with open(pf, encoding="utf-8") as f: pw = f.read().strip()
        except OSError as e:
            L.exc(LOG, "pg_password_file_unreadable", file=pf); raise SystemExit(f"cannot read the Postgres password file {pf}: {e}")
    user = _setting("NAVAAN_PG_USER", "user", "navaan_app")
    return (f"postgresql://{quote(user, safe='')}{':' + quote(pw, safe='') if pw else ''}@{_setting('NAVAAN_PG_HOST', 'host', '127.0.0.1')}:"
            f"{_setting('NAVAAN_PG_PORT', 'port', '5432')}/{_setting('NAVAAN_PG_DB', 'name', 'navaan')}")


def where():
    """For the API and the command line: what the data lives in (no password)."""
    return "postgres " + re.sub(r"//[^@/]*@", "//", _dsn()).split("//", 1)[-1] + " (schema analytics)"


def legacy_path(override=None):
    """The old SQLite analytics file: env NAVAAN_DB, else analytics.db_path in navaan.config.json, else ~/.local/share/navaan/analytics.db."""
    if override: return os.path.expanduser(override)
    env = os.environ.get("NAVAAN_DB")
    if env: return os.path.expanduser(env)
    try:
        from navaan_common import cfg
        c = cfg("analytics.db_path")
    except SystemExit as _e:
        L.ignored(LOG, "no config file: default location", _e)
        c = None
    return os.path.expanduser(c) if c else os.path.expanduser("~/.local/share/navaan/analytics.db")


def _qmark(sql):
    """? to %s outside quoted strings, and a literal % to %%, the way psycopg wants it when parameters are passed."""
    parts = re.split(r"('(?:[^']|'')*')", sql)
    return "".join(p if i % 2 else p.replace("%", "%%").replace("?", "%s") for i, p in enumerate(parts))


class Row(dict):
    """A result row: by column name, and by position."""
    def __getitem__(self, k): return super().__getitem__(k) if isinstance(k, str) else list(self.values())[k]


def _row_factory(cursor):
    names = [c.name for c in cursor.description or []]
    return lambda values: Row(zip(names, values))


def _pg_schema(path, base="analytics", isolate=None):
    if path and (os.environ.get("NAVAAN_DB_SCHEMA_PER_PATH") == "1" if isolate is None else isolate):
        return "t_" + hashlib.md5(os.path.abspath(os.path.expanduser(path)).encode()).hexdigest()[:12] + ("" if base == "analytics" else "_" + base)
    return base


_MIGRATED = set()


def _dsn_key():
    return re.sub(r"//[^@/]*@", "//", _dsn())


_PROBE = {"analytics": "accounts", "studio": "items"}   # a table whose absence means nothing has been stored yet


def _connection_class():
    import psycopg

    class Conn(psycopg.Connection):
        def execute(self, query, params=None, **kw):
            # A failed statement must not poison the whole transaction the way Postgres does by default: the collectors catch an error (a missing optional table,
            # a duplicate) and carry on. ponytail: a savepoint round trip per statement; fine at this volume, switch to batches if a collect run gets slow.
            q = _qmark(query) if params is not None and isinstance(query, str) else query
            super().execute("SAVEPOINT stmt")
            try: cur = super().execute(q, params, **kw)
            except Exception:
                super().execute("ROLLBACK TO SAVEPOINT stmt"); raise
            super().execute("RELEASE SAVEPOINT stmt")
            return cur

        def run(self, query, params=None):
            """execute without the savepoint, for a plain read whose caller rolls back on any error (two round trips fewer)."""
            return super().execute(_qmark(query) if params is not None and isinstance(query, str) else query, params)

    class Num(psycopg.adapt.Loader):
        """SUM and AVG come back as Decimal; the portal turns rows into JSON, so load them as int or float."""
        def load(self, data):
            t = bytes(data).decode()
            return int(t) if t.lstrip("-").isdigit() else float(t)
    return psycopg, Conn, Num


def connect(path=None, readonly=False, base="analytics", isolate=None):
    """A connection with schema `base` (analytics, or studio for studio_store) first on the search path, migrated up to date. readonly returns None when nothing has been
    stored yet. `path` only matters under NAVAAN_DB_SCHEMA_PER_PATH=1 (tests); in the app it is ignored."""
    import db_migrate
    psycopg, Conn, Num = _connection_class()
    schema = _pg_schema(path, base, isolate)
    # ponytail: one connection per call, no pool; the collectors and the portal open a handful a minute. Add psycopg_pool if that changes.
    try: c = Conn.connect(_dsn(), row_factory=_row_factory)
    except psycopg.OperationalError:
        if readonly: L.soft(LOG, "postgres_unreachable"); return None
        raise
    c.adapters.register_loader("numeric", Num)
    if readonly:
        c.read_only = True
        if not c.execute(f'SET search_path TO "{schema}", public').connection.execute("SELECT to_regclass('" + _PROBE[base] + "') IS NOT NULL AS ok").fetchone()["ok"]:
            c.close(); return None   # nothing has been collected yet
    else:
        if (_dsn_key(), schema) not in _MIGRATED:   # migrate once per process: the portal opens many connections, and the check costs several round trips
            db_migrate.migrate(c, schema, source=base); _MIGRATED.add((_dsn_key(), schema))
        c.execute(f'SET search_path TO "{schema}", public')
        if base == "analytics": c.execute(f"INSERT INTO schema_version (version, applied_at) SELECT {PH}, {PH} WHERE NOT EXISTS (SELECT 1 FROM schema_version WHERE version = {PH})", (SCHEMA_VERSION, utcnow(), SCHEMA_VERSION))
    c.execute(f'SET search_path TO "{schema}", public'); c.commit()
    return c


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
