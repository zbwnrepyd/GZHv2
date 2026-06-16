#!/usr/bin/env python3
"""SQLite migration runner for project database files."""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_MIGRATIONS_DIR = ROOT / "migrations"


def _ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS schema_migrations (
             version TEXT PRIMARY KEY,
             checksum TEXT NOT NULL,
             applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
           )"""
    )


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _migration_files(migrations_dir: str | os.PathLike, names: list[str] | None = None) -> list[Path]:
    base = Path(migrations_dir)
    if names:
        files = [base / name for name in names]
    else:
        files = sorted(base.glob("*.sql"))
    missing = [str(path) for path in files if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing migration file(s): " + ", ".join(missing))
    return files


def _execute_migration_sql(conn: sqlite3.Connection, sql: str) -> None:
    """Execute a migration script.

    Local development databases may already have columns that were added before
    schema_migrations existed. Treat only duplicate ADD COLUMN as idempotent so
    the rest of the migration, especially indexes, still runs.
    """
    for statement in sql.split(";"):
        stmt = statement.strip()
        if not stmt:
            continue
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            lowered = stmt.lower()
            is_duplicate_add_column = (
                "duplicate column name" in message
                and "alter table" in lowered
                and "add column" in lowered
            )
            if is_duplicate_add_column:
                continue
            raise


def run_migrations(
    db_path: str,
    migrations_dir: str | os.PathLike = DEFAULT_MIGRATIONS_DIR,
    names: list[str] | None = None,
) -> list[str]:
    """Apply pending SQL migrations to one SQLite database and return applied filenames."""
    applied: list[str] = []
    files = _migration_files(migrations_dir, names)
    with sqlite3.connect(db_path) as conn:
        _ensure_migration_table(conn)
        for path in files:
            version = path.name
            sql = path.read_text(encoding="utf-8")
            checksum = _checksum(sql)
            row = conn.execute(
                "SELECT checksum FROM schema_migrations WHERE version=?",
                (version,),
            ).fetchone()
            if row:
                if row[0] != checksum:
                    raise RuntimeError(f"Migration checksum changed after apply: {version}")
                continue
            _execute_migration_sql(conn, sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                (version, checksum),
            )
            applied.append(version)
        conn.commit()
    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply SQLite migrations.")
    parser.add_argument("db_path", help="SQLite database path")
    parser.add_argument(
        "--migrations-dir",
        default=str(DEFAULT_MIGRATIONS_DIR),
        help="Directory containing .sql migration files",
    )
    parser.add_argument(
        "--only",
        action="append",
        dest="names",
        help="Apply only this migration filename. Can be provided multiple times.",
    )
    args = parser.parse_args()
    for version in run_migrations(args.db_path, args.migrations_dir, args.names):
        print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
