-- 004_v2_fields.sql — 卡片规格 v1 → v2 新增字段
-- 适用数据库：research_db.sqlite
-- 执行方式：python3 db/migrate.py db/research_db.sqlite --names 004_v2_fields.sql

-- 新增 page2：公司成就
ALTER TABLE research ADD COLUMN company_achievement TEXT;

-- 新增 page3：技术栈自由文字描述
ALTER TABLE research ADD COLUMN tech_stack TEXT;

-- 新增 page5：财务与市场
ALTER TABLE research ADD COLUMN company_revenue TEXT;
ALTER TABLE research ADD COLUMN regional_markets TEXT;
ALTER TABLE research ADD COLUMN company_profit TEXT;

-- 注：timeline_events / other_products / hook_paragraph_1~3 /
--     market_opportunity / cold_start 对应列保留，不做 DROP，
--     防止历史数据读取报错。
