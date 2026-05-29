-- company_assets: 公司图片资产追踪表
-- 每家公司固定 7 个 asset_key，按 card_index 对应卡片
CREATE TABLE IF NOT EXISTS company_assets (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT    NOT NULL,
  asset_key    TEXT    NOT NULL,  -- logo|office|product_main|products_other|competitors|flywheel|timeline
  card_index   INTEGER NOT NULL,
  local_path   TEXT,
  source_type  TEXT,              -- favicon|web_search|screenshot|composite|svg_render|api_generate
  source_url   TEXT,
  prompt       TEXT,
  status       TEXT    DEFAULT 'missing',  -- missing|ready|generating|failed
  meta_json    TEXT,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(company_name, asset_key)
);

CREATE INDEX IF NOT EXISTS idx_assets_company ON company_assets(company_name);
