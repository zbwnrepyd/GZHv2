-- 016_final_card_values: 字段定稿表
-- P1: 替代 final_fields 的扁平结构，按卡片页组织
-- 唯一键: (company_key, card_no, field_key)

CREATE TABLE IF NOT EXISTS final_card_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    company_key TEXT NOT NULL,
    card_no INTEGER NOT NULL,               -- 卡片页码 1-8
    field_key TEXT NOT NULL,
    final_value TEXT,                       -- 定稿文案
    source_evidence_ids TEXT,               -- JSON 数组: [span_id, ...]
    status TEXT DEFAULT 'draft',            -- draft|confirmed|proxy|industry_avg|unavailable
    confidence TEXT DEFAULT 'medium',       -- high|medium|low
    editor_note TEXT,                       -- 编辑备注
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (company_key, card_no, field_key)
);

CREATE INDEX IF NOT EXISTS idx_final_card_values_company ON final_card_values(company_key);
CREATE INDEX IF NOT EXISTS idx_final_card_values_card ON final_card_values(company_key, card_no);
