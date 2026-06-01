import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import db
import asset_store


class FinalCardSaveTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        schema_path = os.path.join(ROOT, "db", "init_final_db.sql")
        with open(schema_path, encoding="utf-8") as f:
            schema = f.read()
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(schema)

    def tearDown(self):
        os.remove(self.db_path)

    def test_save_final_card_updates_existing_field(self):
        db.save_final_card(
            self.db_path,
            "DemoCo",
            1,
            {"company_name": "DemoCo", "company_type": "Agent工具"},
        )
        db.save_final_card(
            self.db_path,
            "DemoCo",
            1,
            {"company_name": "DemoCo AI", "company_type": "AI应用"},
        )

        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT field_name, field_value FROM final_content "
                "WHERE company_name=? AND card_index=? ORDER BY field_name",
                ("DemoCo", 1),
            ).fetchall()

        self.assertEqual(
            rows,
            [("company_name", "DemoCo AI"), ("company_type", "AI应用")],
        )

    def test_get_final_cards_cleans_existing_duplicate_fields(self):
        fd, old_db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(old_db_path) and os.remove(old_db_path))

        with sqlite3.connect(old_db_path) as conn:
            conn.executescript(
                """CREATE TABLE final_content (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     company_name TEXT NOT NULL,
                     card_index INTEGER NOT NULL,
                     field_name TEXT NOT NULL,
                     field_value TEXT,
                     img_local_path TEXT,
                     confirmed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                   );"""
            )
            conn.execute(
                "INSERT INTO final_content (company_name, card_index, field_name, field_value) "
                "VALUES ('DemoCo', 7, 'moat', '旧内容')"
            )
            conn.execute(
                "INSERT INTO final_content (company_name, card_index, field_name, field_value) "
                "VALUES ('DemoCo', 7, 'moat', '新内容')"
            )
            conn.commit()

        cards = db.get_final_cards(old_db_path, "DemoCo")

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["field_value"], "新内容")

    def test_final_status_counts_eight_cards(self):
        db.save_final_markdown(self.db_path, "DemoCo", 8, "## 卡片8：总结\n\n**机遇**：新机会")

        status = db.get_final_status(self.db_path, "DemoCo")

        self.assertEqual(status["confirmed"], [8])
        self.assertEqual(status["total"], 8)


class AssetVariantTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        asset_store.init_assets_db(self.db_path)
        asset_store.ensure_assets_rows(self.db_path, "DemoCo")
        asset_store.ensure_assets_rows(self.db_path, "OtherCo")

    def tearDown(self):
        os.remove(self.db_path)

    def test_select_variant_rejects_variant_from_other_company(self):
        other_variant_id = asset_store.insert_variant(
            self.db_path,
            "OtherCo",
            "office",
            local_path="/images/OtherCo/variants/office.png",
            source_type="import_upload",
        )

        selected = asset_store.select_variant(
            self.db_path,
            "DemoCo",
            "office",
            other_variant_id,
        )

        self.assertFalse(selected)
        demo_asset = asset_store.get_asset(self.db_path, "DemoCo", "office")
        self.assertEqual(demo_asset["status"], "missing")
        self.assertIsNone(demo_asset["local_path"])

    def test_select_variant_normalizes_absolute_image_path_for_browser(self):
        variant_id = asset_store.insert_variant(
            self.db_path,
            "DemoCo",
            "office",
            local_path="/Users/example/project/images/DemoCo/variants/office.png",
            source_type="web_tavily",
        )

        selected = asset_store.select_variant(
            self.db_path,
            "DemoCo",
            "office",
            variant_id,
        )

        self.assertTrue(selected)
        demo_asset = asset_store.get_asset(self.db_path, "DemoCo", "office")
        variants = asset_store.list_variants(self.db_path, "DemoCo", "office")
        self.assertEqual(demo_asset["local_path"], "/images/DemoCo/variants/office.png")
        self.assertEqual(variants[0]["local_path"], "/images/DemoCo/variants/office.png")


if __name__ == "__main__":
    unittest.main()
