# Architecture

## System Flow

```text
Python research pipeline -> Flask editor -> final Markdown -> fabric.js card renderer
```

The app no longer depends on n8n for the main path. Research is started from Flask, processed in a background thread, stored in SQLite, then edited and exported through the browser UI.

## Components

- `webapp/app.py`: Flask routes, background job status, static asset routes.
- `webapp/pipeline.py`: four-source collection, DeepSeek L0-L3 analysis, validation, database write.
- `webapp/db.py`: SQLite access helpers for research records and final card content.
- `prompts/`: prompt templates loaded by `webapp/deepseek_client.py`.
- `webapp/static/js/editor.js`: editor orchestration, field picking, research job polling.
- `canvas/`: standalone Markdown-to-card renderer using fabric.js.

## Research Pipeline

1. `POST /api/research/start` creates an in-memory job id and starts a daemon thread.
2. The pipeline collects Tavily, GitHub, YouTube, and website content in parallel.
3. DeepSeek runs L0 cleaning, L1 horizontal/vertical analysis, L2 business analysis, and L3 field extraction for `standard`, `business`, and `spread`.
4. If any L3 version fails, the job fails and records are not written.
5. Successful records are inserted into `research_db.sqlite`.
6. The editor reads the newest record per company/version.

Job status is stored in process memory. Restarting Flask clears job status, but already-written database records remain.

## Data Model

`research_db.sqlite` contains generated research records in `research`. Each run normally writes three rows: one per version.

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
- `GET /api/final/export/<company>`
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
