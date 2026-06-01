import os
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))


class StaticContractTests(unittest.TestCase):
    def test_canvas_page_uses_html_card_workbench(self):
        with open(os.path.join(ROOT, "canvas", "card-renderer.html"), encoding="utf-8") as f:
            html = f.read()

        self.assertNotIn("fabric.min.js", html)
        self.assertIn('id="card-frame"', html)
        self.assertIn('id="source-editor"', html)
        self.assertIn('id="btn-source-all"', html)
        self.assertIn('id="btn-source-css"', html)
        self.assertIn('id="btn-source-html"', html)
        self.assertIn('id="btn-inspect-source"', html)
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
        self.assertIn("box-sizing: border-box", html)
        self.assertIn("@media (max-width: 900px)", html)
        self.assertNotIn("min-width: 1220px", html)
        self.assertIn("this.cardLabel(i)", html)
        self.assertIn("js/html-card-renderer.js", html)
        self.assertIn("js/source-editor.js", html)
        self.assertIn("js/export-client.js", html)
        self.assertIn("8: '总结'", html)

        with open(os.path.join(ROOT, "canvas", "js", "source-editor.js"), encoding="utf-8") as f:
            source_editor_js = f.read()
        self.assertIn("signature(defaultSource)", source_editor_js)
        self.assertIn("saved.signature === signature", source_editor_js)
        self.assertIn("viewMode", source_editor_js)
        self.assertIn("splitSource", source_editor_js)
        self.assertIn("showSection", source_editor_js)
        self.assertIn("inspectMode", source_editor_js)
        self.assertIn("installInspectHooks", source_editor_js)
        self.assertIn("locateSourceForElement", source_editor_js)
        self.assertIn("getFullSource", source_editor_js)

    def test_canvas_single_card_page_uses_same_fit_helper(self):
        with open(os.path.join(ROOT, "canvas", "card.html"), encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(ROOT, "canvas", "js", "api-loader.js"), encoding="utf-8") as f:
            api_loader_js = f.read()

        self.assertIn("fitCardPage()", html)
        self.assertIn("getBoundingClientRect()", html)
        self.assertIn("translate(-50%, -50%)", html)
        self.assertIn("saved.signature === signature", html)
        self.assertIn("background: #F2F2F2", html)
        self.assertIn("renderCardSource", html)
        self.assertIn("fonts.googleapis.com", html)
        self.assertIn("Bebas+Neue", html)
        self.assertIn("cardData._assets = await loadAssetsFromAPI(company)", api_loader_js)

    def test_screenshot_cli_exports_multiple_high_resolution_shots(self):
        with open(os.path.join(ROOT, "canvas", "screenshot.js"), encoding="utf-8") as f:
            script = f.read()

        self.assertIn("--shots", script)
        self.assertIn("--scale", script)
        self.assertIn("--shot-delay", script)
        self.assertIn("deviceScaleFactor: args.scale", script)
        self.assertIn("for (let shotIndex = 1; shotIndex <= args.shots; shotIndex += 1)", script)
        self.assertIn("_shot_", script)

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
        self.assertIn("await this.loadCard(1)", editor_js)
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
        self.assertIn("activeJobId", index_js)
        self.assertIn("pollInFlight", index_js)
        self.assertIn("if (btn.disabled || this.activeJobId) return", index_js)
        self.assertIn("this.activeJobId !== jobId || this.pollInFlight", index_js)

    def test_research_desk_surfaces_source_details(self):
        with open(os.path.join(ROOT, "webapp", "templates", "index.html"), encoding="utf-8") as f:
            index_html = f.read()
        with open(os.path.join(ROOT, "webapp", "static", "js", "index.js"), encoding="utf-8") as f:
            index_js = f.read()
        with open(os.path.join(ROOT, "webapp", "app.py"), encoding="utf-8") as f:
            app_py = f.read()

        self.assertIn('id="source-status-grid"', index_html)
        self.assertIn("renderSourceStatus", index_js)
        self.assertIn("job.sources", index_js)
        self.assertNotIn('on_progress("资产采集"', app_py)
        self.assertNotIn("_refetch_founder_fields", app_py)

    def test_company_library_rows_expand_one_research_detail(self):
        with open(os.path.join(ROOT, "webapp", "static", "js", "index.js"), encoding="utf-8") as f:
            index_js = f.read()

        self.assertIn("expandedCompany", index_js)
        self.assertIn("toggleCompanyDetails", index_js)
        self.assertIn("renderCompanyDetailRow", index_js)
        self.assertIn("API.getAllVersions", index_js)
        self.assertIn('class="company-row ', index_js)
        self.assertIn('data-company="${encodedName}"', index_js)
        self.assertIn('data-refill-company="${this.esc(encodedName)}"', index_js)
        self.assertIn('data-refill-url="${this.esc(encodedUrl)}"', index_js)
        self.assertIn('class="company-detail-row"', index_js)
        self.assertIn("this.expandedCompany = companyName", index_js)
        self.assertIn("refillResearch(encodedName, encodedUrl = '')", index_js)
        self.assertIn("urlInput.value", index_js)
        self.assertNotIn("renderVersionDetail", index_js)
        self.assertNotIn("version-detail-grid", index_js)

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

    def test_image_studio_caches_svg_data_per_asset_key(self):
        with open(os.path.join(ROOT, "image-studio", "js", "studio-app.js"), encoding="utf-8") as f:
            studio_js = f.read()

        self.assertIn("_svDataByKey", studio_js)
        self.assertIn("this._svDataByKey[slot.asset_key]", studio_js)
        self.assertNotIn("if (!this._svData) {", studio_js)

    def test_image_studio_shows_variants_in_middle_panel(self):
        with open(os.path.join(ROOT, "image-studio", "index.html"), encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(ROOT, "image-studio", "js", "search-panel.js"), encoding="utf-8") as f:
            search_js = f.read()
        with open(os.path.join(ROOT, "image-studio", "js", "variant-sidebar.js"), encoding="utf-8") as f:
            sidebar_js = f.read()
        with open(os.path.join(ROOT, "image-studio", "css", "studio.css"), encoding="utf-8") as f:
            css = f.read()

        self.assertIn("候选变体 + 搜索图片网格", html)
        self.assertIn('id="variant-list-main"', search_js)
        self.assertIn("document.getElementById('variant-list-main')", sidebar_js)
        self.assertNotIn("<h3>候选</h3>", sidebar_js)
        self.assertIn(".variant-list-main", css)

    def test_card2_map_is_main_collection_path(self):
        with open(os.path.join(ROOT, "webapp", "asset_pipeline.py"), encoding="utf-8") as f:
            pipeline_py = f.read()
        with open(os.path.join(ROOT, "webapp", "app.py"), encoding="utf-8") as f:
            app_py = f.read()

        self.assertIn("Card 2: map first, then supplemental street-view/Tavily candidates", pipeline_py)
        self.assertIn("卡片2：公司位置地图", pipeline_py)
        self.assertIn("_render_osm_tile_composite", pipeline_py)
        self.assertIn("_render_static_map_card", pipeline_py)
        self.assertIn('if asset_key != "office"', app_py)


if __name__ == "__main__":
    unittest.main()
