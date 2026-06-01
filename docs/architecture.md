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
- `webapp/asset_store.py`: CRUD layer for `company_assets` table (7 asset types per company).
- `webapp/asset_pipeline.py`: automatic image collection pipeline. `collect_all_assets()` handles logo/office/product/competitors/other_products (legacy composite path). `collect_image_variants_pipeline()` runs during research as a visible pipeline stage, generating multi-source variants per card: office first creates and selects an OSM tile-composite map with HTML pin/legend, then appends Google Street View and Tavily office/street-view candidates; product_main uses Playwright screenshots plus Tavily app store/screenshot/review/ad searches; products_other uses Playwright plus Tavily per product; competitors uses Playwright, Tavily images/ad screenshots, and Clearbit logo fallback. Variants are stored in `image_variants`; slots that cannot find any images are marked `failed` for manual resolution in the image studio.
- `webapp/image_query.py`: builds structured image search strategies per slot from research data, with per-product and per-competitor URL-prioritised collection plans.
- `webapp/image_search.py`: multi-source image search (Pexels → Unsplash → Tavily) used by the image studio manual search interface.
- `webapp/infographic.py`: SVG template renderers for growth flywheel and development timeline infographics. LLM extracts structured JSON from Markdown, SVG template renders deterministically, Playwright screenshots to PNG.
- `prompts/`: prompt templates loaded by `webapp/deepseek_client.py`.
- `webapp/static/js/index.js`: research desk orchestration, research job polling, and finalization progress display as `confirmed/8`.
- `webapp/static/js/editor.js`: finalization desk orchestration, three-section accordion (content finalization / hook copy / image finalization), four-column line choice, hook-copy view, card confirmation, and embedded image-studio integration.
- `image-studio/`: standalone image finalization module with three-column layout (slot overview | middle search + candidate variants | right actions/import/current selected). Supports `?embed=1` for iframe integration into the editor; slot navigation moves to the editor accordion in embed mode.
- `image-studio/js/studio-app.js`: image studio main controller, slot loading, read-only logo/SVG slot handling.
- `image-studio/js/search-panel.js`: middle-panel variant library plus multi-source image search with pagination (Pexels / Unsplash / Tavily).
- `image-studio/js/variant-sidebar.js`: right-side actions for AI generation, map generation, current selected image, URL import, file upload, copyright disclosure modal, and SVG render button for infographic slots.
- `image-studio/js/query-gen.js`: smart query generation via DeepSeek Flash with localStorage caching.
- `canvas/`: HTML/CSS card workbench, single-card render page, and Puppeteer screenshot CLI.
- `canvas/js/api-loader.js`: loads card data from `/api/final/export?format=json` and assets from `/api/assets/<company>` when opened with `?company=`.
- `canvas/js/html-card-renderer.js`: converts parsed card data into editable `<style> + <article>` card source; maps asset images to card image boxes via `CARD_ASSET_MAP`.
- `canvas/js/source-editor.js`: syntax-highlighted HTML/CSS source editor with live iframe rendering.
- `canvas/screenshot.js`: screenshots cards 1-8 through Puppeteer.

## Research Pipeline

1. `POST /api/research/start` creates an in-memory job id and starts a daemon thread.
2. The pipeline collects Tavily, GitHub, YouTube, and website content in parallel. Tavily supports `TAVILY_API_KEYS` as a comma-separated fallback list; quota responses try the next key before marking the Tavily chain failed.
3. DeepSeek runs L0 cleaning, L1 horizontal/vertical analysis, L2 business analysis, and L3 field extraction for `standard`, `business`, and `spread`. If L3 misses `founder_edu` or `founder_achievement` while L0 has founder signals, that same L3 version retries once inside the main flow; there is no post-write补抓 pass.
4. If any L3 version fails, the job fails and records are not written.
5. Successful records are inserted into `research_db.sqlite`.
6. **Image collection** runs as a visible pipeline stage, collecting multi-source image variants for 4 card slots (office, product_main, products_other, competitors). The office slot defaults to the OSM map variant, then adds Street View/Tavily candidates as supplements. Each collector is best-effort: skipped sources do not block other sources or the overall pipeline. Variants are written to `image_variants` and status to `company_assets`.
7. On completion, the job stage is set to `done` with record IDs and total image counts.

The research desk surfaces per-chain collection status for Tavily, GitHub, YouTube, and website scraping, including result counts and failure details. The company library table expands one company at a time; clicking another company collapses the previous row and shows compact company facts plus a finalization entry, not the full standard/business/spread prose.

Job status is persisted in the `research_jobs` table. The `/api/research/status/<job_id>` endpoint checks in-memory state first and falls back to the database, so job status survives Flask restarts.

## Data Model

`research_db.sqlite` contains:
- `research`: generated research records, 3 rows per run (one per version).
- `research_jobs`: task lifecycle tracking (status, stage, error). Survives restarts; the status endpoint falls back to this table when the in-memory job dict is cold.

`final_db.sqlite` contains human-confirmed card content in `final_content`. The current finalization desk saves each confirmed card as one `markdown_full` field. Legacy field-level rows are still supported by the export path. The unique key is:

```text
company_name + card_index + field_name
```

Saving the same card again updates existing fields instead of inserting duplicates. `get_final_cards()` also cleans older duplicate rows before reading, keeping the latest row per field.

`assets_db.sqlite` contains the `company_assets` table tracking 7 image asset types per company:

```text
asset_key: logo | office | product_main | products_other | competitors | flywheel | timeline
card_index: 1-7 mapping asset to card (card 8 has no dedicated asset)
status:    missing → ready / generating / failed
```

Each row records `local_path`, `source_type` (favicon/web_search/screenshot/composite/svg_render/api_generate/web_scrape/osm_map/street_view/web_tavily/playwright/import_url/import_upload), `source_url`, `prompt`, and `meta_json`. The unique key is `(company_name, asset_key)`. Assets are collected via the pipeline (logo, office, product, other products, competitors) or generated on-demand (flywheel, timeline via SVG rendering).

`image_variants` stores downloaded image alternatives per asset slot, with copyright metadata:

```text
columns: id, company_name, asset_key, local_path, source_type (pexels/unsplash/tavily/url_import/file_upload/ai_generate),
         source_url, source_page, author, license, attribution_req, prompt, is_selected
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

- `GET /api/assets/<company>` — get all 7 assets for a company.
- `POST /api/assets/collect/<company>` — trigger automatic image collection (logo, office, product screenshot, other products, competitors).
- `POST /api/assets/generate/<company>/<asset_key>` — generate flywheel or timeline infographic via LLM → SVG → Playwright → PNG pipeline.

Image studio:

- `GET /image-studio/` — image studio page; accepts `?company=` and `?embed=1`.
- `GET /api/image-studio/<company>` — 7-slot overview with variant counts.
- `GET /api/image-studio/<company>/<asset_key>` — variant list for a slot.
- `POST /api/image-studio/<company>/<asset_key>/search` — multi-source image search (Pexels/Unsplash/Tavily).
- `POST /api/image-studio/<company>/<asset_key>/fetch` — download a candidate image, create variant, auto-select.
- `POST /api/image-studio/<company>/<asset_key>/generate-map` — regenerate the card 2 office map; only accepts `asset_key=office` and auto-selects the map variant.
- `POST /api/image-studio/<company>/<asset_key>/query` — DeepSeek Flash query generation for the slot.
- `POST /api/image-studio/<company>/<asset_key>/import` — URL import or file upload as variant.
- `PATCH /api/image-studio/<company>/<asset_key>/select` — select a variant as the slot's image.
- `DELETE /api/image-studio/<company>/<asset_key>/variants/<id>` — delete a variant.

SVG templates:

- `GET /api/svg-templates` — list built-in and uploaded Python SVG templates.
- `POST /api/svg-templates/upload` — upload a local Python SVG template; localhost only and requires `X-Template-Upload-Intent: local-dev`.
- `DELETE /api/svg-templates/<template_id>` — delete an uploaded template.
- `POST /api/svg-templates/preview` — render a template preview without selecting it for an asset.

Pages and static assets:

- `GET /` — research desk.
- `GET /editor` and `GET /editor?company=<company>` — finalization desk.
- `GET /editor/<company>` legacy-compatible editor route.
- `GET /canvas/` — card workbench. Use `?company=<company>` to load confirmed cards.
- `GET /canvas/card/<company>/<card_index>` — single-card HTML page for iframe preview and Puppeteer export. Valid indexes are 1-8.
- `GET /canvas/<path>`

`POST /api/generate-image` accepts the existing `company_name`, `field_name`, and `prompt` fields. It also accepts optional runtime `image_api_url` and `image_api_key`; these override environment defaults for that request only. The API key is never returned in the response.

## Card Workbench

The card workbench uses browser-native HTML/CSS layout instead of fabric.js. The center pane shows a scaled 3:4 iframe preview based on a `900 x 1200` card. The left pane is project-scoped: it displays the current company as read-only state from `?company=`, then uses mutually exclusive accordions for card navigation and the image folder. The image folder collects Markdown image URLs from confirmed cards plus generated images saved from the bottom prompt bar, and it contains the local background-watermark controls. Export controls stay outside the accordions so batch export is always visible. The right pane shows the current card's complete HTML+CSS source with local syntax highlighting; edits debounce-render into the iframe and can be saved per company/card in browser `localStorage`.

The workbench toolbar includes `返回定稿台`. With a company loaded, it links to `/editor?company=<company>`; without a company it falls back to `/editor`.

Image generation has been moved to the image studio (search panel). SVG infographics for cards 3 (timeline) and 6 (flywheel) are auto-generated on card confirmation in the editor using default templates; they can also be rendered manually with custom parameters in the image studio SVG editor.

`canvas/js/markdown-parser.js` supports current `markdown_full` exports and legacy field rows. It preserves remote and local Markdown images as `_image`, maps card 1 `# 公司名` plus bold-only subtitle into homepage fields, and maps unlabeled body text on cards 2 and 4 into the expected intro/product fields so the canvas does not drop finalized prose.

The CLI export path opens `/canvas/card/<company>/<card_index>` for each card and captures PNG files. The single-card page loads the same company assets as the full workbench, so selected image-studio variants appear in exported screenshots. Install Node dependencies with `npm install`, then run `node canvas/screenshot.js --company <company> --base-url http://127.0.0.1:5050`.

## Design Constraints

- Vanilla JS frontend; no React/Vue.
- `canvas/` main path uses HTML/CSS and iframe rendering; legacy fabric.js files may remain in the tree but are not referenced by `canvas/card-renderer.html`.
- SQLite through Python `sqlite3`; no ORM.
- Website scraping uses local `trafilatura` via `webapp/firecrawl_local.py`; no Firecrawl API.
- Cards 1-8 are generated. Card 7 is `竞争格局` and contains moat plus competitors; card 8 is `总结` and contains the market opportunity. `hook_paragraph_1/2/3` are displayed through the left-side `传播钩子文案` entry as supporting opening-copy options and are not written into cards.
