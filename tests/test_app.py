import os
import io
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import app as app_module
import db
import asset_store
import asset_pipeline
import infographic_templates


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

    def test_canvas_single_card_route_accepts_card_8(self):
        response = self.client.get("/canvas/card/DemoCo/8")

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="card-page"', response.get_data(as_text=True))

    def test_canvas_single_card_route_rejects_card_9(self):
        response = self.client.get("/canvas/card/DemoCo/9")

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
                    "market_opportunity": "AI 工作流进入重构期。",
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

    def test_research_card_endpoint_returns_card_8_summary_markdown(self):
        response = self.client.get("/api/research/DemoCo/card/8?version=standard")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("## 卡片8：总结", payload["markdown"])
        self.assertIn("**机遇**：AI 工作流进入重构期。", payload["markdown"])


class CompanyListTests(unittest.TestCase):
    def setUp(self):
        self.db_path = init_sqlite("init_research_db.sql")
        db.save_research_records(
            self.db_path,
            [
                {
                    "company_name": "DemoCo",
                    "version": "standard",
                    "company_type": "AI 工具",
                    "website_url": "https://demo.example",
                }
            ],
        )

    def tearDown(self):
        os.remove(self.db_path)

    def test_company_list_includes_latest_website_url_for_refill(self):
        companies = db.get_companies(self.db_path)

        self.assertEqual(companies[0]["company_name"], "DemoCo")
        self.assertEqual(companies[0]["website_url"], "https://demo.example")
        self.assertEqual(companies[0]["company_url"], "https://demo.example")


class ImageRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.assets_db_path = init_sqlite("init_assets_db.sql")
        self.old_assets = app_module.config.DB_PATH_ASSETS
        app_module.config.DB_PATH_ASSETS = self.assets_db_path

    def tearDown(self):
        app_module.config.DB_PATH_ASSETS = self.old_assets
        os.remove(self.assets_db_path)

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

    def test_generate_image_with_asset_key_records_selected_variant(self):
        image_path = os.path.join(ROOT, "images", "DemoCo_office.png")
        with patch.object(app_module, "generate_image", return_value=image_path):
            response = self.client.post(
                "/api/generate-image",
                json={
                    "company_name": "DemoCo",
                    "field_name": "office",
                    "asset_key": "office",
                    "prompt": "clean office image",
                },
            )

        self.assertEqual(response.status_code, 200)
        variants = asset_store.list_variants(self.assets_db_path, "DemoCo", "office")
        self.assertEqual(len(variants), 1)
        self.assertEqual(variants[0]["local_path"], "/images/DemoCo_office.png")
        self.assertEqual(variants[0]["source_type"], "api_generate")
        self.assertEqual(variants[0]["is_selected"], 1)


class SvgTemplateUploadTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_local_python_template_upload_registers_template(self):
        content = b"""META = {
    "id": "unit_test_template",
    "name": "Unit Test Template",
    "asset_key": "timeline",
    "builtin": False,
    "params": [],
}

def build(data, params):
    return '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
"""
        old_registry = dict(infographic_templates._registry)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                with patch.object(infographic_templates, "_USER_DIR", Path(tmp)):
                    response = self.client.post(
                        "/api/svg-templates/upload",
                        data={"file": (io.BytesIO(content), "unit_template.py")},
                        content_type="multipart/form-data",
                        headers={"X-Template-Upload-Intent": "local-dev"},
                    )
                    preview = self.client.post(
                        "/api/svg-templates/preview",
                        json={"template_id": "unit_test_template", "data": {}, "params": {}},
                    )
                    saved = Path(tmp) / "unit_template.py"
                    saved_exists = saved.exists()
            finally:
                infographic_templates._registry.clear()
                infographic_templates._registry.update(old_registry)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["meta"]["id"], "unit_test_template")
        self.assertTrue(saved_exists)
        self.assertEqual(preview.status_code, 200)
        self.assertIn("<svg", preview.get_data(as_text=True))

    def test_python_template_upload_requires_intent_header(self):
        content = b"""META = {
    "id": "unit_test_template",
    "name": "Unit Test Template",
    "asset_key": "timeline",
    "params": [],
}

def build(data, params):
    return '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
"""
        response = self.client.post(
            "/api/svg-templates/upload",
            data={"file": (io.BytesIO(content), "unit_template.py")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("上传意图", response.get_json()["error"])

    def test_python_template_delete_removes_uploaded_filename(self):
        content = b"""META = {
    "id": "unit_test_template",
    "name": "Unit Test Template",
    "asset_key": "timeline",
    "params": [],
}

def build(data, params):
    return '<svg xmlns="http://www.w3.org/2000/svg"></svg>'
"""
        old_registry = dict(infographic_templates._registry)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                with patch.object(infographic_templates, "_USER_DIR", Path(tmp)):
                    upload = self.client.post(
                        "/api/svg-templates/upload",
                        data={"file": (io.BytesIO(content), "unit_template.py")},
                        content_type="multipart/form-data",
                        headers={"X-Template-Upload-Intent": "local-dev"},
                    )
                    response = self.client.delete("/api/svg-templates/unit_test_template")
                    saved = Path(tmp) / "unit_template.py"
                    saved_exists = saved.exists()
            finally:
                infographic_templates._registry.clear()
                infographic_templates._registry.update(old_registry)

        self.assertEqual(upload.status_code, 200)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(saved_exists)

    def test_remote_python_template_upload_is_rejected(self):
        response = self.client.post(
            "/api/svg-templates/upload",
            data={"file": (io.BytesIO(b"META = {}\n\ndef build(data, params):\n    return ''\n"), "unsafe.py")},
            content_type="multipart/form-data",
            environ_base={"REMOTE_ADDR": "10.0.0.20"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("仅允许本机", response.get_json()["error"])


class AssetPathSafetyTests(unittest.TestCase):
    def test_variant_path_sanitizes_company_and_suffix_inside_images_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = asset_pipeline._variant_path(tmp, "../Bad Co", "../timeline", "../../shot")

            root = os.path.abspath(tmp)
            self.assertEqual(os.path.commonpath([root, os.path.abspath(dest)]), root)
            self.assertNotIn("..", os.path.relpath(dest, root))
            self.assertIn("Bad_Co", dest)

    def test_collection_pipeline_selects_first_ready_variant(self):
        assets_db_path = init_sqlite("init_assets_db.sql")
        self.addCleanup(lambda: os.path.exists(assets_db_path) and os.remove(assets_db_path))

        def collect_office(db_path, images_root, company_name, location, query_config):
            asset_store.insert_variant(
                db_path,
                company_name,
                "office",
                local_path="/images/DemoCo/variants/office.png",
                source_type="web_tavily",
            )
            return 1

        with tempfile.TemporaryDirectory() as images_root:
            with patch.object(asset_pipeline, "_collect_office_variants", side_effect=collect_office), \
                 patch.object(asset_pipeline, "_collect_product_main_variants", return_value=0), \
                 patch.object(asset_pipeline, "_collect_products_other_variants", return_value=0), \
                 patch.object(asset_pipeline, "_collect_competitors_variants", return_value=0):
                asset_pipeline.collect_image_variants_pipeline(
                    assets_db_path,
                    images_root,
                    "DemoCo",
                    {"location": "San Francisco"},
                )

        demo_asset = asset_store.get_asset(assets_db_path, "DemoCo", "office")
        variants = asset_store.list_variants(assets_db_path, "DemoCo", "office")
        self.assertEqual(demo_asset["local_path"], "/images/DemoCo/variants/office.png")
        self.assertEqual(variants[0]["is_selected"], 1)

    def test_card2_office_collection_selects_map_and_keeps_supplements(self):
        assets_db_path = init_sqlite("init_assets_db.sql")
        self.addCleanup(lambda: os.path.exists(assets_db_path) and os.remove(assets_db_path))
        asset_store.ensure_assets_rows(assets_db_path, "DemoCo")

        with tempfile.TemporaryDirectory() as images_root:
            with patch.object(asset_pipeline, "_render_osm_map", return_value=True) as render_map, \
                 patch.object(asset_pipeline, "_geocode_location", return_value=(37.77, -122.42)), \
                 patch.object(asset_pipeline.config, "GOOGLE_MAPS_API_KEY", "maps-key"), \
                 patch.object(asset_pipeline, "_fetch_street_view", return_value=True), \
                 patch.object(asset_pipeline, "_try_tavily_images", return_value="https://images.example/office.png"):
                count = asset_pipeline._collect_office_variants(
                    assets_db_path,
                    images_root,
                    "DemoCo",
                    "San Francisco, CA",
                    {"tavily_queries": ["DemoCo office"]},
                )

        variants = asset_store.list_variants(assets_db_path, "DemoCo", "office")
        selected = [v for v in variants if v["is_selected"]]
        self.assertEqual(count, 4)
        self.assertEqual(len(variants), 4)
        self.assertEqual(selected[0]["source_type"], "osm_map")
        self.assertEqual(selected[0]["local_path"], "/images/DemoCo/variants/office__osm_map.png")
        self.assertIn("street_view", {v["source_type"] for v in variants})
        self.assertIn("web_tavily", {v["source_type"] for v in variants})
        render_map.assert_called_once()


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
                "card_index": 8,
                "markdown_content": "# DemoCo\n\n**AI 工具**",
            },
        )
        self.assertEqual(response.status_code, 200)

        status = self.client.get("/api/final/status/DemoCo")
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["confirmed"], [8])
        self.assertEqual(status.get_json()["total"], 8)

        exported = self.client.get("/api/final/export/DemoCo?format=json")
        self.assertEqual(exported.status_code, 200)
        payload = exported.get_json()
        self.assertEqual(payload["cards"]["8"]["markdown_content"], "# DemoCo\n\n**AI 工具**")
        self.assertEqual(payload["confirmed_count"], 1)


class SvgRenderRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        self.final_db_path = init_sqlite("init_final_db.sql")
        self.assets_db_path = init_sqlite("init_assets_db.sql")
        self.old_final = app_module.config.DB_PATH_FINAL
        self.old_assets = app_module.config.DB_PATH_ASSETS
        self.old_images = app_module.config.IMAGES_DIR
        app_module.config.DB_PATH_FINAL = self.final_db_path
        app_module.config.DB_PATH_ASSETS = self.assets_db_path
        self.images_dir = tempfile.mkdtemp()
        app_module.config.IMAGES_DIR = self.images_dir
        db.save_final_markdown(self.final_db_path, "DemoCo", 3, "## 卡片3：发展沿袭\n\n- **2024** 上线")
        asset_store.ensure_assets_rows(self.assets_db_path, "DemoCo")
        asset_store.upsert_asset(
            self.assets_db_path,
            "DemoCo",
            "timeline",
            meta={"svg_data": {"events": [{"year": "2024", "title": "上线", "desc": "发布产品"}]}},
        )

    def tearDown(self):
        app_module.config.DB_PATH_FINAL = self.old_final
        app_module.config.DB_PATH_ASSETS = self.old_assets
        app_module.config.IMAGES_DIR = self.old_images
        os.remove(self.final_db_path)
        os.remove(self.assets_db_path)
        import shutil
        shutil.rmtree(self.images_dir)

    def test_render_svg_uses_cached_structured_data(self):
        with patch.object(app_module, "extract_timeline_json", side_effect=AssertionError("should not extract")), \
             patch.object(app_module, "render_with_template", return_value=True) as render:
            response = self.client.post(
                "/api/image-studio/DemoCo/timeline/render-svg",
                json={"template_id": "timeline_horizontal", "params": {}},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(render.call_args.args[0]["events"][0]["title"], "上线")


if __name__ == "__main__":
    unittest.main()
