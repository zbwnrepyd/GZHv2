import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import app as app_module


class ResearchStartTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_start_research_empty_body_returns_400(self):
        response = self.client.post("/api/research/start")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "缺少 company_name 或 company_url")


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


if __name__ == "__main__":
    unittest.main()
