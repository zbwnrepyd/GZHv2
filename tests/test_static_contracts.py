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
        self.assertIn("async getResearchCard(", api_js)
        self.assertIn("async getFinalStatus(", api_js)

    def test_three_page_spec_static_contract(self):
        with open(os.path.join(ROOT, "webapp", "templates", "index.html"), encoding="utf-8") as f:
            index_html = f.read()
        with open(os.path.join(ROOT, "webapp", "templates", "editor.html"), encoding="utf-8") as f:
            editor_html = f.read()
        with open(os.path.join(ROOT, "webapp", "static", "js", "editor.js"), encoding="utf-8") as f:
            editor_js = f.read()

        self.assertIn('id="research-desk"', index_html)
        self.assertIn('id="company-table-body"', index_html)
        self.assertIn('id="editor-workbench"', editor_html)
        self.assertIn('id="version-compare"', editor_html)
        self.assertIn('data-version="standard"', editor_html)
        self.assertIn('data-version="business"', editor_html)
        self.assertIn('data-version="spread"', editor_html)
        self.assertIn('id="line-choice-grid"', editor_html)
        self.assertIn('id="preview-render"', editor_html)
        self.assertIn("markdown_content", editor_js)
        self.assertIn("loadVersionChoices", editor_js)
        self.assertIn("renderLineChoices", editor_js)
        self.assertIn("applyLineChoice", editor_js)
        self.assertIn("getFinalMarkdown", editor_js)
        self.assertNotIn('class="version-radio"', editor_html)
        self.assertNotIn('id="markdown-editor"', editor_html)
        self.assertNotIn('id="field-edit-mini"', editor_html)

    def test_failed_research_status_surfaces_error(self):
        with open(os.path.join(ROOT, "webapp", "static", "js", "index.js"), encoding="utf-8") as f:
            index_js = f.read()

        self.assertIn("job.error", index_js)
        self.assertIn("研究失败", index_js)

    def test_editor_surfaces_hook_copy_view(self):
        with open(os.path.join(ROOT, "webapp", "templates", "editor.html"), encoding="utf-8") as f:
            editor_html = f.read()
        with open(os.path.join(ROOT, "webapp", "static", "js", "editor.js"), encoding="utf-8") as f:
            editor_js = f.read()

        self.assertIn('data-card="hook"', editor_html)
        self.assertIn('id="hook-render"', editor_html)
        self.assertIn("loadHookChoices", editor_js)
        self.assertIn("showHooks", editor_js)
        self.assertIn("renderHookContent", editor_js)
        self.assertIn("hook_paragraph_1", editor_js)


if __name__ == "__main__":
    unittest.main()
