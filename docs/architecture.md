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
- `webapp/asset_pipeline.py`: automatic image collection pipeline (logo, office, product screenshot, competitor logos, other products composite).
- `webapp/infographic.py`: SVG template renderers for growth flywheel and development timeline infographics. LLM extracts structured JSON from Markdown, SVG template renders deterministically, Playwright screenshots to PNG.
- `prompts/`: prompt templates loaded by `webapp/deepseek_client.py`.
- `webapp/static/js/index.js`: research desk orchestration, research job polling, and finalization progress display as `confirmed/8`.
- `webapp/static/js/editor.js`: finalization desk orchestration, four-column line choice, hook-copy view, and card confirmation.
- `canvas/`: HTML/CSS card workbench, single-card render page, and Puppeteer screenshot CLI.
- `canvas/js/api-loader.js`: loads card data from `/api/final/export?format=json` and assets from `/api/assets/<company>` when opened with `?company=`.
- `canvas/js/html-card-renderer.js`: converts parsed card data into editable `<style> + <article>` card source; maps asset images to card image boxes via `CARD_ASSET_MAP`.
- `canvas/js/source-editor.js`: syntax-highlighted HTML/CSS source editor with live iframe rendering.
- `canvas/js/prompt-bar.js`: per-card image prompt editor and image API request wiring. Flywheel (card 6) and timeline (card 3) call `/api/assets/generate` for SVG-based rendering instead of generic image generation.
- `canvas/screenshot.js`: screenshots cards 1-8 through Puppeteer.

## Research Pipeline

1. `POST /api/research/start` creates an in-memory job id and starts a daemon thread.
2. The pipeline collects Tavily, GitHub, YouTube, and website content in parallel. Tavily supports `TAVILY_API_KEYS` as a comma-separated fallback list; quota responses try the next key before marking the Tavily chain failed.
3. DeepSeek runs L0 cleaning, L1 horizontal/vertical analysis, L2 business analysis, and L3 field extraction for `standard`, `business`, and `spread`.
4. If any L3 version fails, the job fails and records are not written.
5. Successful records are inserted into `research_db.sqlite`.
6. The finalization desk reads generated card Markdown per company/version.

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

Each row records `local_path`, `source_type` (favicon/web_search/screenshot/composite/svg_render/api_generate), `source_url`, `prompt`, and `meta_json`. The unique key is `(company_name, asset_key)`. Assets are collected via the pipeline (logo, office, product, other products, competitors) or generated on-demand (flywheel, timeline via SVG rendering).

## Routes

Research:

- `GET /api/companies`
- `GET /api/research/<company>`
- `GET /api/research/<company>/<version>`
- `GET /api/research/<company>/card/<card_index>?version=<version>`
- `POST /api/research/start`
- `GET /api/research/status/<job_id>`
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

The bottom prompt bar stores per-card prompts and generated image paths in browser `localStorage`. The API URL may be remembered locally, but the API key is kept only in page memory and sent only with the image generation request. For cards 3 (timeline) and 6 (flywheel), the generate button calls `/api/assets/generate` to produce an SVG-based infographic instead of a generic AI image.

`canvas/js/markdown-parser.js` supports current `markdown_full` exports and legacy field rows. It preserves remote and local Markdown images as `_image`, maps card 1 `# 公司名` plus bold-only subtitle into homepage fields, and maps unlabeled body text on cards 2 and 4 into the expected intro/product fields so the canvas does not drop finalized prose.

The CLI export path opens `/canvas/card/<company>/<card_index>` for each card and captures PNG files. Install Node dependencies with `npm install`, then run `node canvas/screenshot.js --company <company> --base-url http://127.0.0.1:5050`.

## Design Constraints

- Vanilla JS frontend; no React/Vue.
- `canvas/` main path uses HTML/CSS and iframe rendering; legacy fabric.js files may remain in the tree but are not referenced by `canvas/card-renderer.html`.
- SQLite through Python `sqlite3`; no ORM.
- Website scraping uses local `trafilatura` via `webapp/firecrawl_local.py`; no Firecrawl API.
- Cards 1-8 are generated. Card 7 is `竞争格局` and contains moat plus competitors; card 8 is `总结` and contains the market opportunity. `hook_paragraph_1/2/3` are displayed through the left-side `传播钩子文案` entry as supporting opening-copy options and are not written into cards.
