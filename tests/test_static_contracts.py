import os
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))


class StaticContractTests(unittest.TestCase):
    def test_canvas_page_uses_html_card_workbench(self):
        with open(os.path.join(ROOT, "canvas", "card-renderer.html"), encoding="utf-8") as f:
            html = f.read()

        self.assertNotIn("fabric.min.js", html)
        self.assertIn('id="card-frame"', html)
        self.assertIn('id="prompt-bar"', html)
        self.assertIn('id="source-editor"', html)
        self.assertIn('id="image-api-url"', html)
        self.assertIn('id="image-api-key"', html)
        self.assertIn('id="btn-back-research"', html)
        self.assertIn('href="/editor"', html)
        self.assertIn('/editor?company=', html)
        self.assertIn('id="current-company-name"', html)
        self.assertNotIn('id="company-name-input"', html)
        self.assertIn('id="cards-accordion"', html)
        self.assertIn('id="image-folder-accordion"', html)
        self.assertIn('class="left-accordion is-open"', html)
        self.assertIn('class="accordion-trigger"', html)
        self.assertIn('id="image-folder"', html)
        self.assertIn('class="image-folder-tools"', html)
        self.assertIn('id="bg-file-input"', html)
        self.assertIn('id="btn-export-all"', html)
        self.assertLess(html.index('id="image-folder-accordion"'), html.index('id="bg-file-input"'))
        self.assertLess(html.index('id="bg-file-input"'), html.index('id="image-folder"'))
        self.assertLess(html.index('id="image-folder-accordion"'), html.index('id="btn-export-all"'))
        self.assertIn("bindAccordions()", html)
        self.assertIn("data-accordion-target", html)
        self.assertIn("other.classList.remove('is-open')", html)
        self.assertIn("fitFrameToStage(stage, frame)", html)
        self.assertIn("min-width: 0", html)
        self.assertIn("#canvas-stage {\n    position: relative;\n    min-width: 0", html)
        self.assertIn("#prompt-input, #image-api-url, #image-api-key {\n    width: 100%;\n    min-width: 0", html)
        self.assertIn("box-sizing: border-box", html)
        self.assertIn("@media (max-width: 900px)", html)
        self.assertNotIn("min-width: 1220px", html)
        self.assertIn("this.cardLabel(i)", html)
        self.assertIn("js/html-card-renderer.js", html)
        self.assertIn("js/source-editor.js", html)
        self.assertIn("js/prompt-bar.js", html)
        self.assertIn("js/export-client.js", html)
        self.assertIn("8: '总结'", html)

        with open(os.path.join(ROOT, "canvas", "js", "source-editor.js"), encoding="utf-8") as f:
            source_editor_js = f.read()
        self.assertIn("signature(defaultSource)", source_editor_js)
        self.assertIn("saved.signature === signature", source_editor_js)

    def test_canvas_single_card_page_uses_same_fit_helper(self):
        with open(os.path.join(ROOT, "canvas", "card.html"), encoding="utf-8") as f:
            html = f.read()

        self.assertIn("fitCardPage()", html)
        self.assertIn("getBoundingClientRect()", html)
        self.assertIn("translate(-50%, -50%)", html)
        self.assertIn("saved.signature === signature", html)

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
        with open(os.path.join(ROOT, "webapp", "static", "js", "index.js"), encoding="utf-8") as f:
            index_js = f.read()

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
        self.assertIn("CARD_COUNT = 8", index_js)
        self.assertIn("${confirmed}/${total}", index_js)
        self.assertNotIn("${confirmed}/7", index_js)
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
        self.assertIn('data-card="8"', editor_html)
        self.assertIn('id="hook-render"', editor_html)
        self.assertIn("loadHookChoices", editor_js)
        self.assertIn("showHooks", editor_js)
        self.assertIn("renderHookContent", editor_js)
        self.assertIn("hook_paragraph_1", editor_js)


if __name__ == "__main__":
    unittest.main()
