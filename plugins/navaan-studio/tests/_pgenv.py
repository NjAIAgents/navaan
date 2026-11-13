"""Imported first by every test that touches the database: each explicit path gets its own throwaway Postgres schema (the app itself ignores the path).
The database comes from NAVAAN_DATABASE_URL, else the dev defaults (docker compose -f deploy/compose.dev.yml up -d)."""
import os
os.environ.setdefault("NAVAAN_DB_SCHEMA_PER_PATH", "1")


def publish_album(K, slug):
    """Mark an album released straight in the catalog, for tests about what a released album shows (the release itself is tested in test_album_release)."""
    K._tx(lambda c: K._reindex_album(c, str(c.execute("UPDATE albums SET status = 'published' WHERE slug = ? RETURNING id", (slug,)).fetchone()["id"])))
