-- 018_company_key_fields: research_fields / final_fields 增加 company_key
-- P0: company_key 贯穿字段层；旧数据用 company_name 回填
-- 此迁移用于 research_db.sqlite（含 research_fields 和 final_fields 的早期副本）
-- final_db.sqlite 的 final_fields 迁移见 019_company_key_final_fields.sql

-- research_fields 增加 company_key
ALTER TABLE research_fields ADD COLUMN company_key TEXT DEFAULT '';

-- final_fields 增加 company_key（若表存在）
-- 注意：final_db.sqlite 中 final_fields 由 019 处理
ALTER TABLE final_fields ADD COLUMN company_key TEXT DEFAULT '';

-- 回填已有数据
UPDATE research_fields SET company_key = LOWER(company_name) WHERE company_key = '' OR company_key IS NULL;
UPDATE final_fields SET company_key = LOWER(company_name) WHERE company_key = '' OR company_key IS NULL;

-- 索引
CREATE INDEX IF NOT EXISTS idx_research_fields_ckey ON research_fields(company_key, version);
CREATE INDEX IF NOT EXISTS idx_final_fields_ckey ON final_fields(company_key);
