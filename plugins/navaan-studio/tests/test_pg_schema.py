"""NAV-3: the Postgres schema cannot drift from the SQLite one, and the migration runner is safe to repeat. The drift test needs no Postgres."""
import os, sys, sqlite3, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import analytics_db as db

HERE = os.path.dirname(os.path.abspath(__file__))
MIGRATION = os.path.join(HERE, "..", "db", "migrations", "analytics", "0001_analytics.sql")


class Drift(unittest.TestCase):
    def test_the_postgres_migration_is_the_sqlite_schema_translated(self):
        with open(db.SCHEMA_FILE, encoding="utf-8") as f: want = db.pg_ddl(f.read())
        with open(MIGRATION, encoding="utf-8") as f: have = f.read()
        self.assertIn(want, have, "plugins/navaan-studio/db/migrations/analytics/0001_analytics.sql is out of date: regenerate it from analytics_schema.sql with analytics_db.pg_ddl (before release) or add a new migration (after)")

    def test_no_sqlite_only_syntax_in_the_postgres_migration(self):
        with open(MIGRATION, encoding="utf-8") as f: sql = "\n".join(l for l in f.read().splitlines() if not l.lstrip().startswith("--")).upper()   # comments may name what is absent
        for bad in ("AUTOINCREMENT", "PRAGMA", "WITHOUT ROWID", "INSERT OR "): self.assertNotIn(bad, sql)

    def test_question_marks_become_placeholders_outside_quotes_only(self):
        self.assertEqual(db._qmark("SELECT * FROM t WHERE a = ? AND b LIKE '%x?%' AND c = ?"), "SELECT * FROM t WHERE a = %s AND b LIKE '%x?%' AND c = %s")
        self.assertEqual(db._qmark("SELECT 5 % 2, ?"), "SELECT 5 %% 2, %s")


class Dsn(unittest.TestCase):
    def test_pg_env_from_vault_switches_postgres_on_and_its_absence_leaves_sqlite(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"NAVAAN_SECRETS_DIR": d}):
            for k in ("NAVAAN_DATABASE_URL", "NAVAAN_PG_HOST", "NAVAAN_PG_PASSWORD"): os.environ.pop(k, None)
            self.assertEqual(db._dsn(), "")
            with open(os.path.join(d, "pg.env"), "w") as f: f.write("NAVAAN_PG_HOST=navaan-postgres\nNAVAAN_PG_PASSWORD='p@ss/w:rd'\n")
            self.assertEqual(db._dsn(), "postgresql://navaan:p%40ss%2Fw%3Ard@navaan-postgres:5432/navaan")
            os.environ["NAVAAN_DATABASE_URL"] = "postgresql://x/y"
            self.assertEqual(db._dsn(), "postgresql://x/y")


@unittest.skipUnless(db.PG, "needs NAVAAN_DATABASE_URL")
class Runner(unittest.TestCase):
    def test_running_twice_applies_once_and_records_it(self):
        import db_migrate
        c = db.connect(os.path.join(HERE, "runner-test-a.db"))
        try:
            self.assertEqual(db_migrate.migrate(c, db._pg_schema(os.path.join(HERE, "runner-test-a.db")), source="analytics"), [])
            n = c.execute("SELECT COUNT(*) AS n FROM core.schema_migrations WHERE name = '0001_analytics.sql'").fetchone()["n"]
            self.assertGreaterEqual(n, 1)
        finally:
            c.close()

    def test_a_failed_statement_does_not_poison_the_transaction(self):
        c = db.connect(os.path.join(HERE, "runner-test-b.db"))
        try:
            with self.assertRaises(Exception): c.execute("SELECT * FROM no_such_table")
            self.assertEqual(c.execute("SELECT 1 AS one").fetchone()["one"], 1)
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
