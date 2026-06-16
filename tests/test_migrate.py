import importlib.util
import os
import shutil
import sqlite3
import tempfile
import textwrap
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))


def load_migrate_module():
    module_path = os.path.join(ROOT, "db", "migrate.py")
    spec = importlib.util.spec_from_file_location("gzh_db_migrate", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MigrationRunnerTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(self.db_path) and os.remove(self.db_path))
        self.migrations_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: os.path.isdir(self.migrations_dir) and shutil.rmtree(self.migrations_dir))
        with open(os.path.join(self.migrations_dir, "001_create_demo.sql"), "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(
                """
                CREATE TABLE demo_items (
                  id INTEGER PRIMARY KEY,
                  name TEXT
                );
                """
            ).strip())
        with open(os.path.join(self.migrations_dir, "002_insert_demo.sql"), "w", encoding="utf-8") as f:
            f.write("INSERT INTO demo_items (name) VALUES ('first');")

    def test_run_migrations_records_and_skips_already_applied_files(self):
        migrate = load_migrate_module()

        first = migrate.run_migrations(self.db_path, self.migrations_dir)
        second = migrate.run_migrations(self.db_path, self.migrations_dir)

        self.assertEqual(first, ["001_create_demo.sql", "002_insert_demo.sql"])
        self.assertEqual(second, [])
        with sqlite3.connect(self.db_path) as conn:
            row_count = conn.execute("SELECT COUNT(*) FROM demo_items").fetchone()[0]
            applied = conn.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        self.assertEqual(row_count, 1)
        self.assertEqual([row[0] for row in applied], ["001_create_demo.sql", "002_insert_demo.sql"])

    def test_run_selected_migrations_only_applies_requested_files(self):
        migrate = load_migrate_module()

        applied = migrate.run_migrations(
            self.db_path,
            self.migrations_dir,
            names=["001_create_demo.sql"],
        )

        self.assertEqual(applied, ["001_create_demo.sql"])
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        self.assertEqual(count, 1)

    def test_run_migrations_ignores_duplicate_add_column_but_keeps_indexes(self):
        migrate = load_migrate_module()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE demo_existing (id INTEGER PRIMARY KEY, name TEXT)")
            conn.commit()
        with open(os.path.join(self.migrations_dir, "003_duplicate_column.sql"), "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(
                """
                ALTER TABLE demo_existing ADD COLUMN name TEXT;
                ALTER TABLE demo_existing ADD COLUMN score REAL;
                CREATE INDEX IF NOT EXISTS idx_demo_existing_score
                  ON demo_existing(score);
                """
            ).strip())

        applied = migrate.run_migrations(
            self.db_path,
            self.migrations_dir,
            names=["003_duplicate_column.sql"],
        )

        self.assertEqual(applied, ["003_duplicate_column.sql"])
        with sqlite3.connect(self.db_path) as conn:
            cols = {row[1]: row[2] for row in conn.execute("PRAGMA table_info(demo_existing)")}
            indexes = {row[1] for row in conn.execute("PRAGMA index_list(demo_existing)")}
        self.assertEqual(cols["score"], "REAL")
        self.assertIn("idx_demo_existing_score", indexes)


if __name__ == "__main__":
    unittest.main()
