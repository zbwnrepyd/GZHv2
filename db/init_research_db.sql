-- research_db: AI 原始研究输出，每公司 3 版本 (standard/business/spread)
CREATE TABLE IF NOT EXISTS research (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name  TEXT    NOT NULL,
  version       TEXT    CHECK(version IN ('standard','business','spread')),
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  -- 卡片1：首页 ─────────────────────────────────────────────────
  company_type  TEXT,
  -- 卡片2：公司介绍 ───────────────────────────────────────────
  location      TEXT,
  company_def   TEXT,
  founder_name  TEXT,
  founder_edu   TEXT,
  founder_bg    TEXT,
  founder_achievement TEXT,
  team_size     TEXT,
  team_highlight TEXT,
  funding_info  TEXT,
  website_url   TEXT,
  -- 卡片3：发展沿袭 ───────────────────────────────────────────
  timeline_events TEXT, -- JSON数组: [{"date":"...", "event":"...", "impact":"..."}]
  -- 卡片4：主产品 ─────────────────────────────────────────────
  main_product_name        TEXT,
  main_product_def         TEXT,
  main_product_highlight   TEXT,
  main_product_achievement TEXT,
  main_product_img_src     TEXT,
  -- 卡片5：其他产品 ───────────────────────────────────────────
  other_products  TEXT, -- JSON数组: [{"name":"...", "def":"...", "highlight":"..."}]
  -- 卡片6：商业模式 ───────────────────────────────────────────
  revenue_model   TEXT,
  gtm_strategy    TEXT,
  cold_start      TEXT,
  customer_segment TEXT,
  growth_flywheel TEXT,
  -- 卡片7：总结 ───────────────────────────────────────────────
  moat            TEXT,
  competitors     TEXT, -- JSON数组: [{"name":"...", "product":"...", "data":"..."}]
  market_opportunity TEXT,
  -- 传播钩子段落 ───────────────────────────────────────────────
  hook_paragraph_1 TEXT,
  hook_paragraph_2 TEXT,
  hook_paragraph_3 TEXT,
  -- 质量控制 ───────────────────────────────────────────────────
  data_confidence TEXT  -- 高 / 中 / 低
);

CREATE INDEX IF NOT EXISTS idx_research_company ON research(company_name);
CREATE INDEX IF NOT EXISTS idx_research_version ON research(company_name, version);

-- research_jobs: 研究任务状态追踪（持久化，服务重启不丢失）
CREATE TABLE IF NOT EXISTS research_jobs (
  job_id       TEXT PRIMARY KEY,
  company_name TEXT NOT NULL,
  company_url  TEXT NOT NULL,
  status       TEXT DEFAULT 'pending',
  stage        TEXT,
  detail       TEXT,
  error        TEXT,
  record_ids   TEXT,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
