import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import app as app_module
import db


def init_sqlite(schema_name: str) -> str:
    fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    schema_path = os.path.join(ROOT, "db", schema_name)
    with open(schema_path, encoding="utf-8") as f:
        schema = f.read()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
    return db_path


class ResearchStartTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_start_research_empty_body_returns_400(self):
        response = self.client.post("/api/research/start")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "缺少 company_name 或 company_url")


class PageRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_root_renders_research_desk_not_editor(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="research-desk"', html)
        self.assertIn("公司库", html)
        self.assertNotIn('id="company-select"', html)

    def test_editor_without_trailing_slash_renders_directly(self):
        response = self.client.get("/editor?company=DemoCo")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="editor-workbench"', response.get_data(as_text=True))

    def test_canvas_single_card_route_renders_html_card_page(self):
        response = self.client.get("/canvas/card/DemoCo/1")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('id="card-page"', html)
        self.assertIn("knowledge-card", html)

    def test_canvas_single_card_route_rejects_card_8(self):
        response = self.client.get("/canvas/card/DemoCo/8")

        self.assertEqual(response.status_code, 400)
        self.assertIn("card_index", response.get_json()["error"])


class ResearchCardMarkdownTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.db_path = init_sqlite("init_research_db.sql")
        self.old_research = app_module.config.DB_PATH_RESEARCH
        app_module.config.DB_PATH_RESEARCH = self.db_path
        db.save_research_records(
            self.db_path,
            [
                {
                    "company_name": "DemoCo",
                    "version": "standard",
                    "company_type": "AI 工具",
                    "timeline_events": [
                        {"date": "2024-01", "event": "上线 Beta", "impact": "获得首批用户"}
                    ],
                }
            ],
        )

    def tearDown(self):
        app_module.config.DB_PATH_RESEARCH = self.old_research
        os.remove(self.db_path)

    def test_research_card_endpoint_returns_card_markdown(self):
        response = self.client.get("/api/research/DemoCo/card/3?version=standard")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("## 卡片3：发展沿袭", payload["markdown"])
        self.assertIn("2024-01", payload["markdown"])


class ImageRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_generate_image_returns_browser_url(self):
        image_path = os.path.join(ROOT, "images", "DemoCo_logo.png")
        with patch.object(app_module, "generate_image", return_value=image_path):
            response = self.client.post(
                "/api/generate-image",
                json={
                    "company_name": "DemoCo",
                    "field_name": "logo",
                    "prompt": "clean product image",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["img_path"], "/images/DemoCo_logo.png")

    def test_generate_image_accepts_runtime_api_config_without_echoing_key(self):
        image_path = os.path.join(ROOT, "images", "DemoCo_card.png")
        with patch.object(app_module, "generate_image", return_value=image_path) as generate:
            response = self.client.post(
                "/api/generate-image",
                json={
                    "company_name": "DemoCo",
                    "field_name": "card_1_image",
                    "prompt": "clean card image",
                    "image_api_url": "https://image.example.test/generate",
                    "image_api_key": "secret-test-key",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["img_path"], "/images/DemoCo_card.png")
        self.assertNotIn("secret-test-key", str(payload))
        self.assertEqual(generate.call_args.kwargs["api_url"], "https://image.example.test/generate")
        self.assertEqual(generate.call_args.kwargs["api_key"], "secret-test-key")


class FinalMarkdownFlowTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.db_path = init_sqlite("init_final_db.sql")
        self.old_final = app_module.config.DB_PATH_FINAL
        app_module.config.DB_PATH_FINAL = self.db_path

    def tearDown(self):
        app_module.config.DB_PATH_FINAL = self.old_final
        os.remove(self.db_path)

    def test_final_save_accepts_full_markdown_and_exports_json(self):
        response = self.client.post(
            "/api/final/save",
            json={
                "company_name": "DemoCo",
                "card_index": 1,
                "markdown_content": "# DemoCo\n\n**AI 工具**",
            },
        )
        self.assertEqual(response.status_code, 200)

        status = self.client.get("/api/final/status/DemoCo")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["confirmed"], [1])
        self.assertEqual(status.get_json()["total"], 7)

        exported = self.client.get("/api/final/export/DemoCo?format=json")
        self.assertEqual(exported.status_code, 200)
        payload = exported.get_json()
        self.assertEqual(payload["cards"]["1"]["markdown_content"], "# DemoCo\n\n**AI 工具**")
        self.assertEqual(payload["confirmed_count"], 1)


if __name__ == "__main__":
    unittest.main()
