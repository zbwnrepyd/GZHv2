# Architecture

## System Flow

```text
Python research pipeline -> Flask editor -> final Markdown -> HTML/CSS card workbench -> Puppeteer PNG export
```

The app no longer depends on n8n for the main path. Research is started from the Flask research desk, processed in a background thread, stored in SQLite, then edited in the browser and sent to the HTML/CSS card workbench.

## Components

- `webapp/app.py`: Flask routes, background job status, static asset routes, and asset API.
- `webapp/pipeline.py`: four-source collection, DeepSeek L0-L3 analysis, validation, database write.
- `webapp/db.py`: SQLite access helpers for research records, job tracking, final fields, and legacy final card content.
- `db/migrate.py`: idempotent SQLite migration runner. It records applied SQL files in `schema_migrations`; app startup initializes composition/template DBs and applies research/final migrations including evidence, field-resolution, and v3 field extensions.
- `webapp/path_safety.py`: shared path-segment sanitizer for company image directories and media upload paths.
- `webapp/asset_store.py`: CRUD layer for `company_assets` table (12 asset keys per company: 9 active slots plus legacy `office/products_other/timeline` rows retained for compatibility).
- `webapp/research/`: evidence persistence and field-resolution helpers. The pipeline writes scored evidence to `evidence_items`, marks each `research_fields` row as confirmed/derived/proxy/unavailable/manual_needed/not_applicable/llm_extracted, and records gap-audit events in `field_resolution_logs`.
- `references/field_manifest.yaml`, `references/source_policy.md`, `references/unavailable_policy.md`: field availability policy. They define which fields can be confirmed from public evidence, which are formula-derived, which may be market proxies, and which private operating metrics should remain unavailable instead of being guessed.
- `webapp/competitive_scoring.py`: enum-to-score mapping and v2 scoring formulas for defensibility, incumbent attention, and value capture (5+4+4 sub-item framework). New fields resolved with fallback to legacy 10-field mapping for backward compatibility. Also contains Chinese funding-round normalization (`FUNDING_CN_MAP`).
- `webapp/field_rules.py`: rule-layer enum extraction (no LLM). Infers `stack_layer` from `company_type` via 100+ keyword patterns. Scrapes `/pricing` page for `pricing_model` and `customer_segment_type` signals. Rule hits are passed to LLM Group C so it skips already-determined fields.
- `webapp/field_validator.py`: Pydantic `CompetitiveFields` model with per-field enum validation. `validate_enum_fields()` rejects illegal values before database write, preventing dirty data from reaching the scoring formulas.
- `webapp/asset_pipeline.py`: automatic image collection pipeline. `collect_all_assets()` keeps the legacy composite path for logo/office/product/competitors/other_products. `collect_image_variants_pipeline()` runs during research as a visible pipeline stage, generating multi-source variants for active slots: website screenshots, product_main, founder_photo where available, competitors, and v1/legacy office map supplements. Office first creates and selects an OSM tile-composite map with HTML pin/legend, then appends Google Street View and Tavily office/street-view candidates; product_main uses official `og:image`, Playwright screenshots, and Tavily app screenshot searches; competitors uses official `og:image`, Playwright, Tavily images/ad screenshots, and Clearbit logo fallback. Downloaded candidates are inspected, filtered, scored, and stored in `image_variants`; slots that cannot find any usable images are marked `failed` with a reason for manual resolution in image studio.
- `webapp/image_candidate.py`: normalized `ImageCandidate` dataclass used by collectors, quality checks, and scoring.
- `webapp/image_quality.py`: Pillow-based hard filters for dimensions, file size, corrupt files, extreme ratios, tracking pixels, and pure-color images.
- `webapp/image_scorer.py`: rule-based `final_score` calculator using source, quality, relevance, layout, copyright, and freshness scores.
- `webapp/screenshot_client.py`: screenshot abstraction. The first implementation uses local Playwright and rejects login/captcha/Cloudflare/empty pages before saving screenshots.
- `webapp/image_query.py`: builds structured image search strategies per slot from research data, with per-product and per-competitor URL-prioritised collection plans.
- `webapp/image_search.py`: multi-source image search (Pexels → Unsplash → Tavily) used by the image studio manual search interface.
- `webapp/infographic.py`: SVG/HTML renderers for infographics. Flywheel/timeline use LLM-extracted JSON → SVG templates → Playwright PNG. chart_competitive（竞争格局定位图）和 chart_ecosystem（AI 栈生态位图）使用 ECharts HTML：0–10 绝对坐标（不做归一化）、动态标题给结论、markArea 象限背景（x=5/y=5 中轴）、目标公司高亮（青色 `#29B8D4` 白边框 2px 固定 22px 气泡）、竞品降权（`rgba(27,42,74,0.35)` 14px 气泡）、全员标签展示。ecosystem Y 轴为 5 条 category 泳道（分发渠道→垂直应用→中间件层→模型层→基础设施层）+ splitArea 交替背景。800×600 → Playwright 2x PNG。内联 `webapp/static/vendor/echarts.min.js`，不依赖 CDN。CSS 禁用 vw/vh（srcdoc iframe 坍塌），使用 `position:absolute;inset:0`。
- `prompts/`: prompt templates loaded by `webapp/deepseek_client.py`.
- `webapp/static/js/index.js`: research desk orchestration, research job polling, source-chain status, recent-event display, and finalization progress display from `final_fields` when available.
- `webapp/static/js/editor.js`: finalization desk orchestration. Left navigation has card settings, text finalization, image finalization, and a fixed bottom “进入排版” link; the three work panels are mutually exclusive overlays.
- `image-studio/`: standalone image finalization module with three-column layout (slot overview | middle preview + toolbar or chart bar | right candidate thumbnails/code + confirm). Two slot modes: **image slots** (logo/website_screenshot/founder_photo/product_main/competitors/competitors_logo_strip plus compatibility office/products_other) use preview/search toggle + toolbar; **chart slots** (flywheel/timeline/chart_competitive/chart_ecosystem) use a proportional real-time iframe preview, bottom parameter bar, and right-side code/action dock with the final confirm button. Supports `?embed=1` for iframe integration into the editor; slot navigation moves to the editor accordion in embed mode.
- `image-studio/js/studio-app.js` and `image-studio/js/workspace-chart.js`: main controllers. Generated chart slots are routed to the chart workspace: flywheel/timeline use SVG template params + preview; chart_competitive/chart_ecosystem use editable ECharts/HTML preview with syntax-highlighted code and live application.
- `image-studio/js/search-panel.js`: middle panel for image slots — preview/search toggle bar, large preview stage, search results grid with pagination, and toolbar (search bar + engine selector, recollect all/slot, AI generation, upload, URL import).
- `image-studio/js/variant-sidebar.js`: right panel — 2-column candidate thumbnail grid with sort control, preview highlighting, delete, and "确定图片" confirm button.
- `canvas/`: HTML/CSS card workbench, single-card render page, and Puppeteer screenshot CLI.
- `canvas/js/render-data-loader.js` and `canvas/js/template-renderer.js`: dynamic renderer path. The card workbench, layout center, and single-card page first load `/api/render-data/<company>` and render enabled `card_compositions`; single-card loads preserve `?set=v1|v2|v3` for dynamic IDs such as `v2_card_01` or `v3_card_01`. The legacy fixed-card renderer remains as fallback. Text regions support Markdown `value` overrides from layout editing; an override takes precedence over field items for that region.
- `webapp/static/js/layout/layout-app.js`: layout center controller. It renders selected cards into a scaled iframe, overlays parent-page transparent region hitboxes for layer selection, opens a Markdown textarea inside text regions on double-click, writes text/geometry/style changes into layout overrides, and saves them through `/api/layout/<company>/<card_id>`.
- `canvas/js/api-loader.js`: legacy fallback loader for `/api/final/export?format=json` and `/api/assets/<company>`.
- `canvas/js/html-card-renderer.js`: converts parsed card data into editable `<style> + <article>` card source; maps asset images to card image boxes via `CARD_ASSET_MAP`.
- `canvas/js/source-editor.js`: syntax-highlighted HTML/CSS source editor with live iframe rendering.
- `canvas/js/param-controls.js`: collapsible parameter-tuning bar in the card workbench. Renders accordion sliders/color-pickers for typography, colors, spacing, and layout. Changes are debounced and injected directly into the iframe via `renderSourceIntoDocument()`. Params persist in localStorage key `aistartups.paramTuning`.
- `canvas/screenshot.js`: loads enabled cards from `/api/render-data/<company>?set=v1|v2|v3` and screenshots each card through Puppeteer; `--set` defaults to `v1`, and fallback to legacy 1-8 is used only when render-data is unavailable.
- `webapp/services/export_service.py`: asynchronous PNG/ZIP export for render-data cards plus v3-oriented Markdown/PDF/Notion bundle generation through `render_export_bundle()`.

## Research Pipeline

1. `POST /api/research/start` creates an in-memory job id and starts a daemon thread.
2. The pipeline collects Tavily, GitHub, YouTube, and website content in parallel. Tavily supports `TAVILY_API_KEYS` as a comma-separated fallback list; quota responses try the next key before marking the Tavily chain failed. The default deep Tavily budget is 24 planned queries, but adaptive mode initially runs the first 10 as `basic` queries without raw content, evaluates evidence coverage, and escalates only missing high-priority intents to `advanced` queries. Repeated Tavily calls are cached by query/depth/raw-content/max-results for `TAVILY_CACHE_TTL_SECONDS` (default 86400). Deep Tavily plans cover overview/founders/funding/product plus operating metric intents: market size, revenue metrics, user metrics, retention metrics, unit economics, and capital efficiency. Tavily queues report partial progress after each query so the research desk does not stay at "waiting" until the whole queue completes.
3. DeepSeek runs L0 cleaning, L1 horizontal/vertical analysis, L2 business analysis, and L3 field extraction for `standard`, `business`, and `spread`. After each L3 call, the 10 competitive-positioning enum fields are overridden through a three-layer flow: Rule layer (`field_rules.py` — pricing-page scraping + keyword inference) → LLM layer (3 independent groups A/B/C, each extracting 3 fields, max_tokens=200) → Pydantic validation (`field_validator.py`). Three key fields (`ai_model_dependency`, `incumbent_direct_competitor`, `pricing_model`) receive majority voting (2-3 rounds). If L3 misses `founder_edu` or `founder_achievement` while L0 has founder signals, that same L3 version retries once inside the main flow; there is no post-write补抓 pass.
4. The evidence pool is de-duplicated/scored and persisted to `evidence_items`. Metric snippets are retained for operating-metric audit scripts.
5. If any L3 version fails, the job fails and records are not written.
6. Successful records are inserted into `research_db.sqlite`, then split into `research_fields`. Field-resolution status is written after field insertion; failure to write audit metadata does not block the main research record.
7. **Image collection** runs as a visible pipeline stage, collecting multi-source image variants for active render slots plus v1/legacy compatibility slots. Tavily collectors try up to 10 returned images per query and never accept the first URL directly. The office slot defaults to the OSM map variant, then adds Street View/Tavily candidates as supplements. Product, founder, website screenshot, and competitor slots first try official or high-confidence sources where possible, then validated screenshots and Tavily candidates. Each collector is best-effort: skipped sources do not block other sources or the overall pipeline. Variants are written to `image_variants`; accepted variants receive scores, rejected variants keep `reject_reason`, and `company_assets` records the selected variant and final score.
8. On completion, the job stage is set to `done` with record IDs and total image counts.

The research desk surfaces per-chain collection status for Tavily, GitHub, YouTube, and website scraping, including result counts and failure details. The company library table expands one company at a time; clicking another company collapses the previous row and shows compact company facts plus a finalization entry, not the full standard/business/spread prose.

Job status is persisted in the `research_jobs` table. The `/api/research/status/<job_id>` endpoint checks in-memory state first and falls back to the database, so job status survives Flask restarts.

## Evidence & Field Resolution Pipeline

After L3 field extraction, the pipeline runs three additional stages before image collection:

1. **Evidence span binding** (`_bind_evidence_spans`, gated by `EVIDENCE_SPAN_BINDING_ENABLED=1`): mirrors evidence_pool items into `source_documents`, then matches field values against document content by keyword overlap, creating `evidence_spans` rows. Failed matches do not block the pipeline.
2. **Forum moderation** (`_run_forum_moderation`): runs `ForumModerator.audit_batch()` against all resolved fields, checking for weak evidence (confirmed without evidence_spans), missing market context (region/segment/year), private metrics incorrectly marked confirmed, and multi-candidate conflicts. Produces `weak_evidence_fields`, `conflict_fields`, `refetch_tasks`. Printed to logs; errors do not block the pipeline.
3. **Orchestrator agents** (`_run_orchestrator_agents`, gated by `ORCHESTRATOR_ENABLED=1`, default off): runs the multi-agent orchestrator to collect additional field_candidates from MediaAgent, GitHubAgent, CommunityAgent, and InsightAgent. Candidates are persisted to `field_candidates` and merged into the evidence pool.

Field status follows a unified enum: `confirmed` | `derived` | `proxy` | `industry_avg` | `llm_extracted` | `manual_needed` | `unavailable` | `not_applicable` | `conflict` | `draft` | `hidden`. LTV/CAC uses a four-level fallback: `confirmed` (direct disclosure) → `proxy` (peer inference) → `industry_avg` (benchmark, annotated "不代表公司披露") → `unavailable`.

## Multi-Agent System

`webapp/research_agents/` contains 11 agent implementations coordinated by `orchestrator.py`:

| Agent | File | Role |
|-------|------|------|
| IdentityAgent | `agents/identity_agent.py` | company identity normalization |
| SourcePlanningAgent | `agents/source_planning_agent.py` | field-driven collection planning |
| OfficialAgent | `agents/official_agent.py` | 16-path website deep crawl |
| QueryAgent | `agents/query_agent.py` | Tavily search with budget limits |
| GitHubAgent | `agents/github_agent.py` | repo search + README/stars/forks/issues/discussions |
| MediaAgent | `agents/media_agent.py` | YouTube search + transcript extraction |
| CommunityAgent | `agents/community_agent.py` | Product Hunt / HN / Reddit signals |
| InsightAgent | `agents/insight_agent.py` | industry benchmarks and historical samples |
| MetricAgent | `agents/metric_agent.py` | operating metric extraction |
| CompetitorAgent | `agents/competitor_agent.py` | competitor data collection |
| ReportAgent | `agents/report_agent.py` | Standard/Business/Spread version generation |

Forum modules (`forum/`) provide `ForumModerator`, `ClaimCard`, `ConflictDetector`, and `RefetchPlanner`. Resolvers (`resolvers/`) include `field_resolver_v2.py` and `market_size_resolver.py` (market field context validation: region/segment/year). Storage (`storage/`) provides `candidate_store.py` for the `field_candidates` table.

Agents implement `BaseAgent` with `enabled` flag and `AgentResult` return type. Non-core agents use fallback mode — failures do not block the pipeline. The orchestrator (`orchestrator.py`) manages agent registration and sequential execution.

## Data Model

`research_db.sqlite` contains:
- `research`: generated research records, 3 rows per run (one per version). Competitive-positioning enum fields are stored in `research_fields` (key-value by `company_name`/`version`/`field_key`): 10 legacy fields extracted by L3 (`ai_model_dependency`, `workflow_integration_level`, `data_flywheel`, `proprietary_data_asset`, `incumbent_direct_competitor`, `customer_segment_type`, `funding_stage`, `pricing_model`, `inference_cost_exposure`, `stack_layer`) plus 12 v2 fields computed with legacy fallback (`incumbent_overlap`, `workflow_lock_in`, `data_lock_in`, `technical_uniqueness`, `distribution_lock`, `brand_or_community`, `market_size`, `strategic_dependency`, `user_visibility`, `pricing_power`, `gross_margin`, `customer_budget_level`). Cached scores: `funding_stage_score`, `score_defensibility`, `score_incumbent_attention`, `score_value_capture`.
- `research_jobs`: task lifecycle tracking (status, stage, error). Survives restarts; the status endpoint falls back to this table when the in-memory job dict is cold.
- `research_fields`: field-level research pool split from the wide research row. It is keyed by `(company_name, version, field_key)` and created by migration `001_research_fields.sql`. Migration `010_field_resolution.sql` adds `resolution_status`, `evidence_ids`, `unavailable_reason`, and `resolution_method` so the editor can distinguish confirmed facts from formulas, proxies, unavailable private metrics, manual-needed market estimates, and B2B-not-applicable user fields.
- `evidence_items`: persistent evidence pool created by migration `009_evidence_items.sql`. Stores source type, source URL/title, evidence text, a de-duplication hash, relevance/reliability scores, and research version.
- `field_resolution_logs`: append-only field-resolution and gap-audit log created by migration `010_field_resolution.sql`.
- v3 report fields added by migration `011_v3_fields.sql`, including market landscape, normalized market-size/TAM values, product usage/playbook fields, customer evidence, LTV/CAC benchmark metadata, acquisition channels, and competition-position fields. These are also split into `research_fields` with page/sort/value metadata for report-style rendering.
- **Normalized entity tables** (migrations 020-030): `companies`, `products`, `metrics`, `sectors`, `founders`, `funding_rounds`, `customers`, `competitors`, `company_analysis`, `research_runs`. These decompose the old `research` wide table into a layered fact/analysis/display architecture (PDF §3). CRUD is provided by `webapp/repositories/entity_repo.py` (638 lines, 22 functions). Data migration from the old wide table is handled by `webapp/db/migrate_entities.py`.
- **Evidence layer tables** (migrations 013-019): `source_documents` (full fetched documents), `evidence_spans` (field-level text excerpts with document foreign keys), `field_candidates` (multi-agent candidate values with confidence and selection state), `final_card_values` (curated display values keyed by `(company_key, card_no, field_key)`), `card_schema` (8-page card field mapping with render_order/required/render_type).

`final_db.sqlite` contains:

- `final_fields`: current field-level finalization table, keyed by `(company_name, field_key)`. Text finalization writes here with `status` values such as `draft` and `confirmed`. Company-library progress is computed as confirmed fields divided by total fields when rows exist.
- v3 finalization metadata from migration `012_v3_final_fields.sql`: `card_set_key`, `page_no`, `block_key`, `block_type`, `render_json`, and `export_targets`. Existing field-level reads remain compatible with older DBs.
- `final_content`: legacy card-level content table. It is still supported by export and compatibility paths. The unique key is:

```text
company_name + card_index + field_name
```

Saving the same card again updates existing fields instead of inserting duplicates. `get_final_cards()` also cleans older duplicate rows before reading, keeping the latest row per field.

`assets_db.sqlite` contains the `company_assets` table tracking demand-based media asset types per company:

```text
asset_key: logo | website_screenshot | founder_photo | product_main |
           competitors | competitors_logo_strip | flywheel |
           chart_competitive | chart_ecosystem |
           office | products_other | timeline
card_index: compatibility hint only; card placement is controlled by card_items
status:    missing → ready / generating / failed
selected_variant_id / final_score / auto_selected / fail_reason: final selection metadata
```

Each row records `local_path`, `source_type` (favicon/web_search/screenshot/composite/svg_render/api_generate/web_scrape/osm_map/street_view/web_tavily/playwright/import_url/import_upload), `source_url`, `prompt`, `selected_variant_id`, `final_score`, `auto_selected`, `fail_reason`, and `meta_json`. The unique key is `(company_name, asset_key)`. `company_key` is used for identity matching and legacy row repair, but upserts must still respect `(company_name, asset_key)` to avoid duplicate-slot writes. Assets are collected via the pipeline (logo, website/product screenshots, founder/competitor candidates, and v1/legacy office map), generated on-demand (competitors_logo_strip, flywheel, timeline, chart_competitive, chart_ecosystem), or manually imported/generated in image studio. `office/products_other/timeline` are compatibility slots and should not be reintroduced as v2/v3 primary render dependencies.

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
- `GET /api/research/running`
- `POST /api/research/stop/<job_id>`
- `DELETE /api/research/<company>` — 真删除公司全部数据（3 DB × 5 表 + images 目录），不可恢复
- `POST /api/research/save` legacy-compatible save endpoint

Editing and export:

- `POST /api/final/save`
- `GET /api/final/status/<company>`
- `GET /api/final/card/<company>/<card_index>`
- `GET /api/final/export/<company>` — returns Markdown by default. Add `?format=json` for structured data consumed by the canvas renderer.
- `GET /api/check/<company>`
- `POST /api/split-text`
- `POST /api/generate-image` — accepts optional `asset_key` to also write into `company_assets`.
- `GET /images/<filename>`
- `POST /api/final/abstract/<company>` — generate a short abstract from finalized content.

Decoupled card/field/render/media APIs:

- `GET /api/card-config/<company>?set=v1|v2|v3`
- `GET /api/card-config/<company>/cards/<card_id>`
- `POST /api/card-config/<company>/cards`
- `PATCH /api/card-config/<company>/cards/<card_id>`
- `DELETE /api/card-config/<company>/cards/<card_id>`
- `POST /api/card-config/<company>/cards/reorder`
- `GET /api/card-config/<company>/cards/<card_id>/items`
- `POST /api/card-config/<company>/cards/<card_id>/items`
- `PATCH /api/card-config/<company>/cards/<card_id>/items/<item_id>`
- `DELETE /api/card-config/<company>/cards/<card_id>/items/<item_id>`
- `POST /api/card-config/<company>/cards/<card_id>/items/batch`
- `GET /api/fields/<company>`
- `GET /api/fields/<company>/research`
- `GET /api/fields/<company>/final`
- `PATCH /api/fields/<company>/<field_key>`
- `POST /api/fields/<company>/confirm`
- `GET /api/render-data/<company>?set=v1|v2|v3`
- `GET /api/render-data/<company>/<card_id>?set=v1|v2|v3`
- `GET /api/media/<company>`
- `GET /api/media/<company>/<media_key>`
- `PATCH /api/media/<company>/<media_key>/select`
- `POST /api/media/<company>/<media_key>/recollect`
- `POST /api/media/<company>/<media_key>/generate`
- `POST /api/media/<company>/<media_key>/upload`

Asset system:

- `GET /api/assets/<company>` — get all assets for a company.
- `GET /api/assets/resolved?company=<company>&spec=v1|v2` — legacy stable card-assets resolver. v3 should use render-data or export bundle paths.
- `POST /api/assets/collect/<company>` — trigger automatic image collection (logo, office, product screenshot, other products, competitors). Add `?asset_key=office` to collect only one slot.
- `POST /api/assets/generate/<company>/<asset_key>` — generate flywheel or timeline infographic via LLM → SVG → Playwright → PNG pipeline.
- `GET /api/company/<company>/all-fields` — merged research/final field debug view with resolution metadata.

Image studio:

- `GET /image-studio/` — image studio page; accepts `?company=` and `?embed=1`.
- `GET /api/image-studio/<company>` — slot overview with variant counts.
- `GET /api/image-studio/<company>/<asset_key>` — variant list for a slot.
- `GET /api/image-studio/<company>/<asset_key>/variants` — same variant list, explicit scored-candidate endpoint.
- `POST /api/image-studio/<company>/<asset_key>/search` — multi-source image search (Pexels/Unsplash/Tavily).
- `POST /api/image-studio/<company>/<asset_key>/fetch` — download a candidate image, create variant, auto-select.
- `POST /api/image-studio/<company>/<asset_key>/generate-map` — regenerate the office map asset; only accepts `asset_key=office` and auto-selects the map variant.
- `POST /api/image-studio/<company>/<asset_key>/query` — DeepSeek Flash query generation for the slot.
- `POST /api/image-studio/<company>/<asset_key>/import` — URL import or file upload as variant.
- `POST /api/image-studio/<company>/<asset_key>/preview` — render preview HTML for chart/SVG slots.
- `POST /api/image-studio/<company>/<asset_key>/chart-data` — return extracted data for chart workspaces.
- `POST /api/image-studio/<company>/<asset_key>/extract-data` — extract flywheel/timeline data before SVG rendering.
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
- `GET /api/templates`
- `GET /api/templates/<template_id>`
- `POST /api/templates`
- `PATCH /api/templates/<template_id>`
- `DELETE /api/templates/<template_id>`
- `POST /api/templates/<template_id>/duplicate`
- `GET /canvas/` — card workbench. Use `?company=<company>` to load confirmed cards.
- `GET /canvas/card/<company>/<card_id>` — single-card HTML page for iframe preview and Puppeteer export. `card_id` may be a dynamic ID such as `card_06`, `v2_card_01`, or `v3_card_01`; pass `?set=` for dynamic card-set IDs. Numeric legacy IDs still work.
- `GET /canvas/<path>`

`POST /api/generate-image` accepts the existing `company_name`, `field_name`, and `prompt` fields. It also accepts optional runtime `image_api_url` and `image_api_key`; these override environment defaults for that request only. The API key is never returned in the response.

Layout persistence:

- `GET /api/layout/<company>/<card_id>` — return the saved layout instance for one card.
- `PATCH /api/layout/<company>/<card_id>` — merge `overrides` into the card layout instance. Region overrides may contain geometry/style keys and text `value`.
- `POST /api/layout/<company>/<card_id>/reset` — delete the saved layout instance and fall back to template defaults.
- `POST /api/export/<company>` — create an async render-data screenshot export job.
- `GET /api/export/<company>/jobs/<job_id>` — poll export job state.
- `GET /api/export/<company>/download/<job_id>` — download export result.

Evidence trace (field provenance):

- `GET /api/evidence/<company_key>/<field_key>` — full evidence chain for a field (spans with doc title/URL/trust_tier)
- `GET /api/evidence/<company_key>` — company evidence summary (total docs/spans, by source type, by trust tier, top evidenced fields)
- `GET /api/evidence/<company_key>/<field_key>/sources` — source documents contributing to a field

Card set management (`card_set_key` = v1|v2|v3 or user-defined):

- `GET /api/card-sets` — list all registered card sets.
- `POST /api/card-sets` — create a user-defined card set.
- `DELETE /api/card-sets/<set_key>` — delete a user-defined card set.
- `POST /api/final/<company>/init-set/<set_key>` — initialize composition structure for a company in a card set.
- `DELETE /api/final/<company>/set/<set_key>` — delete a company's data in a card set.

## Layout Center And Card Workbench

The layout center at `/layout?company=<company>&set=v1|v2|v3` is the main visual layout editor. It loads `/api/render-data/<company>`, lets the user choose a card and template, then exposes template regions as layers. Selecting a layer updates the right-side property panel and adds a cyan highlight inside the iframe preview. Geometry and style controls write region patches to layout overrides.

Text editing deliberately does not rely on browser `contentEditable` in the iframe. The iframe itself is rendered with pointer events disabled, and the parent page places transparent hitboxes over each region. This prevents double-clicking text from creating a browser-native blue selection across the whole card. When a text hitbox is double-clicked, the parent page opens a focused Markdown `<textarea>` inside the matching iframe region, temporarily lets pointer events reach the iframe for editing, and commits the raw Markdown to the region's `value` override on blur or Cmd/Ctrl+Enter. Escape cancels and re-renders the preview. `TemplateRenderer` then renders that `value` through its Markdown parser, so headings and `**bold**` survive layout re-renders and exports.

## Card Workbench

The card workbench uses browser-native HTML/CSS layout instead of fabric.js. The center pane shows a scaled 3:4 iframe preview based on a `900 x 1200` card. The left pane is project-scoped: it displays the current company as read-only state from `?company=`, then uses mutually exclusive accordions for card navigation, template selection, and the image folder. The template system is global (shared across all companies) and stores full HTML+CSS source sets for card-set templates in browser `localStorage`; templates can be imported/exported as JSON. On first visit, default templates are auto-loaded from `/canvas/default-templates.json`. The right pane shows the current card's complete HTML+CSS source with local syntax highlighting; edits debounce-render into the iframe.

The workbench toolbar includes `返回定稿台` and `参数编辑器`. With a company loaded, `返回定稿台` links to `/editor?company=<company>`; without a company it falls back to `/editor`. The `参数编辑器` button toggles a collapsible parameter-tuning bar below the iframe preview, containing single-accordion sliders/color-pickers for typography, colors, spacing, and layout. Changes are injected directly into the iframe via `renderSourceIntoDocument()`.

SVG infographics are auto-generated on card confirmation using default templates: v1 triggers timeline on card 3 + flywheel on card 6 + scatter charts on card 7; v2 triggers chart_ecosystem on card 3 + flywheel on card 6 + chart_competitive on card 7. They can also be rendered manually with custom parameters in the image studio editor.

`canvas/js/markdown-parser.js` supports current `markdown_full` exports and legacy field rows. It preserves remote and local Markdown images as `_image`, maps card 1 `# 公司名` plus bold-only subtitle into homepage fields, and maps unlabeled body text on cards 2 and 4 into the expected intro/product fields so the canvas does not drop finalized prose.

The CLI export path opens `/canvas/card/<company>/<card_id>?set=<set_key>` for each card and captures PNG files. The single-card page loads the same company assets as the full workbench, so selected image-studio variants appear in exported screenshots. Install Node dependencies with `npm install`, then run `node canvas/screenshot.js --company <company> --set v3 --base-url http://127.0.0.1:5050` for the v3 report set.

## Design Constraints

- Vanilla JS frontend; no React/Vue.
- `canvas/` main path uses HTML/CSS and iframe rendering; legacy fabric.js files may remain in the tree but are not referenced by `canvas/card-renderer.html`.
- SQLite through Python `sqlite3`; no ORM.
- Website scraping uses local `trafilatura` via `webapp/firecrawl_local.py`; no Firecrawl API.
- Cards are generated per the active card set (v1 = 8 cards, v2 = 7 cards). v1 card 7 is `竞争格局` with moat/ecosystem analysis + competitors, card 8 is `总结`. v2 card 7 covers competition without a separate summary card. `hook_paragraph_1/2/3` are research fields and are not written into cards.
