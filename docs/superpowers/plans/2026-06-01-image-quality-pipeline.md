# Image Quality Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace direct image acceptance with a candidate pool that records quality metadata, scores variants, auto-selects the best usable image, and exposes scoring/failure details in image-studio.

**Architecture:** Add small backend modules for candidate data, quality inspection, scoring, and screenshot capture. Extend `asset_store` as the single persistence API for scored variants, then route Tavily/OG/Playwright/manual imports through that API. Keep image-studio as the human confirmation layer.

**Tech Stack:** Python stdlib, Pillow, Flask, sqlite3, Playwright, Vanilla JS.

---

### Task 1: Data Contract

**Files:**
- Modify: `db/init_assets_db.sql`
- Modify: `webapp/asset_store.py`
- Test: `tests/test_db.py`

- [ ] Add tests proving `image_variants` persists width, height, file size, aspect ratio, quality/relevance/source/final scores, reject reason, and meta JSON.
- [ ] Add tests proving `select_variant()` writes `company_assets.selected_variant_id`, `final_score`, and `auto_selected`.
- [ ] Implement schema migrations in `ensure_assets_schema()` so existing DB files gain the new columns.

### Task 2: Candidate, Quality, Scoring

**Files:**
- Create: `webapp/image_candidate.py`
- Create: `webapp/image_quality.py`
- Create: `webapp/image_scorer.py`
- Test: `tests/test_image_quality.py`

- [ ] Add tests for small-image rejection, extreme-ratio rejection, corrupt-image rejection, logo minimums, and final score ordering.
- [ ] Implement `ImageCandidate`.
- [ ] Implement `inspect_local_image()` and `validate_candidate()`.
- [ ] Implement `score_candidate()` with source, quality, relevance, layout, copyright, and freshness components.

### Task 3: Candidate Persistence Helpers

**Files:**
- Modify: `webapp/asset_pipeline.py`
- Modify: `webapp/asset_store.py`
- Test: `tests/test_app.py`

- [ ] Add a helper that downloads/inspects/scores an `ImageCandidate`, saves accepted and rejected variants, and returns the persisted id.
- [ ] Ensure accepted candidates are ranked by `final_score`.
- [ ] Ensure failed slots write `company_assets.fail_reason`.

### Task 4: Source Collectors

**Files:**
- Modify: `webapp/asset_pipeline.py`
- Create: `webapp/screenshot_client.py`
- Test: `tests/test_pipeline.py`

- [ ] Tavily collectors must try up to 10 images, never `images[0]`.
- [ ] Add OG image extraction for official pages, About/Contact, and product pages.
- [ ] Add Product Hunt URL search and OG extraction for `product_main`.
- [ ] Wrap Playwright screenshots with page validity checks and failure reasons.

### Task 5: Image Studio UX/API

**Files:**
- Modify: `webapp/app.py`
- Modify: `image-studio/js/search-panel.js`
- Modify: `image-studio/js/variant-sidebar.js`
- Modify: `image-studio/css/studio.css`
- Test: `tests/test_static_contracts.py`

- [ ] Add `GET /api/image-studio/<company>/<asset_key>/variants`.
- [ ] Add `POST /api/image-studio/<company>/<asset_key>/rescore`.
- [ ] Render source, dimensions, scores, selected/auto-selected state, copyright, and reject reason.
- [ ] Default sort variants by `final_score` descending, with UI sort controls for score/source/size/time/selected.

### Task 6: Verification

**Files:**
- Modify: docs only when behavior changes need operator notes.

- [ ] Run `python3 -m unittest discover -s tests -v`.
- [ ] Run `python3 -m py_compile webapp/*.py`.
- [ ] Smoke the local Flask app and image-studio endpoint.
