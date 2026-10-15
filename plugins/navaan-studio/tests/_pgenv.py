"""Imported first by every test that touches the database: each explicit path gets its own throwaway Postgres schema (the app itself ignores the path).
The database comes from NAVAAN_DATABASE_URL, else the dev defaults (docker compose -f deploy/compose.dev.yml up -d)."""
import os
os.environ.setdefault("NAVAAN_DB_SCHEMA_PER_PATH", "1")
