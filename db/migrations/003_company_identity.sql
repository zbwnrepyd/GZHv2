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
