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

    def test_split_text_and_draft_export_are_not_silent(self):
        with open(os.path.join(ROOT, "webapp", "static", "js", "editor.js"), encoding="utf-8") as f:
            editor_js = f.read()
        with open(os.path.join(ROOT, "webapp", "templates", "editor.html"), encoding="utf-8") as f:
            editor_html = f.read()

        self.assertNotIn("val.length < 100", editor_js)
        self.assertNotIn("分段失败静默跳过", editor_js)
        self.assertIn("splitErrors", editor_js)
        self.assertIn("exportDraftMarkdown", editor_js)
        self.assertIn("btn-export-draft", editor_html)
        self.assertIn("导出草稿 Markdown", editor_html)

    def test_failed_research_status_surfaces_error(self):
        with open(os.path.join(ROOT, "webapp", "static", "js", "editor.js"), encoding="utf-8") as f:
            editor_js = f.read()

        self.assertIn("job.error", editor_js)
        self.assertIn("研究失败", editor_js)


if __name__ == "__main__":
    unittest.main()
