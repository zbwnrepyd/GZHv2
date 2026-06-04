# Demand-Based Image Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework image-studio so image finalization is organized by image demand, with separate workspaces for collected images and generated charts, richer chart parameter editing, and canvas access to all finalized assets.

**Architecture:** Keep the current Flask + SQLite + Vanilla JS stack. Extend the existing asset model with `website_screenshot`, reuse `image_variants` for all candidate/generated versions, and replace the image-studio controller UI with demand-based navigation plus type-specific workspaces. Generated charts use a right-side parameter inspector and preview/render endpoints; collected images reuse the existing search/import/rescore APIs.

**Tech Stack:** Python Flask, SQLite `sqlite3`, Vanilla JS, ECharts HTML previews, SVG templates, Playwright PNG rendering, `unittest`.

---

## File Map

- Modify `webapp/asset_store.py`: add `website_screenshot`, update card mapping and row creation.
- Modify `db/init_assets_db.sql`: update asset key comment.
- Modify `webapp/app.py`: update overview order, query generation, add chart data endpoint, improve preview/render support.
- Modify `webapp/infographic.py`: add richer chart params and safe empty-state HTML.
- Modify `image-studio/index.html`: load new workspace/inspector modules.
- Modify `image-studio/js/studio-api.js`: add chart data and render helpers.
- Modify `image-studio/js/studio-app.js`: simplify app orchestration and demand-based left nav.
- Create `image-studio/js/workspace-image.js`: collected image workspace.
- Create `image-studio/js/param-inspector.js`: grouped parameter inspector.
- Create `image-studio/js/workspace-chart.js`: generated chart workspace.
- Modify `image-studio/js/variant-sidebar.js`: support external confirm placement and generated version labels.
- Modify `image-studio/css/studio.css`: demand list, integrated workspace, parameter inspector layout.
- Modify `webapp/static/js/editor.js`: update embedded slot labels/order.
- Modify `canvas/js/api-loader.js`, `canvas/card-renderer.html`, `canvas/js/html-card-renderer.js`: expose all finalized assets in image folder without single-card limitation.
- Modify `tests/test_db.py`, `tests/test_app.py`, `tests/test_static_contracts.py`: cover new asset key, chart endpoints, UI contracts, and canvas multi-asset support.

## Task 1: Asset Keys And Backend Overview

**Files:**
- Modify: `webapp/asset_store.py`
- Modify: `db/init_assets_db.sql`
- Modify: `webapp/app.py`
- Modify: `tests/test_db.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing tests for demand asset keys**

Add tests in `tests/test_db.py`:

```python
def test_demand_based_assets_include_website_screenshot(self):
    assets = asset_store.get_assets(self.db_path, "DemoCo")
    self.assertIn("website_screenshot", assets)
    self.assertEqual(assets["website_screenshot"]["card_index"], 2)

def test_demand_asset_count_is_ten(self):
    assets = asset_store.get_assets(self.db_path, "DemoCo")
    expected = {
        "logo", "website_screenshot", "office", "product_main",
        "products_other", "competitors", "chart_competitive",
        "chart_ecosystem", "flywheel", "timeline",
    }
    self.assertEqual(set(assets), expected)
```

Add an overview order test in `tests/test_app.py`:

```python
def test_image_studio_overview_uses_demand_order(self):
    response = self.client.get("/api/image-studio/DemoCo")
    self.assertEqual(response.status_code, 200)
    keys = [slot["asset_key"] for slot in response.get_json()["slots"]]
    self.assertEqual(keys, [
        "logo", "website_screenshot", "office", "product_main",
        "products_other", "competitors", "chart_competitive",
        "chart_ecosystem", "flywheel", "timeline",
    ])
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
python3 -m unittest tests.test_db.AssetVariantTests tests.test_app.ImageStudioTests -v
```

Expected: tests fail because `website_screenshot` is missing or overview order differs.

- [ ] **Step 3: Implement asset key updates**

Update `ASSET_KEYS`, `CARD_ASSET_MAP`, `ASSET_TO_CARD`, `db/init_assets_db.sql`, overview slot order, and query topic/fallback mappings. Use `website_screenshot` card index `2` as a weak usage hint, not a canvas limitation.

- [ ] **Step 4: Run focused backend tests**

Run:

```bash
python3 -m unittest tests.test_db.AssetVariantTests tests.test_app.ImageStudioTests -v
```

Expected: pass.

## Task 2: Chart Data And Preview API

**Files:**
- Modify: `webapp/app.py`
- Modify: `webapp/infographic.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: Write failing tests for chart data and empty preview**

Add tests:

```python
def test_chart_data_endpoint_returns_editable_competitive_payload(self):
    response = self.client.post("/api/image-studio/DemoCo/chart_competitive/chart-data")
    self.assertEqual(response.status_code, 200)
    data = response.get_json()
    self.assertEqual(data["asset_key"], "chart_competitive")
    self.assertIn("companies", data)
    self.assertIn("params", data)
    self.assertIn("title", data["params"])

def test_chart_preview_returns_html_even_without_scored_companies(self):
    response = self.client.post(
        "/api/image-studio/DemoCo/chart_competitive/preview",
        json={"params": {"title": "竞争格局图"}},
    )
    self.assertEqual(response.status_code, 200)
    self.assertIn("<!DOCTYPE html>", response.get_data(as_text=True))
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
python3 -m unittest tests.test_app.ImageStudioTests -v
```

Expected: `chart-data` endpoint missing.

- [ ] **Step 3: Implement chart data endpoint and richer params**

Add `POST /api/image-studio/<company>/<asset_key>/chart-data`. Return editable `companies`, `data`, `params`, and `templates` where applicable. Update chart preview builders to accept `title`, `subtitle`, `note`, quadrant labels, thresholds, label density, canvas size, and color params. If no scored companies exist, return an HTML empty state instead of blank chart.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m unittest tests.test_app.ImageStudioTests -v
```

Expected: pass.

## Task 3: Demand-Based Image Studio UI

**Files:**
- Modify: `image-studio/index.html`
- Modify: `image-studio/js/studio-api.js`
- Modify: `image-studio/js/studio-app.js`
- Create: `image-studio/js/workspace-image.js`
- Create: `image-studio/js/param-inspector.js`
- Create: `image-studio/js/workspace-chart.js`
- Modify: `image-studio/js/variant-sidebar.js`
- Modify: `image-studio/css/studio.css`
- Modify: `tests/test_static_contracts.py`

- [ ] **Step 1: Write failing static contracts**

Add assertions in `tests/test_static_contracts.py`:

```python
def test_image_studio_uses_demand_based_workspaces(self):
    with open(os.path.join(ROOT, "image-studio", "index.html"), encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(ROOT, "image-studio", "js", "studio-app.js"), encoding="utf-8") as f:
        app_js = f.read()
    with open(os.path.join(ROOT, "image-studio", "js", "param-inspector.js"), encoding="utf-8") as f:
        inspector_js = f.read()
    with open(os.path.join(ROOT, "image-studio", "css", "studio.css"), encoding="utf-8") as f:
        css = f.read()

    self.assertIn("workspace-image.js", html)
    self.assertIn("workspace-chart.js", html)
    self.assertIn("param-inspector.js", html)
    self.assertIn("DEMAND_LABELS", app_js)
    self.assertIn("website_screenshot", app_js)
    self.assertIn("数据与文字", inspector_js)
    self.assertIn("画布与版式", inspector_js)
    self.assertIn("字体与颜色", inspector_js)
    self.assertIn("图表专属", inspector_js)
    self.assertIn("输出版本", inspector_js)
    self.assertIn(".demand-workspace", css)
    self.assertIn(".param-inspector", css)
```

- [ ] **Step 2: Run static contract to verify red**

Run:

```bash
python3 -m unittest tests.test_static_contracts.StaticContractTests.test_image_studio_uses_demand_based_workspaces -v
```

Expected: fail because new files do not exist.

- [ ] **Step 3: Implement UI modules**

Create focused Vanilla JS modules:

```text
WorkspaceImage.mount(container, context)
WorkspaceChart.mount(container, context)
ParamInspector.render(container, schema, values, onChange)
```

`StudioApp` owns company, slots, active demand, and calls the correct workspace. `WorkspaceImage` reuses SearchPanel and VariantSidebar. `WorkspaceChart` loads chart data, renders the inspector, updates preview through debounce, renders PNG variants, and delegates final selection to VariantSidebar/select.

- [ ] **Step 4: Run static contracts**

Run:

```bash
python3 -m unittest tests.test_static_contracts.StaticContractTests.test_image_studio_uses_demand_based_workspaces -v
```

Expected: pass.

## Task 4: Canvas Image Folder Reads All Finalized Assets

**Files:**
- Modify: `canvas/js/api-loader.js`
- Modify: `canvas/card-renderer.html`
- Modify: `canvas/js/html-card-renderer.js`
- Modify: `tests/test_static_contracts.py`

- [ ] **Step 1: Write failing static contract**

Add:

```python
def test_canvas_image_folder_supports_all_asset_keys(self):
    with open(os.path.join(ROOT, "canvas", "card-renderer.html"), encoding="utf-8") as f:
        html = f.read()
    with open(os.path.join(ROOT, "canvas", "js", "api-loader.js"), encoding="utf-8") as f:
        api_loader = f.read()
    with open(os.path.join(ROOT, "canvas", "js", "html-card-renderer.js"), encoding="utf-8") as f:
        renderer = f.read()

    self.assertIn("renderAllCompanyAssets", html)
    self.assertIn("website_screenshot", api_loader)
    self.assertIn("chart_competitive", api_loader)
    self.assertIn("chart_ecosystem", api_loader)
    self.assertIn("allAssets", renderer)
```

- [ ] **Step 2: Run test to verify red**

Run:

```bash
python3 -m unittest tests.test_static_contracts.StaticContractTests.test_canvas_image_folder_supports_all_asset_keys -v
```

Expected: fail because canvas still relies on limited map.

- [ ] **Step 3: Implement all-asset image folder support**

Add an all-assets array from `/api/assets/<company>` response and render it in the canvas image folder. Keep existing card auto-mapping for backward compatibility, but expose all ready assets as draggable/fillable items.

- [ ] **Step 4: Run static contract**

Run:

```bash
python3 -m unittest tests.test_static_contracts.StaticContractTests.test_canvas_image_folder_supports_all_asset_keys -v
```

Expected: pass.

## Task 5: Verification

**Files:**
- No new files.

- [ ] **Step 1: Run Python unit suite**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: pass.

- [ ] **Step 2: Run Python compile check**

Run:

```bash
python3 -m py_compile webapp/*.py
```

Expected: pass.

- [ ] **Step 3: Run screenshot CLI help check**

Run:

```bash
node canvas/screenshot.js --help
```

Expected: help output and exit 0.

- [ ] **Step 4: Report changed files and residual risks**

Summarize demand UI changes, backend/API changes, canvas image folder changes, tests run, and any remaining visual verification gap.
