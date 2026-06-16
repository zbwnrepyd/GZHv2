-- 008_operating_metrics_fields.sql — 运营指标 + 卡片拆分字段
-- 适用数据库：research_db.sqlite
-- 执行方式：python3 db/migrate.py db/research_db.sqlite --only 008_operating_metrics_fields.sql

ALTER TABLE research ADD COLUMN tam TEXT;
ALTER TABLE research ADD COLUMN sam TEXT;
ALTER TABLE research ADD COLUMN som TEXT;
ALTER TABLE research ADD COLUMN market_cagr TEXT;
ALTER TABLE research ADD COLUMN arr TEXT;
ALTER TABLE research ADD COLUMN mrr TEXT;
ALTER TABLE research ADD COLUMN registered_users TEXT;
ALTER TABLE research ADD COLUMN active_users TEXT;
ALTER TABLE research ADD COLUMN paying_users TEXT;
ALTER TABLE research ADD COLUMN retention_rate TEXT;
ALTER TABLE research ADD COLUMN churn_rate TEXT;
ALTER TABLE research ADD COLUMN cac TEXT;
ALTER TABLE research ADD COLUMN ltv TEXT;
ALTER TABLE research ADD COLUMN ltv_cac_ratio TEXT;
ALTER TABLE research ADD COLUMN gross_margin TEXT;
ALTER TABLE research ADD COLUMN burn_rate TEXT;
ALTER TABLE research ADD COLUMN runway_months TEXT;
ALTER TABLE research ADD COLUMN market_size_source_note TEXT;

ALTER TABLE research ADD COLUMN ecosystem_positioning TEXT;
ALTER TABLE research ADD COLUMN differentiation_strategy TEXT;
ALTER TABLE research ADD COLUMN cost_advantage TEXT;
ALTER TABLE research ADD COLUMN technical_barrier TEXT;
ALTER TABLE research ADD COLUMN switching_cost TEXT;
ALTER TABLE research ADD COLUMN ideal_customer_profile TEXT;
ALTER TABLE research ADD COLUMN customer_segment_primary TEXT;
ALTER TABLE research ADD COLUMN customer_segment_secondary TEXT;
ALTER TABLE research ADD COLUMN growth_strategy TEXT;
ALTER TABLE research ADD COLUMN gtm_motion TEXT;
