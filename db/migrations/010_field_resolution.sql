-- 010_field_resolution.sql — 字段分辨率状态 + 审计日志
-- 在 research_fields 上增加生命周期状态列，新建 resolution_logs 表

-- 1. 扩展 research_fields：字段分辨率元数据（SQLite ALTER TABLE 只支持 ADD COLUMN）
ALTER TABLE research_fields ADD COLUMN resolution_status TEXT;
  -- confirmed | derived | proxy | unavailable | manual_needed | not_applicable | llm_extracted
ALTER TABLE research_fields ADD COLUMN evidence_ids TEXT;
  -- 逗号分隔的 evidence_items.id，可追溯来源
ALTER TABLE research_fields ADD COLUMN unavailable_reason TEXT;
  -- 不可得时的解释
ALTER TABLE research_fields ADD COLUMN resolution_method TEXT;
  -- formula | rule_match | proxy_estimate | llm_extract | marked_unavailable

-- 2. 字段分辨率日志表（审计追踪）
CREATE TABLE IF NOT EXISTS field_resolution_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT NOT NULL,
  version TEXT DEFAULT 'standard',
  field_key TEXT NOT NULL,
  resolution_status TEXT,
  resolution_method TEXT,
  evidence_count INTEGER DEFAULT 0,
  resolved_at TEXT DEFAULT (datetime('now')),
  detail_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_reslog_company ON field_resolution_logs(company_name, version);
CREATE INDEX IF NOT EXISTS idx_reslog_field ON field_resolution_logs(company_name, field_key);
