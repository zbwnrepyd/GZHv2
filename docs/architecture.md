# Architecture

## System Flow

```text
Python research pipeline -> Flask editor -> final Markdown -> fabric.js card renderer
```

The app no longer depends on n8n for the main path. Research is started from Flask, processed in a background thread, stored in SQLite, then edited and exported through the browser UI.

## Components

- `webapp/app.py`: Flask routes, background job status, static asset routes.
- `webapp/pipeline.py`: four-source collection, DeepSeek L0-L3 analysis, validation, database write.
- `webapp/db.py`: SQLite access helpers for research records, job tracking, and final card content.
- `prompts/`: prompt templates loaded by `webapp/deepseek_client.py`.
- `webapp/static/js/editor.js`: editor orchestration, field picking, research job polling.
- `canvas/`: standalone Markdown-to-card renderer using fabric.js.
- `canvas/js/api-loader.js`: loads card data from `/api/final/export?format=json` when opened with `?company=`.
- `canvas/js/thumbnail-nav.js`: generates small card previews for the left-side navigation.

## Research Pipeline

1. `POST /api/research/start` creates an in-memory job id and starts a daemon thread.
2. The pipeline collects Tavily, GitHub, YouTube, and website content in parallel.
3. DeepSeek runs L0 cleaning, L1 horizontal/vertical analysis, L2 business analysis, and L3 field extraction for `standard`, `business`, and `spread`.
4. If any L3 version fails, the job fails and records are not written.
5. Successful records are inserted into `research_db.sqlite`.
6. The editor reads the newest record per company/version.

Job status is persisted in the `research_jobs` table. The `/api/research/status/<job_id>` endpoint checks in-memory state first and falls back to the database, so job status survives Flask restarts.

## Data Model

`research_db.sqlite` contains:
- `research`: generated research records, 3 rows per run (one per version).
- `research_jobs`: task lifecycle tracking (status, stage, error). Survives restarts; the status endpoint falls back to this table when the in-memory job dict is cold.

`final_db.sqlite` contains human-confirmed card fields in `final_content`. The unique key is:

```text
company_name + card_index + field_name
```

Saving the same card again updates existing fields instead of inserting duplicates. `get_final_cards()` also cleans older duplicate rows before reading, keeping the latest row per field.

## Routes

Research:

- `GET /api/companies`
- `GET /api/research/<company>`
- `GET /api/research/<company>/<version>`
- `POST /api/research/start`
- `GET /api/research/status/<job_id>`
- `POST /api/research/save` legacy-compatible save endpoint

Editing and export:

- `POST /api/final/save`
- `GET /api/final/export/<company>` — returns Markdown by default. Add `?format=json` for structured data consumed by the canvas renderer.
- `GET /api/check/<company>`
- `POST /api/split-text`
- `POST /api/generate-image`
- `GET /images/<filename>`

Pages and static assets:

- `GET /editor/`
- `GET /canvas/`
- `GET /canvas/<path>`

## Design Constraints

- Vanilla JS frontend; no React/Vue.
- SQLite through Python `sqlite3`; no ORM.
- Website scraping uses local `trafilatura` via `webapp/firecrawl_local.py`; no Firecrawl API.
- Card 8 is not generated. Hook paragraphs are displayed as supporting text after card 7.
