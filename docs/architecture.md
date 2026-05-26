# Architecture

## System Flow

```text
Python research pipeline -> Flask editor -> final Markdown -> HTML/CSS card workbench -> Puppeteer PNG export
```

The app no longer depends on n8n for the main path. Research is started from the Flask research desk, processed in a background thread, stored in SQLite, then edited in the browser and sent to the HTML/CSS card workbench.

## Components

- `webapp/app.py`: Flask routes, background job status, static asset routes.
- `webapp/pipeline.py`: four-source collection, DeepSeek L0-L3 analysis, validation, database write.
- `webapp/db.py`: SQLite access helpers for research records, job tracking, and final card content.
- `prompts/`: prompt templates loaded by `webapp/deepseek_client.py`.
- `webapp/static/js/index.js`: research desk orchestration and research job polling.
- `webapp/static/js/editor.js`: finalization desk orchestration, four-column line choice, hook-copy view, and card confirmation.
- `canvas/`: HTML/CSS card workbench, single-card render page, and Puppeteer screenshot CLI.
- `canvas/js/api-loader.js`: loads card data from `/api/final/export?format=json` when opened with `?company=`.
- `canvas/js/html-card-renderer.js`: converts parsed card data into editable `<style> + <article>` card source.
- `canvas/js/source-editor.js`: syntax-highlighted HTML/CSS source editor with live iframe rendering.
- `canvas/js/prompt-bar.js`: per-card image prompt editor and image API request wiring.
- `canvas/screenshot.js`: screenshots cards 1-7 through Puppeteer.

## Research Pipeline

1. `POST /api/research/start` creates an in-memory job id and starts a daemon thread.
2. The pipeline collects Tavily, GitHub, YouTube, and website content in parallel.
3. DeepSeek runs L0 cleaning, L1 horizontal/vertical analysis, L2 business analysis, and L3 field extraction for `standard`, `business`, and `spread`.
4. If any L3 version fails, the job fails and records are not written.
5. Successful records are inserted into `research_db.sqlite`.
6. The finalization desk reads generated card Markdown per company/version.

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
- `POST /api/generate-image`
- `GET /images/<filename>`

Pages and static assets:

- `GET /` — research desk.
- `GET /editor` and `GET /editor?company=<company>` — finalization desk.
- `GET /editor/<company>` legacy-compatible editor route.
- `GET /canvas/` — card workbench. Use `?company=<company>` to load confirmed cards.
- `GET /canvas/card/<company>/<card_index>` — single-card HTML page for iframe preview and Puppeteer export. Valid indexes are 1-7.
- `GET /canvas/<path>`

`POST /api/generate-image` accepts the existing `company_name`, `field_name`, and `prompt` fields. It also accepts optional runtime `image_api_url` and `image_api_key`; these override environment defaults for that request only. The API key is never returned in the response.

## Card Workbench

The card workbench uses browser-native HTML/CSS layout instead of fabric.js. The center pane shows a scaled 3:4 iframe preview based on a `900 x 1200` card. The right pane shows the current card's complete HTML+CSS source with local syntax highlighting; edits debounce-render into the iframe and can be saved per company/card in browser `localStorage`.

The bottom prompt bar stores per-card prompts and generated image paths in browser `localStorage`. The API URL may be remembered locally, but the API key is kept only in page memory and sent only with the image generation request.

The CLI export path opens `/canvas/card/<company>/<card_index>` for each card and captures PNG files. Install Node dependencies with `npm install`, then run `node canvas/screenshot.js --company <company> --base-url http://127.0.0.1:5050`.

## Design Constraints

- Vanilla JS frontend; no React/Vue.
- `canvas/` main path uses HTML/CSS and iframe rendering; legacy fabric.js files may remain in the tree but are not referenced by `canvas/card-renderer.html`.
- SQLite through Python `sqlite3`; no ORM.
- Website scraping uses local `trafilatura` via `webapp/firecrawl_local.py`; no Firecrawl API.
- Card 8 is not generated. `hook_paragraph_1/2/3` are displayed through the left-side `传播钩子文案` entry as supporting opening-copy options.
