-- 011_v3_fields.sql — v3 研究数据库扩列：research 宽表 + research_fields + evidence_items
-- 应用于: research_db.sqlite
-- 原则：只增不减，不破坏 v1/v2 既有数据和测试

BEGIN TRANSACTION;

-- ════════════════════════════════════════════════════════
-- 1. research 宽表：只增不减（36 个新列）
-- ════════════════════════════════════════════════════════
ALTER TABLE research ADD COLUMN market_landscape_summary TEXT;
ALTER TABLE research ADD COLUMN market_landscape_top_players TEXT;
ALTER TABLE research ADD COLUMN market_size_value REAL;
ALTER TABLE research ADD COLUMN market_size_currency TEXT;
ALTER TABLE research ADD COLUMN market_size_year INTEGER;
ALTER TABLE research ADD COLUMN tam_value REAL;
ALTER TABLE research ADD COLUMN tam_currency TEXT;
ALTER TABLE research ADD COLUMN tam_year INTEGER;
ALTER TABLE research ADD COLUMN founded_date TEXT;
ALTER TABLE research ADD COLUMN core_business TEXT;
ALTER TABLE research ADD COLUMN core_competency TEXT;
ALTER TABLE research ADD COLUMN funding_rounds TEXT;
ALTER TABLE research ADD COLUMN company_achievements TEXT;
ALTER TABLE research ADD COLUMN industry_positioning TEXT;
ALTER TABLE research ADD COLUMN product_pain_points TEXT;
ALTER TABLE research ADD COLUMN product_core_features TEXT;
ALTER TABLE research ADD COLUMN product_usage_playbook TEXT;
ALTER TABLE research ADD COLUMN product_tech_stack TEXT;
ALTER TABLE research ADD COLUMN regional_market_focus TEXT;
ALTER TABLE research ADD COLUMN mau INTEGER;
ALTER TABLE research ADD COLUMN mau_as_of TEXT;
ALTER TABLE research ADD COLUMN retention_definition TEXT;
ALTER TABLE research ADD COLUMN pricing_summary TEXT;
ALTER TABLE research ADD COLUMN pricing_tiers TEXT;
ALTER TABLE research ADD COLUMN ecosystem_niche TEXT;
ALTER TABLE research ADD COLUMN customer_names TEXT;
ALTER TABLE research ADD COLUMN customer_selection_reasons TEXT;
ALTER TABLE research ADD COLUMN customer_choice_evidence TEXT;
ALTER TABLE research ADD COLUMN pricing_strategy TEXT;
ALTER TABLE research ADD COLUMN ltv_cac_is_benchmark INTEGER DEFAULT 0;
ALTER TABLE research ADD COLUMN ltv_cac_benchmark_source TEXT;
ALTER TABLE research ADD COLUMN acquisition_channels TEXT;
ALTER TABLE research ADD COLUMN competitors_top3 TEXT;
ALTER TABLE research ADD COLUMN competitive_position TEXT;
ALTER TABLE research ADD COLUMN differentiated_opportunity TEXT;
ALTER TABLE research ADD COLUMN competitive_advantages TEXT;

-- ════════════════════════════════════════════════════════
-- 2. research_fields 扩列：字段型权威层
--    （evidence_ids 已在 010 添加，此处跳过）
-- ════════════════════════════════════════════════════════
ALTER TABLE research_fields ADD COLUMN value_type TEXT;
ALTER TABLE research_fields ADD COLUMN norm_value TEXT;
ALTER TABLE research_fields ADD COLUMN currency_code TEXT;
ALTER TABLE research_fields ADD COLUMN unit TEXT;
ALTER TABLE research_fields ADD COLUMN as_of_date TEXT;
ALTER TABLE research_fields ADD COLUMN source_urls TEXT;
ALTER TABLE research_fields ADD COLUMN page_no INTEGER;
ALTER TABLE research_fields ADD COLUMN sort_order INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_research_fields_company_page
  ON research_fields(company_name, version, page_no, sort_order);

-- 文档中标记为“普通索引”的字段
CREATE INDEX IF NOT EXISTS idx_research_company_type
  ON research(company_type);
CREATE INDEX IF NOT EXISTS idx_research_market_landscape_summary
  ON research(market_landscape_summary);
CREATE INDEX IF NOT EXISTS idx_research_market_size_value
  ON research(market_size_value);
CREATE INDEX IF NOT EXISTS idx_research_market_size_year
  ON research(market_size_year);
CREATE INDEX IF NOT EXISTS idx_research_market_cagr
  ON research(market_cagr);
CREATE INDEX IF NOT EXISTS idx_research_tam_value
  ON research(tam_value);
CREATE INDEX IF NOT EXISTS idx_research_tam_year
  ON research(tam_year);
CREATE INDEX IF NOT EXISTS idx_research_location
  ON research(location);
CREATE INDEX IF NOT EXISTS idx_research_founded_date
  ON research(founded_date);
CREATE INDEX IF NOT EXISTS idx_research_industry_positioning
  ON research(industry_positioning);
CREATE INDEX IF NOT EXISTS idx_research_main_product_name
  ON research(main_product_name);
CREATE INDEX IF NOT EXISTS idx_research_product_tech_stack
  ON research(product_tech_stack);
CREATE INDEX IF NOT EXISTS idx_research_regional_market_focus
  ON research(regional_market_focus);
CREATE INDEX IF NOT EXISTS idx_research_mau
  ON research(mau);
CREATE INDEX IF NOT EXISTS idx_research_mau_as_of
  ON research(mau_as_of);
CREATE INDEX IF NOT EXISTS idx_research_retention_rate
  ON research(retention_rate);
CREATE INDEX IF NOT EXISTS idx_research_ideal_customer_profile
  ON research(ideal_customer_profile);
CREATE INDEX IF NOT EXISTS idx_research_customer_segment_primary
  ON research(customer_segment_primary);
CREATE INDEX IF NOT EXISTS idx_research_customer_segment_secondary
  ON research(customer_segment_secondary);
CREATE INDEX IF NOT EXISTS idx_research_ltv
  ON research(ltv);
CREATE INDEX IF NOT EXISTS idx_research_cac
  ON research(cac);
CREATE INDEX IF NOT EXISTS idx_research_ltv_cac_ratio
  ON research(ltv_cac_ratio);
CREATE INDEX IF NOT EXISTS idx_research_ltv_cac_is_benchmark
  ON research(ltv_cac_is_benchmark);

-- ════════════════════════════════════════════════════════
-- 3. evidence_items 扩列：证据池
-- ════════════════════════════════════════════════════════
ALTER TABLE evidence_items ADD COLUMN domain TEXT;
ALTER TABLE evidence_items ADD COLUMN published_at TEXT;
ALTER TABLE evidence_items ADD COLUMN lang TEXT;
ALTER TABLE evidence_items ADD COLUMN content_hash TEXT;
ALTER TABLE evidence_items ADD COLUMN robots_status TEXT;
ALTER TABLE evidence_items ADD COLUMN source_family TEXT;

COMMIT;
