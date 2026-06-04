-- 002_final_fields.sql — 定稿字段表
-- final_fields 按字段维度保存人工定稿内容，不按卡片组织

CREATE TABLE IF NOT EXISTS final_fields (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name    TEXT    NOT NULL,
  field_key       TEXT    NOT NULL,
  field_label     TEXT,
  final_value     TEXT,
  source_version  TEXT    DEFAULT 'standard',   -- 来源版本
  status          TEXT    DEFAULT 'draft',       -- draft | confirmed | hidden
  updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(company_name, field_key)
);

CREATE INDEX IF NOT EXISTS idx_final_fields_company
  ON final_fields(company_name);
