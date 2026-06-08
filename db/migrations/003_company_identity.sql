-- 003_company_identity.sql — 公司身份归一化
-- 为所有主表增加 company_key，防止 Limitless/limitless 被当成不同公司

ALTER TABLE research ADD COLUMN company_key TEXT;
ALTER TABLE research ADD COLUMN display_name TEXT;
ALTER TABLE research ADD COLUMN input_name TEXT;
ALTER TABLE research ADD COLUMN website_host TEXT;
ALTER TABLE research ADD COLUMN source_chain_version TEXT DEFAULT 'collection_v2';

CREATE INDEX IF NOT EXISTS idx_research_company_key
  ON research(company_key, version, created_at);

-- research_jobs
ALTER TABLE research_jobs ADD COLUMN company_key TEXT;
ALTER TABLE research_jobs ADD COLUMN display_name TEXT;
ALTER TABLE research_jobs ADD COLUMN website_host TEXT;

CREATE INDEX IF NOT EXISTS idx_research_jobs_company_key
  ON research_jobs(company_key, created_at);

-- company_assets + image_variants (assets_db)
ALTER TABLE company_assets ADD COLUMN company_key TEXT;
ALTER TABLE image_variants ADD COLUMN company_key TEXT;

CREATE INDEX IF NOT EXISTS idx_assets_company_key
  ON company_assets(company_key);

CREATE INDEX IF NOT EXISTS idx_variants_company_key_asset
  ON image_variants(company_key, asset_key);

-- final_fields (final_db)
ALTER TABLE final_fields ADD COLUMN company_key TEXT;

CREATE INDEX IF NOT EXISTS idx_final_fields_company_key
  ON final_fields(company_key);

-- research_fields (research_db)
ALTER TABLE research_fields ADD COLUMN company_key TEXT;

CREATE INDEX IF NOT EXISTS idx_research_fields_company_key
  ON research_fields(company_key, version);

-- composition_db 迁移已通过 db/migrate.py 直接对 composition_db.sqlite 执行:
--   python3 db/migrate.py db/composition_db.sqlite --names 003_company_identity.sql
-- 如 composition_db 也使用同一迁移目录，以下 ALTER TABLE 会被幂等执行:
ALTER TABLE card_compositions ADD COLUMN company_key TEXT;
ALTER TABLE card_items ADD COLUMN company_key TEXT;

CREATE INDEX IF NOT EXISTS idx_card_compositions_company_key
  ON card_compositions(company_key);

CREATE INDEX IF NOT EXISTS idx_card_items_company_key_card
  ON card_items(company_key, card_id);
