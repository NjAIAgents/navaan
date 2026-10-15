"""NAV-3: the Postgres layer. The lint test needs no database; the rest use the throwaway schemas of _pgenv."""
import os, sys, sqlite3, tempfile, unittest, uuid
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import _pgenv  # noqa: F401
import analytics_db as db
import analytics_to_postgres as M

HERE = os.path.dirname(os.path.abspath(__file__))
MIGRATIONS = os.path.join(HERE, "..", "db", "migrations", "analytics")


class Lint(unittest.TestCase):
    def test_migrations_are_numbered_and_have_no_sqlite_only_syntax(self):
        names = sorted(n for n in os.listdir(MIGRATIONS) if n.endswith(".sql"))
        self.assertTrue(names)
        for i, n in enumerate(names, 1): self.assertEqual(n[:4], f"{i:04d}", "migrations are numbered 0001, 0002 ... without gaps")
        for n in names:
            with open(os.path.join(MIGRATIONS, n), encoding="utf-8") as f: sql = "\n".join(l for l in f.read().splitlines() if not l.lstrip().startswith("--")).upper()
            for bad in ("AUTOINCREMENT", "PRAGMA", "WITHOUT ROWID", "INSERT OR ", "TRIGGER"): self.assertNotIn(bad, sql, n)

    def test_question_marks_become_placeholders_outside_quotes_only(self):
        self.assertEqual(db._qmark("SELECT * FROM t WHERE a = ? AND b LIKE '%x?%' AND c = ?"), "SELECT * FROM t WHERE a = %s AND b LIKE '%x?%' AND c = %s")
        self.assertEqual(db._qmark("SELECT 5 % 2, ?"), "SELECT 5 %% 2, %s")


class Dsn(unittest.TestCase):
    ENV = ("NAVAAN_DATABASE_URL", "NAVAAN_PG_HOST", "NAVAAN_PG_PORT", "NAVAAN_PG_DB", "NAVAAN_PG_USER", "NAVAAN_PG_PASSWORD", "NAVAAN_PG_PASSWORD_FILE")

    def clean(self):
        for k in self.ENV: os.environ.pop(k, None)

    NO_CONFIG = staticmethod(lambda: mock.patch("navaan_common.cfg", side_effect=lambda k, d=None: d))   # a developer's own navaan.config.json must not leak into these tests

    def test_defaults_are_the_dev_container_and_the_dedicated_role(self):
        with mock.patch.dict(os.environ), self.NO_CONFIG(): self.clean(); self.assertEqual(db._dsn(), "postgresql://navaan_app@127.0.0.1:5432/navaan")

    def test_environment_and_password_file(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ), self.NO_CONFIG():
            self.clean(); pf = os.path.join(d, "pw")
            with open(pf, "w") as f: f.write("p@ss/w:rd\n")
            os.environ.update(NAVAAN_PG_HOST="navaan-postgres", NAVAAN_PG_PASSWORD_FILE=pf)
            self.assertEqual(db._dsn(), "postgresql://navaan_app:p%40ss%2Fw%3Ard@navaan-postgres:5432/navaan")
            self.assertNotIn("p@ss", db.where())
            os.environ["NAVAAN_DATABASE_URL"] = "postgresql://x/y"; self.assertEqual(db._dsn(), "postgresql://x/y")

    def test_the_database_section_of_navaan_config_json_is_used_and_env_wins(self):
        section = {"host": "cfg-host", "user": "cfg_user", "port": 6543, "name": "cfgdb"}
        with mock.patch.dict(os.environ), mock.patch("navaan_common.cfg", side_effect=lambda k, d=None: section.get(k.split(".", 1)[1], d) if k.startswith("database.") else d):
            self.clean(); self.assertEqual(db._dsn(), "postgresql://cfg_user@cfg-host:6543/cfgdb")
            os.environ["NAVAAN_PG_HOST"] = "env-host"; self.assertIn("@env-host:", db._dsn())


class Runner(unittest.TestCase):
    def test_running_twice_applies_once_and_records_it(self):
        import db_migrate
        p = os.path.join(HERE, "runner-a.db"); c = db.connect(p)
        try:
            self.assertEqual(db_migrate.migrate(c, db._pg_schema(p), source="analytics"), [])
            self.assertGreaterEqual(c.execute("SELECT COUNT(*) AS n FROM core.schema_migrations WHERE name = '0001_analytics.sql'").fetchone()["n"], 1)
        finally: c.close()

    def test_a_failed_statement_does_not_poison_the_transaction(self):
        c = db.connect(os.path.join(HERE, "runner-b.db"))
        try:
            with self.assertRaises(Exception): c.execute("SELECT * FROM no_such_table")
            self.assertEqual(c.execute("SELECT 1 AS one").fetchone()["one"], 1)
        finally: c.close()

    def test_sums_and_averages_come_back_as_plain_numbers(self):
        c = db.connect(os.path.join(HERE, "runner-c.db"))
        try:
            r = c.execute("SELECT SUM(x) AS s, AVG(x) AS a FROM (SELECT 3::bigint AS x UNION ALL SELECT 4::bigint) t").fetchone()
            self.assertEqual((r["s"], r["a"]), (7, 3.5)); self.assertIsInstance(r["s"], int)
        finally: c.close()

    def test_readonly_is_none_until_something_exists(self):
        self.assertIsNone(db.connect(os.path.join(HERE, "never-created.db"), readonly=True))


class Cutover(unittest.TestCase):
    """The first start after the move: the SQLite history is copied, verified, and not copied twice."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.lite = os.path.join(self.tmp.name, "analytics.db")
        c = sqlite3.connect(self.lite)
        c.execute("CREATE TABLE songs (slug TEXT PRIMARY KEY, item_type TEXT, title TEXT, album TEXT, genre TEXT, language TEXT, state TEXT, tags_json TEXT, updated_at TEXT NOT NULL)")
        c.executemany("INSERT INTO songs (slug, title, updated_at) VALUES (?,?,?)", [("song-001", "Pehla", "2026-10-01T00:00:00Z"), ("song-002", "Doosra", "2026-10-02T00:00:00Z")])
        c.commit(); c.close()
        env = mock.patch.dict(os.environ, {"NAVAAN_DB": self.lite}); env.start(); self.addCleanup(env.stop)
        schema = "t_cut_" + uuid.uuid4().hex[:10]
        p = mock.patch.object(db, "_pg_schema", lambda path: schema); p.start(); self.addCleanup(p.stop)

    def count(self):
        c = db.connect()
        try: return c.execute("SELECT COUNT(*) AS n FROM songs").fetchone()["n"]
        finally: c.close()

    def test_copies_once_and_leaves_the_sqlite_file_alone(self):
        self.assertEqual(M.auto(), "copied"); self.assertEqual(self.count(), 2)
        self.assertEqual(M.auto(), "already in postgres"); self.assertEqual(self.count(), 2)
        self.assertTrue(os.path.exists(self.lite))

    def test_no_sqlite_file_means_nothing_to_do(self):
        os.remove(self.lite); self.assertEqual(M.auto(), "no sqlite file")

    def test_a_value_postgres_refuses_stops_the_start_and_writes_nothing(self):
        c = sqlite3.connect(self.lite); c.execute("INSERT INTO songs (slug, title, updated_at) VALUES ('song-003', ?, '2026-10-03T00:00:00Z')", ("bad\x00byte",)); c.commit(); c.close()
        with self.assertRaises(SystemExit) as cm: M.auto()
        self.assertIn("nothing was written", str(cm.exception)); self.assertEqual(self.count(), 0)


if __name__ == "__main__":
    unittest.main()
