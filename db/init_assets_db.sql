-- company_assets: 公司图片资产追踪表
-- 每家公司固定资产槽位，按 card_index 对应卡片
CREATE TABLE IF NOT EXISTS company_assets (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT    NOT NULL,
  asset_key    TEXT    NOT NULL,  -- logo|website_screenshot|office|product_main|products_other|competitors|competitors_logo_strip|flywheel|timeline|chart_competitive|chart_ecosystem
  card_index   INTEGER NOT NULL,
  local_path   TEXT,
  source_type  TEXT,              -- favicon|web_search|screenshot|composite|svg_render|api_generate
  source_url   TEXT,
  prompt       TEXT,
  status       TEXT    DEFAULT 'missing',  -- missing|ready|generating|failed
  selected_variant_id INTEGER,
  final_score  REAL    DEFAULT 0,
  auto_selected INTEGER DEFAULT 0,
  fail_reason  TEXT,
  meta_json    TEXT,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(company_name, asset_key)
);

CREATE INDEX IF NOT EXISTS idx_assets_company ON company_assets(company_name);

-- image_variants: 图片变体库（每张卡片可有多个候选版本）
CREATE TABLE IF NOT EXISTS image_variants (
  id              INTEGER  PRIMARY KEY AUTOINCREMENT,
  company_name    TEXT     NOT NULL,
  asset_key       TEXT     NOT NULL,
  local_path      TEXT     NOT NULL,
  source_type     TEXT     NOT NULL,  -- web_pexels|web_unsplash|web_tavily|
                                       -- import_upload|import_url|api_generate
  source_url      TEXT,               -- 原始图片 URL
  source_page     TEXT,               -- 图片所在网页（用于标注）
  author          TEXT,               -- 图片作者
  license         TEXT,               -- 版权说明
  attribution_req INTEGER DEFAULT 0,  -- 1=用户选择标注来源
  prompt          TEXT,               -- AI 生图时使用的 prompt
  width           INTEGER,
  height          INTEGER,
  file_size       INTEGER,
  aspect_ratio    REAL,
  quality_score   REAL DEFAULT 0,
  relevance_score REAL DEFAULT 0,
  source_score    REAL DEFAULT 0,
  final_score     REAL DEFAULT 0,
  reject_reason   TEXT,
  meta_json       TEXT,
  is_selected     INTEGER DEFAULT 0,  -- 1=当前选定版本
  created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_variants_company_asset
  ON image_variants(company_name, asset_key);
