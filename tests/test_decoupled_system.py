import os
import sqlite3
import sys
import tempfile
import unittest
from io import BytesIO

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import app as app_module
import asset_store
from repositories.card_config_repo import add_card_item, get_cards
from repositories.field_repo import upsert_final_field
from services.card_config_service import create_default_cards_for_company
from services.template_service import save_template


def init_sqlite(schema_name: str) -> str:
    fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    schema_path = os.path.join(ROOT, "db", schema_name)
    with open(schema_path, encoding="utf-8") as f:
        schema = f.read()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
    return db_path


class DecoupledSystemTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.research_db = init_sqlite("init_research_db.sql")
        self.final_db = init_sqlite("init_final_db.sql")
        self.assets_db = init_sqlite("init_assets_db.sql")
        self.composition_db = init_sqlite("init_composition_db.sql")
        self.template_db = init_sqlite("init_template_db.sql")
        for db_path, migration in [
            (self.research_db, "001_research_fields.sql"),
            (self.final_db, "002_final_fields.sql"),
        ]:
            with open(os.path.join(ROOT, "db", "migrations", migration), encoding="utf-8") as f:
                sql = f.read()
            with sqlite3.connect(db_path) as conn:
                conn.executescript(sql)

        self.old_paths = (
            app_module.config.DB_PATH_RESEARCH,
            app_module.config.DB_PATH_FINAL,
            app_module.config.DB_PATH_ASSETS,
            app_module.config.DB_PATH_COMPOSITION,
            app_module.config.DB_PATH_TEMPLATE,
        )
        app_module.config.DB_PATH_RESEARCH = self.research_db
        app_module.config.DB_PATH_FINAL = self.final_db
        app_module.config.DB_PATH_ASSETS = self.assets_db
        app_module.config.DB_PATH_COMPOSITION = self.composition_db
        app_module.config.DB_PATH_TEMPLATE = self.template_db

    def tearDown(self):
        (
            app_module.config.DB_PATH_RESEARCH,
            app_module.config.DB_PATH_FINAL,
            app_module.config.DB_PATH_ASSETS,
            app_module.config.DB_PATH_COMPOSITION,
            app_module.config.DB_PATH_TEMPLATE,
        ) = self.old_paths
        for path in [self.research_db, self.final_db, self.assets_db, self.composition_db, self.template_db]:
            if os.path.exists(path):
                os.remove(path)

    def test_card_config_creates_default_cards_and_items(self):
        created = create_default_cards_for_company(self.composition_db, "DemoCo")

        self.assertEqual(created[0], "card_01")
        cards = get_cards(self.composition_db, "DemoCo")
        self.assertEqual(len(cards), 8)
        self.assertEqual(cards[6]["card_id"], "card_07")
        self.assertEqual(cards[6]["template_id"], "multi_chart")

    def test_render_data_auto_creates_defaults_and_resolves_items(self):
        upsert_final_field(self.final_db, "DemoCo", "company_name", "DemoCo", status="confirmed")
        asset_store.ensure_assets_rows(self.assets_db, "DemoCo")
        variant_id = asset_store.insert_variant(
            self.assets_db,
            "DemoCo",
            "logo",
            local_path="/images/DemoCo/variants/logo.png",
            source_type="upload",
            width=512,
            height=512,
        )
        asset_store.select_variant(self.assets_db, "DemoCo", "logo", variant_id)

        response = self.client.get("/api/render-data/DemoCo")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["cards"]), 8)
        card1 = payload["cards"][0]
        self.assertEqual(card1["card_id"], "card_01")
        self.assertEqual(card1["items"][0]["value"], "DemoCo")
        media_items = [item for item in card1["items"] if item["item_type"] == "media"]
        self.assertEqual(media_items[0]["url"], "/images/DemoCo/variants/logo.png")
        self.assertIn("regions", card1["template"])

    def test_media_api_wraps_existing_asset_store(self):
        asset_store.ensure_assets_rows(self.assets_db, "DemoCo")
        variant_id = asset_store.insert_variant(
            self.assets_db,
            "DemoCo",
            "product_main",
            local_path="/images/DemoCo/variants/product.png",
            source_type="upload",
            final_score=91,
        )

        selected = self.client.patch(
            "/api/media/DemoCo/product_main/select",
            json={"variant_id": variant_id},
        )
        self.assertEqual(selected.status_code, 200)

        response = self.client.get("/api/media/DemoCo/product_main")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["media_key"], "product_main")
        self.assertEqual(payload["selected_variant"]["id"], variant_id)

    def test_media_upload_rejects_svg_for_regular_image_slots(self):
        response = self.client.post(
            "/api/media/DemoCo/logo/upload",
            data={"file": (BytesIO(b"<svg></svg>"), "logo.svg")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("svg", response.get_json()["error"])

    def test_media_generate_for_echarts_assets_preserves_old_renderer_route(self):
        response = self.client.post("/api/media/DemoCo/chart_competitive/generate")

        self.assertEqual(response.status_code, 307)
        self.assertIn("/api/assets/generate/DemoCo/chart_competitive", response.headers["Location"])

    def test_render_data_allows_any_media_on_any_card(self):
        create_default_cards_for_company(self.composition_db, "DemoCo")
        add_card_item(
            self.composition_db,
            "DemoCo",
            "card_08",
            item_type="media",
            item_key="product_main",
            display_role="hero_image",
            sort_order=99,
        )
        asset_store.ensure_assets_rows(self.assets_db, "DemoCo")
        variant_id = asset_store.insert_variant(
            self.assets_db,
            "DemoCo",
            "product_main",
            local_path="/images/DemoCo/variants/product.png",
            source_type="upload",
        )
        asset_store.select_variant(self.assets_db, "DemoCo", "product_main", variant_id)

        response = self.client.get("/api/render-data/DemoCo/card_08")

        self.assertEqual(response.status_code, 200)
        media_items = [item for item in response.get_json()["items"] if item["item_type"] == "media"]
        self.assertEqual(media_items[-1]["item_key"], "product_main")
        self.assertEqual(media_items[-1]["url"], "/images/DemoCo/variants/product.png")

    def test_template_service_rejects_duplicate_region_ids(self):
        ok, errors = save_template(
            self.template_db,
            "bad",
            "坏模板",
            {
                "canvas": {"width": 900, "height": 1200},
                "regions": [
                    {"id": "title", "type": "text", "role": "title", "x": 0, "y": 0, "w": 100, "h": 100},
                    {"id": "title", "type": "text", "role": "body", "x": 0, "y": 0, "w": 100, "h": 100},
                ],
            },
        )

        self.assertFalse(ok)
        self.assertTrue(any("重复" in item for item in errors))

    def test_template_api_updates_duplicates_and_deletes_custom_templates(self):
        template = {
            "canvas": {"width": 900, "height": 1200},
            "regions": [
                {"id": "title", "type": "text", "role": "title", "x": 0, "y": 0, "w": 100, "h": 100},
            ],
        }
        created = self.client.post(
            "/api/templates",
            json={"template_id": "custom_test", "template_name": "测试模板", "template_json": template},
        )
        self.assertEqual(created.status_code, 200)

        template["regions"][0]["w"] = 180
        updated = self.client.patch(
            "/api/templates/custom_test",
            json={"template_name": "测试模板2", "template_json": template},
        )
        self.assertEqual(updated.status_code, 200)

        duplicated = self.client.post(
            "/api/templates/custom_test/duplicate",
            json={"template_id": "custom_test_copy", "template_name": "测试模板副本"},
        )
        self.assertEqual(duplicated.status_code, 200)

        deleted = self.client.delete("/api/templates/custom_test_copy")
        self.assertEqual(deleted.status_code, 200)

    def test_layout_export_endpoint_creates_job(self):
        create_default_cards_for_company(self.composition_db, "DemoCo")
        response = self.client.post(
            "/api/export/DemoCo",
            json={"card_ids": ["card_01"], "format": "png", "scale": 1},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["job_id"].startswith("exp_"))


if __name__ == "__main__":
    unittest.main()
