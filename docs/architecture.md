# Architecture

## System Flow

```text
Python research pipeline -> Flask editor -> final Markdown -> HTML/CSS card workbench -> Puppeteer PNG export
```

The app no longer depends on n8n for the main path. Research is started from the Flask research desk, processed in a background thread, stored in SQLite, then edited in the browser and sent to the HTML/CSS card workbench.

## Components

- `webapp/app.py`: Flask routes, background job status, static asset routes, and asset API.
- `webapp/pipeline.py`: four-source collection, DeepSeek L0-L3 analysis, validation, database write.
- `webapp/db.py`: SQLite access helpers for research records, job tracking, and final card content.
- `webapp/asset_store.py`: CRUD layer for `company_assets` table (8 asset types per company).
- `webapp/competitive_scoring.py`: enum normalization and scoring formulas for defensibility, incumbent attention, value capture, and funding-stage bubble size. Also contains Chinese funding-round normalization (`FUNDING_CN_MAP`).
- `webapp/field_rules.py`: rule-layer enum extraction (no LLM). Infers `stack_layer` from `company_type` via 100+ keyword patterns. Scrapes `/pricing` page for `pricing_model` and `customer_segment_type` signals. Rule hits are passed to LLM Group C so it skips already-determined fields.
- `webapp/field_validator.py`: Pydantic `CompetitiveFields` model with per-field enum validation. `validate_enum_fields()` rejects illegal values before database write, preventing dirty data from reaching the scoring formulas.
- `webapp/asset_pipeline.py`: automatic image collection pipeline. `collect_all_assets()` handles logo/office/product/competitors/other_products (legacy composite path). `collect_image_variants_pipeline()` runs during research as a visible pipeline stage, generating multi-source variants per card: office first creates and selects an OSM tile-composite map with HTML pin/legend, then appends Google Street View and Tavily office/street-view candidates; product_main uses official `og:image`, Playwright screenshots, and Tavily app screenshot searches; products_other uses official `og:image`, Playwright, and Tavily per product; competitors uses official `og:image`, Playwright, Tavily images/ad screenshots, and Clearbit logo fallback. Downloaded candidates are inspected, filtered, scored, and stored in `image_variants`; slots that cannot find any usable images are marked `failed` with a reason for manual resolution in image studio.
- `webapp/image_candidate.py`: normalized `ImageCandidate` dataclass used by collectors, quality checks, and scoring.
- `webapp/image_quality.py`: Pillow-based hard filters for dimensions, file size, corrupt files, extreme ratios, tracking pixels, and pure-color images.
- `webapp/image_scorer.py`: rule-based `final_score` calculator using source, quality, relevance, layout, copyright, and freshness scores.
- `webapp/screenshot_client.py`: screenshot abstraction. The first implementation uses local Playwright and rejects login/captcha/Cloudflare/empty pages before saving screenshots.
- `webapp/image_query.py`: builds structured image search strategies per slot from research data, with per-product and per-competitor URL-prioritised collection plans.
- `webapp/image_search.py`: multi-source image search (Pexels → Unsplash → Tavily) used by the image studio manual search interface.
- `webapp/infographic.py`: SVG/HTML renderers for infographics. Flywheel/timeline use LLM-extracted JSON → SVG templates → Playwright PNG. Competitive positioning scatter plots use Frappe Charts CDN rendered in an HTML page → Playwright screenshot at 2x deviceScaleFactor. All rendered via `_html_to_png()` for sharp output.
- `prompts/`: prompt templates loaded by `webapp/deepseek_client.py`.
- `webapp/static/js/index.js`: research desk orchestration, research job polling, and finalization progress display as `confirmed/8`.
- `webapp/static/js/editor.js`: finalization desk orchestration, three-section accordion (content finalization / hook copy / image finalization), four-column line choice, hook-copy view, card confirmation, and embedded image-studio integration.
- `image-studio/`: standalone image finalization module with three-column layout (slot overview | middle preview + toolbar or chart bar | right candidate thumbnails/code + confirm). Two slot modes: **image slots** (logo/office/website_screenshot/product/competitors/competitors_logo_strip) use preview/search toggle + toolbar; **chart slots** (flywheel/timeline/chart_competitive/chart_ecosystem) use a proportional real-time iframe preview, bottom parameter bar, and right-side code/action dock with the final confirm button. Supports `?embed=1` for iframe integration into the editor; slot navigation moves to the editor accordion in embed mode.
- `image-studio/js/studio-app.js` and `image-studio/js/workspace-chart.js`: main controllers. Generated chart slots are routed to the chart workspace: flywheel/timeline use SVG template params + preview; chart_competitive/chart_ecosystem use editable ECharts/HTML preview with syntax-highlighted code and live application.
- `image-studio/js/search-panel.js`: middle panel for image slots — preview/search toggle bar, large preview stage, search results grid with pagination, and toolbar (search bar + engine selector, recollect all/slot, AI generation, upload, URL import).
- `image-studio/js/variant-sidebar.js`: right panel — 2-column candidate thumbnail grid with sort control, preview highlighting, delete, and "确定图片" confirm button.
- `canvas/`: HTML/CSS card workbench, single-card render page, and Puppeteer screenshot CLI.
- `canvas/js/render-data-loader.js` and `canvas/js/template-renderer.js`: dynamic GZHv2 renderer path. The card workbench, layout center, and single-card page first load `/api/render-data/<company>` and render enabled `card_compositions`; the legacy fixed-card renderer remains as fallback. Text regions support Markdown `value` overrides from layout editing; an override takes precedence over field items for that region.
- `webapp/static/js/layout/layout-app.js`: layout center controller. It renders selected cards into a scaled iframe, overlays parent-page transparent region hitboxes for layer selection, opens a Markdown textarea inside text regions on double-click, writes text/geometry/style changes into layout overrides, and saves them through `/api/layout/<company>/<card_id>`.
- `canvas/js/api-loader.js`: legacy fallback loader for `/api/final/export?format=json` and `/api/assets/<company>`.
- `canvas/js/html-card-renderer.js`: converts parsed card data into editable `<style> + <article>` card source; maps asset images to card image boxes via `CARD_ASSET_MAP`.
- `canvas/js/source-editor.js`: syntax-highlighted HTML/CSS source editor with live iframe rendering.
- `canvas/js/param-controls.js`: collapsible parameter-tuning bar in the card workbench. Renders accordion sliders/color-pickers for typography, colors, spacing, and layout. Changes are debounced and injected directly into the iframe via `renderSourceIntoDocument()`. Params persist in localStorage key `aistartups.paramTuning`.
- `canvas/screenshot.js`: loads enabled cards from `/api/render-data/<company>` and screenshots each card through Puppeteer; falls back to legacy 1-8 only when render-data is unavailable.

## Research Pipeline

1. `POST /api/research/start` creates an in-memory job id and starts a daemon thread.
2. The pipeline collects Tavily, GitHub, YouTube, and website content in parallel. Tavily supports `TAVILY_API_KEYS` as a comma-separated fallback list; quota responses try the next key before marking the Tavily chain failed.
3. DeepSeek runs L0 cleaning, L1 horizontal/vertical analysis, L2 business analysis, and L3 field extraction for `standard`, `business`, and `spread`. After each L3 call, the 10 competitive-positioning enum fields are overridden through a three-layer flow: Rule layer (`field_rules.py` — pricing-page scraping + keyword inference) → LLM layer (3 independent groups A/B/C, each extracting 3 fields, max_tokens=200) → Pydantic validation (`field_validator.py`). Three key fields (`ai_model_dependency`, `incumbent_direct_competitor`, `pricing_model`) receive majority voting (2-3 rounds). If L3 misses `founder_edu` or `founder_achievement` while L0 has founder signals, that same L3 version retries once inside the main flow; there is no post-write补抓 pass.
4. If any L3 version fails, the job fails and records are not written.
5. Successful records are inserted into `research_db.sqlite`.
6. **Image collection** runs as a visible pipeline stage, collecting multi-source image variants for 4 card slots (office, product_main, products_other, competitors). Tavily collectors try up to 10 returned images per query and never accept the first URL directly. The office slot defaults to the OSM map variant, then adds Street View/Tavily candidates as supplements. Product and competitor slots first try official `og:image`, then validated screenshots and Tavily candidates. Each collector is best-effort: skipped sources do not block other sources or the overall pipeline. Variants are written to `image_variants`; accepted variants receive scores, rejected variants keep `reject_reason`, and `company_assets` records the selected variant and final score.
7. On completion, the job stage is set to `done` with record IDs and total image counts.

The research desk surfaces per-chain collection status for Tavily, GitHub, YouTube, and website scraping, including result counts and failure details. The company library table expands one company at a time; clicking another company collapses the previous row and shows compact company facts plus a finalization entry, not the full standard/business/spread prose.

Job status is persisted in the `research_jobs` table. The `/api/research/status/<job_id>` endpoint checks in-memory state first and falls back to the database, so job status survives Flask restarts.

## Data Model

`research_db.sqlite` contains:
- `research`: generated research records, 3 rows per run (one per version). It also stores competitive-positioning enum fields (`ai_model_dependency`, `workflow_integration_level`, `data_flywheel`, `proprietary_data_asset`, `incumbent_direct_competitor`, `customer_segment_type`, `funding_stage`, `pricing_model`, `inference_cost_exposure`, `stack_layer`) plus cached scores (`funding_stage_score`, `score_defensibility`, `score_incumbent_attention`, `score_value_capture`).
- `research_jobs`: task lifecycle tracking (status, stage, error). Survives restarts; the status endpoint falls back to this table when the in-memory job dict is cold.

`final_db.sqlite` contains human-confirmed card content in `final_content`. The current finalization desk saves each confirmed card as one `markdown_full` field. Legacy field-level rows are still supported by the export path. The unique key is:

```text
company_name + card_index + field_name
```

Saving the same card again updates existing fields instead of inserting duplicates. `get_final_cards()` also cleans older duplicate rows before reading, keeping the latest row per field.

`assets_db.sqlite` contains the `company_assets` table tracking demand-based media asset types per company:

```text
asset_key: logo | website_screenshot | office | product_main | products_other |
           competitors | competitors_logo_strip | flywheel | timeline |
           chart_competitive | chart_ecosystem
card_index: compatibility hint only; card placement is controlled by card_items
status:    missing → ready / generating / failed
selected_variant_id / final_score / auto_selected / fail_reason: final selection metadata
```

Each row records `local_path`, `source_type` (favicon/web_search/screenshot/composite/svg_render/api_generate/web_scrape/osm_map/street_view/web_tavily/playwright/import_url/import_upload), `source_url`, `prompt`, `selected_variant_id`, `final_score`, `auto_selected`, `fail_reason`, and `meta_json`. The unique key is `(company_name, asset_key)`. Assets are collected via the pipeline (logo, office, website/product screenshots, competitors), generated on-demand (competitors_logo_strip, flywheel, timeline, chart_competitive, chart_ecosystem), or manually imported/generated in image studio.

`image_variants` stores downloaded image alternatives per asset slot, with copyright metadata:

```text
columns: id, company_name, asset_key, local_path, source_type,
         source_url, source_page, author, license, attribution_req, prompt,
         width, height, file_size, aspect_ratio,
         quality_score, relevance_score, source_score, final_score,
         reject_reason, meta_json, is_selected
```

Selecting a variant marks it `is_selected` and writes its `local_path` back to `company_assets`. Only one variant per slot is selected at a time.

## Routes

Research:

- `GET /api/companies`
- `GET /api/research/<company>`
- `GET /api/research/<company>/<version>`
- `GET /api/research/<company>/card/<card_index>?version=<version>`
- `POST /api/research/start`
- `GET /api/research/status/<job_id>`
- `DELETE /api/research/<company>` — 真删除公司全部数据（3 DB × 5 表 + images 目录），不可恢复
- `POST /api/research/save` legacy-compatible save endpoint

Editing and export:

- `POST /api/final/save`
- `GET /api/final/status/<company>`
- `GET /api/final/export/<company>` — returns Markdown by default. Add `?format=json` for structured data consumed by the canvas renderer.
- `GET /api/check/<company>`
- `POST /api/split-text`
- `POST /api/generate-image` — accepts optional `asset_key` to also write into `company_assets`.
- `GET /images/<filename>`

Asset system:

- `GET /api/assets/<company>` — get all assets for a company.
- `POST /api/assets/collect/<company>` — trigger automatic image collection (logo, office, product screenshot, other products, competitors). Add `?asset_key=office` to collect only one slot.
- `POST /api/assets/generate/<company>/<asset_key>` — generate flywheel or timeline infographic via LLM → SVG → Playwright → PNG pipeline.

Image studio:

- `GET /image-studio/` — image studio page; accepts `?company=` and `?embed=1`.
- `GET /api/image-studio/<company>` — slot overview with variant counts.
- `GET /api/image-studio/<company>/<asset_key>` — variant list for a slot.
- `GET /api/image-studio/<company>/<asset_key>/variants` — same variant list, explicit scored-candidate endpoint.
- `POST /api/image-studio/<company>/<asset_key>/search` — multi-source image search (Pexels/Unsplash/Tavily).
- `POST /api/image-studio/<company>/<asset_key>/fetch` — download a candidate image, create variant, auto-select.
- `POST /api/image-studio/<company>/<asset_key>/generate-map` — regenerate the card 2 office map; only accepts `asset_key=office` and auto-selects the map variant.
- `POST /api/image-studio/<company>/<asset_key>/query` — DeepSeek Flash query generation for the slot.
- `POST /api/image-studio/<company>/<asset_key>/import` — URL import or file upload as variant.
- `POST /api/image-studio/<company>/<asset_key>/rescore` — recompute rule-based scores for existing variants and auto-select the highest scored candidate.
- `PATCH /api/image-studio/<company>/<asset_key>/select` — select a variant as the slot's image.
- `DELETE /api/image-studio/<company>/<asset_key>/variants/<id>` — delete a variant.

SVG templates:

- `GET /api/svg-templates` — list built-in and uploaded Python SVG templates.
- `POST /api/svg-templates/upload` — upload a local Python SVG template; localhost only and requires `X-Template-Upload-Intent: local-dev`.
- `DELETE /api/svg-templates/<template_id>` — delete an uploaded template.
- `POST /api/svg-templates/preview` — render a template preview without selecting it for an asset.

Generated charts:

- `POST /api/image-studio/<company>/chart_competitive/render-html` — save a hand-edited ECharts/HTML competitive landscape version.
- `POST /api/image-studio/<company>/chart_ecosystem/render-html` — save a hand-edited ECharts/HTML AI stack positioning version.
- `POST /api/image-studio/<company>/<asset_key>/render-svg` — render SVG-template chart assets such as flywheel and timeline.
- `POST /api/media/<company>/<media_key>/generate` — stable media API wrapper that dispatches generated slots to the current renderer.

Pages and static assets:

- `GET /` — research desk.
- `GET /editor` and `GET /editor?company=<company>` — finalization desk.
- `GET /editor/<company>` legacy-compatible editor route.
- `GET /layout`, `GET /layout?company=<company>`, and `GET /layout/<company>` — layout center for template selection, layer editing, and PNG export dialog.
- `GET /template-maker` — template creation and editing UI.
- `GET /canvas/` — card workbench. Use `?company=<company>` to load confirmed cards.
- `GET /canvas/card/<company>/<card_id>` — single-card HTML page for iframe preview and Puppeteer export. `card_id` may be a dynamic ID such as `card_06`; numeric legacy IDs still work.
- `GET /canvas/<path>`

`POST /api/generate-image` accepts the existing `company_name`, `field_name`, and `prompt` fields. It also accepts optional runtime `image_api_url` and `image_api_key`; these override environment defaults for that request only. The API key is never returned in the response.

Layout persistence:

- `GET /api/layout/<company>/<card_id>` — return the saved layout instance for one card.
- `PATCH /api/layout/<company>/<card_id>` — merge `overrides` into the card layout instance. Region overrides may contain geometry/style keys and text `value`.
- `POST /api/layout/<company>/<card_id>/reset` — delete the saved layout instance and fall back to template defaults.

## Layout Center And Card Workbench

The layout center at `/layout?company=<company>` is the main visual layout editor. It loads `/api/render-data/<company>`, lets the user choose a card and template, then exposes template regions as layers. Selecting a layer updates the right-side property panel and adds a cyan highlight inside the iframe preview. Geometry and style controls write region patches to layout overrides.

Text editing deliberately does not rely on browser `contentEditable` in the iframe. The iframe itself is rendered with pointer events disabled, and the parent page places transparent hitboxes over each region. This prevents double-clicking text from creating a browser-native blue selection across the whole card. When a text hitbox is double-clicked, the parent page opens a focused Markdown `<textarea>` inside the matching iframe region, temporarily lets pointer events reach the iframe for editing, and commits the raw Markdown to the region's `value` override on blur or Cmd/Ctrl+Enter. Escape cancels and re-renders the preview. `TemplateRenderer` then renders that `value` through its Markdown parser, so headings and `**bold**` survive layout re-renders and exports.

## Card Workbench

The card workbench uses browser-native HTML/CSS layout instead of fabric.js. The center pane shows a scaled 3:4 iframe preview based on a `900 x 1200` card. The left pane is project-scoped: it displays the current company as read-only state from `?company=`, then uses mutually exclusive accordions for card navigation, template selection, and the image folder. The template system is global (shared across all companies) and stores full HTML+CSS source sets (8 cards) in browser `localStorage`; templates can be imported/exported as JSON. On first visit, default templates are auto-loaded from `/canvas/default-templates.json`. The right pane shows the current card's complete HTML+CSS source with local syntax highlighting; edits debounce-render into the iframe.

The workbench toolbar includes `返回定稿台` and `参数编辑器`. With a company loaded, `返回定稿台` links to `/editor?company=<company>`; without a company it falls back to `/editor`. The `参数编辑器` button toggles a collapsible parameter-tuning bar below the iframe preview, containing single-accordion sliders/color-pickers for typography, colors, spacing, and layout. Changes are injected directly into the iframe via `renderSourceIntoDocument()`.

SVG infographics for cards 3 (timeline) and 6 (flywheel) are auto-generated on card confirmation in the editor using default templates; they can also be rendered manually with custom parameters in the image studio SVG editor. Card 6 confirmation also auto-generates two scatter-plot positioning charts (competitive landscape matrix and AI stack positioning map), displayed as thumbnails in the editor's right preview pane.

`canvas/js/markdown-parser.js` supports current `markdown_full` exports and legacy field rows. It preserves remote and local Markdown images as `_image`, maps card 1 `# 公司名` plus bold-only subtitle into homepage fields, and maps unlabeled body text on cards 2 and 4 into the expected intro/product fields so the canvas does not drop finalized prose.

The CLI export path opens `/canvas/card/<company>/<card_index>` for each card and captures PNG files. The single-card page loads the same company assets as the full workbench, so selected image-studio variants appear in exported screenshots. Install Node dependencies with `npm install`, then run `node canvas/screenshot.js --company <company> --base-url http://127.0.0.1:5050`.

## Design Constraints

- Vanilla JS frontend; no React/Vue.
- `canvas/` main path uses HTML/CSS and iframe rendering; legacy fabric.js files may remain in the tree but are not referenced by `canvas/card-renderer.html`.
- SQLite through Python `sqlite3`; no ORM.
- Website scraping uses local `trafilatura` via `webapp/firecrawl_local.py`; no Firecrawl API.
- Cards 1-8 are generated. Card 7 is `竞争格局` and contains moat (now expanded to include ecosystem/niche analysis: value chain, niche overlap scoring, differentiation strategy, evolution trends) plus competitors; card 8 is `总结` and contains the market opportunity. `hook_paragraph_1/2/3` are displayed through the left-side `传播钩子文案` entry as supporting opening-copy options and are not written into cards.
