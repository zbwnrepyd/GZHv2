-- 005_v2_fields_fix.sql — 修正 v2 字段名 + 新增 competitors_summary
-- 适用数据库：research_db.sqlite
-- company_revenue/company_profit 在 004 中已加，此处新增正确的字段名替代

ALTER TABLE research ADD COLUMN revenue_metrics TEXT;
ALTER TABLE research ADD COLUMN growth_metrics TEXT;
ALTER TABLE research ADD COLUMN competitors_summary TEXT;
