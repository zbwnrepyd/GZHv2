import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import db
import asset_store


class ResearchScoringSaveTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        schema_path = os.path.join(ROOT, "db", "init_research_db.sql")
        with open(schema_path, encoding="utf-8") as f:
            schema = f.read()
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(schema)

    def tearDown(self):
        os.remove(self.db_path)

    def test_save_research_records_persists_competitive_scores(self):
        db.save_research_records(
            self.db_path,
            [
                {
                    "company_name": "DemoCo",
                    "version": "standard",
                    "funding_info": "Series A $15M",
                    "ai_model_dependency": "multi_model",
                    "workflow_integration_level": "workflow_embedded",
                    "data_flywheel": "partial",
                    "proprietary_data_asset": "yes_supplementary",
                    "incumbent_direct_competitor": "other",
                    "customer_segment_type": "b2b_enterprise",
                    "pricing_model": "enterprise_contract",
                    "inference_cost_exposure": "low",
                    "stack_layer": "vertical_app",
                }
            ],
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT funding_stage, funding_stage_score, score_defensibility, "
                "score_incumbent_attention, score_value_capture, stack_layer "
                "FROM research WHERE company_name='DemoCo'"
            ).fetchone()

        self.assertEqual(row["funding_stage"], "series_a")
        self.assertEqual(row["funding_stage_score"], 5)
        self.assertAlmostEqual(row["score_defensibility"], 5.6)
        self.assertAlmostEqual(row["score_incumbent_attention"], 6.2)
        self.assertAlmostEqual(row["score_value_capture"], 7.45)
        self.assertEqual(row["stack_layer"], "vertical_app")

    def test_company_list_exposes_scores_for_charting(self):
        db.save_research_records(
            self.db_path,
            [
                {
                    "company_name": "ChartCo",
                    "version": "standard",
                    "company_type": "AI 应用",
                    "funding_info": "Seed $5M",
                    "stack_layer": "middleware",
                }
            ],
        )

        companies = db.get_companies(self.db_path)

        self.assertEqual(companies[0]["category"], "AI 应用")
        self.assertEqual(companies[0]["funding_stage"], "seed")
        self.assertEqual(companies[0]["funding_stage_score"], 3)
        self.assertEqual(companies[0]["stack_layer"], "middleware")
        self.assertIn("score_defensibility", companies[0])

    def test_company_list_uses_final_fields_progress_when_available(self):
        fd, final_db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(final_db_path) and os.remove(final_db_path))
        with sqlite3.connect(final_db_path) as conn:
            with open(os.path.join(ROOT, "db", "migrations", "002_final_fields.sql"), encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.executemany(
                "INSERT INTO final_fields (company_name, field_key, final_value, status) VALUES (?, ?, ?, ?)",
                [
                    ("FieldCo", "company_name", "FieldCo", "confirmed"),
                    ("FieldCo", "company_type", "AI 工具", "confirmed"),
                    ("FieldCo", "main_product_def", "Demo", "draft"),
                ],
            )

        db.save_research_records(
            self.db_path,
            [{"company_name": "FieldCo", "version": "standard", "company_type": "AI 工具"}],
        )

        companies = db.get_companies(self.db_path, final_db_path)

        self.assertEqual(companies[0]["confirmed"], 2)
        self.assertEqual(companies[0]["total"], 3)

    def test_company_list_computes_default_scores_for_legacy_rows(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO research (company_name, version, company_type, funding_info) "
                "VALUES ('LegacyCo', 'standard', 'AI 工具', 'Series B $80M')"
            )
            conn.commit()

        companies = db.get_companies(self.db_path)

        self.assertEqual(companies[0]["funding_stage"], "series_b")
        self.assertEqual(companies[0]["funding_stage_score"], 7)
        self.assertIsNotNone(companies[0]["score_defensibility"])
        self.assertIsNotNone(companies[0]["score_incumbent_attention"])
        self.assertIsNotNone(companies[0]["score_value_capture"])

    def test_get_latest_running_job_returns_newest_running_or_cancelling_job(self):
        db.create_job(self.db_path, "old-running", "OldCo", "https://old.example")
        db.create_job(self.db_path, "new-running", "NewCo", "https://new.example")
        db.update_job(self.db_path, "old-running", status="done")
        db.update_job(self.db_path, "new-running", status="cancelling", stage="正在停止")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE research_jobs SET created_at='2026-01-01 00:00:00' WHERE job_id='old-running'")
            conn.execute("UPDATE research_jobs SET created_at='2026-01-01 00:01:00' WHERE job_id='new-running'")
            conn.commit()

        job = db.get_latest_running_job(self.db_path)

        self.assertEqual(job["job_id"], "new-running")
        self.assertEqual(job["status"], "cancelling")
        self.assertEqual(job["stage"], "正在停止")


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

    def test_chart_slots_attached_to_card_7(self):
        """chart_competitive 和 chart_ecosystem 同属卡片7"""
        assets = asset_store.get_assets(self.db_path, "DemoCo")

        self.assertIn("chart_competitive", assets)
        self.assertEqual(assets["chart_competitive"]["card_index"], 7)
        self.assertIn("chart_ecosystem", assets)
        self.assertEqual(assets["chart_ecosystem"]["card_index"], 7)
        # 旧 positioning_charts 已被迁移删除
        self.assertNotIn("positioning_charts", assets)

    def test_demand_based_assets_include_website_screenshot(self):
        assets = asset_store.get_assets(self.db_path, "DemoCo")

        self.assertIn("website_screenshot", assets)
        self.assertEqual(assets["website_screenshot"]["card_index"], 2)

    def test_demand_asset_count_is_eleven(self):
        assets = asset_store.get_assets(self.db_path, "DemoCo")
        expected = {
            "logo", "website_screenshot", "office", "product_main",
            "products_other", "competitors", "competitors_logo_strip", "chart_competitive",
            "chart_ecosystem", "flywheel", "timeline",
        }

        self.assertEqual(set(assets), expected)

    def test_office_asset_starts_missing(self):
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

    def test_variant_quality_metadata_persists_and_sorts_by_final_score(self):
        low_id = asset_store.insert_variant(
            self.db_path,
            "DemoCo",
            "product_main",
            local_path="/images/DemoCo/variants/low.png",
            source_type="web_tavily",
            width=320,
            height=220,
            file_size=12000,
            aspect_ratio=1.45,
            quality_score=35,
            relevance_score=20,
            source_score=45,
            final_score=34.5,
            reject_reason="",
            meta={"query": "DemoCo app screenshot"},
        )
        high_id = asset_store.insert_variant(
            self.db_path,
            "DemoCo",
            "product_main",
            local_path="/images/DemoCo/variants/high.png",
            source_type="official_og_image",
            width=1200,
            height=630,
            file_size=180000,
            aspect_ratio=1.9,
            quality_score=85,
            relevance_score=75,
            source_score=95,
            final_score=84.25,
            reject_reason="",
            meta={"og_property": "og:image"},
        )

        variants = asset_store.list_variants(self.db_path, "DemoCo", "product_main")

        self.assertEqual([v["id"] for v in variants], [high_id, low_id])
        self.assertEqual(variants[0]["width"], 1200)
        self.assertEqual(variants[0]["height"], 630)
        self.assertEqual(variants[0]["file_size"], 180000)
        self.assertAlmostEqual(variants[0]["aspect_ratio"], 1.9)
        self.assertAlmostEqual(variants[0]["final_score"], 84.25)
        self.assertEqual(variants[0]["meta"]["og_property"], "og:image")

    def test_select_variant_writes_score_and_selected_variant_to_asset(self):
        variant_id = asset_store.insert_variant(
            self.db_path,
            "DemoCo",
            "product_main",
            local_path="/images/DemoCo/variants/product.png",
            source_type="official_og_image",
            source_url="https://demo.example/og.png",
            prompt="DemoCo product dashboard",
            final_score=88.0,
        )

        selected = asset_store.select_variant(
            self.db_path,
            "DemoCo",
            "product_main",
            variant_id,
            auto_selected=True,
        )

        self.assertTrue(selected)
        asset = asset_store.get_asset(self.db_path, "DemoCo", "product_main")
        self.assertEqual(asset["selected_variant_id"], variant_id)
        self.assertEqual(asset["auto_selected"], 1)
        self.assertAlmostEqual(asset["final_score"], 88.0)
        self.assertEqual(asset["source_type"], "official_og_image")


if __name__ == "__main__":
    unittest.main()
