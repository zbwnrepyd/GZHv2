import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))


def _exec_sql(conn: sqlite3.Connection, rel_path: str) -> None:
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as f:
        conn.executescript(f.read())


class ExportBundleV3Tests(unittest.TestCase):
    def setUp(self):
        fd, self.composition_db = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        fd, self.final_db = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        fd, self.research_db = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.out_dir = tempfile.mkdtemp()
        with sqlite3.connect(self.composition_db) as conn:
            _exec_sql(conn, "db/init_composition_db.sql")
        with sqlite3.connect(self.final_db) as conn:
            _exec_sql(conn, "db/migrations/002_final_fields.sql")
            _exec_sql(conn, "db/migrations/012_v3_final_fields.sql")
        with sqlite3.connect(self.research_db) as conn:
            _exec_sql(conn, "db/init_research_db.sql")
            _exec_sql(conn, "db/migrations/001_research_fields.sql")
            _exec_sql(conn, "db/migrations/009_evidence_items.sql")
            _exec_sql(conn, "db/migrations/010_field_resolution.sql")
            _exec_sql(conn, "db/migrations/011_v3_fields.sql")

    def tearDown(self):
        for path in (self.composition_db, self.final_db, self.research_db):
            if os.path.exists(path):
                os.remove(path)
        if os.path.isdir(self.out_dir):
            import shutil
            shutil.rmtree(self.out_dir)

    def test_v3_export_bundle_creates_markdown_pdf_and_notion_payload(self):
        from repositories.field_repo import upsert_final_field
        from services.card_config_service import create_default_cards_for_company
        from services.export_service import render_export_bundle

        create_default_cards_for_company(self.composition_db, "DemoCo", card_set_key="v3")
        upsert_final_field(self.final_db, "DemoCo", "company_name", "DemoCo", status="confirmed", card_set_key="v3", page_no=1)
        upsert_final_field(self.final_db, "DemoCo", "company_type", "AI 搜索", status="confirmed", card_set_key="v3", page_no=1)
        upsert_final_field(self.final_db, "DemoCo", "market_landscape_summary", "AI 搜索竞争加速。", status="confirmed", card_set_key="v3", page_no=2)

        bundle = render_export_bundle(
            "DemoCo",
            card_set_key="v3",
            composition_db=self.composition_db,
            final_db=self.final_db,
            research_db=self.research_db,
            output_dir=self.out_dir,
        )

        self.assertEqual(len(bundle["pages"]), 8)
        self.assertTrue(os.path.exists(bundle["markdown"]))
        self.assertTrue(os.path.exists(bundle["pdf"]))
        self.assertEqual(bundle["notion"]["type"], "notion_block_tree")
        self.assertEqual(len(bundle["notion"]["children"]), 8)
        with open(bundle["markdown"], encoding="utf-8") as f:
            markdown = f.read()
        self.assertIn("## 1. 封面", markdown)
        self.assertIn("DemoCo", markdown)
        self.assertIn("AI 搜索竞争加速。", markdown)
        with open(bundle["pdf"], "rb") as f:
            self.assertEqual(f.read(4), b"%PDF")


if __name__ == "__main__":
    unittest.main()
