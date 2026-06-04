-- 001_research_fields.sql — 将研究宽表拆分为字段池
-- research_fields 是采集后的字段池，不关心卡片

CREATE TABLE IF NOT EXISTS research_fields (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT    NOT NULL,
  version      TEXT    DEFAULT 'standard',  -- standard | business | spread
  field_key    TEXT    NOT NULL,
  field_label  TEXT,
  field_value  TEXT,
  source_type  TEXT,               -- llm_extract | web_scrape | tavily_search | manual
  source_url   TEXT,
  confidence   TEXT,               -- high | medium | low
  raw_payload  TEXT,               -- 原始 JSON（保留未拆分的嵌套数据）
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(company_name, version, field_key)
);

CREATE INDEX IF NOT EXISTS idx_research_fields_company
  ON research_fields(company_name, version);
