-- 019_company_key_final_fields: final_fields 增加 company_key（仅 final_db.sqlite）
-- 018_company_key_fields.sql 包含 research_fields 的 ALTER，只适用于 research_db.sqlite

ALTER TABLE final_fields ADD COLUMN company_key TEXT DEFAULT '';

-- 回填已有数据
UPDATE final_fields SET company_key = LOWER(company_name) WHERE company_key = '' OR company_key IS NULL;

CREATE INDEX IF NOT EXISTS idx_final_fields_ckey ON final_fields(company_key);
