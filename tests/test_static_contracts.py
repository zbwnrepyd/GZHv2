import os
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))


class StaticContractTests(unittest.TestCase):
    def test_canvas_page_handler_does_not_shadow_export_module(self):
        with open(os.path.join(ROOT, "canvas", "card-renderer.html"), encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(ROOT, "canvas", "js", "export.js"), encoding="utf-8") as f:
            export_js = f.read()

        self.assertIn("async function exportAllCards(", export_js)
        self.assertIn("function exportAllCardsFromPage()", html)
        self.assertIn("onclick=\"exportAllCardsFromPage()\"", html)

    def test_editor_api_exposes_research_job_helpers(self):
        with open(os.path.join(ROOT, "webapp", "static", "js", "api.js"), encoding="utf-8") as f:
            api_js = f.read()

        self.assertIn("async startResearch(", api_js)
        self.assertIn("async getResearchStatus(", api_js)


if __name__ == "__main__":
    unittest.main()
