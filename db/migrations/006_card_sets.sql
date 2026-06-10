-- 006_card_sets.sql — 套卡系统（composition_db）
-- 执行：sqlite3 db/composition_db.sqlite < db/migrations/006_card_sets.sql

-- 1. 新建 card_set_registry
CREATE TABLE IF NOT EXISTS card_set_registry (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    set_key        TEXT    NOT NULL UNIQUE,
    display_name   TEXT    NOT NULL,
    spec_version   TEXT    NOT NULL,
    card_count     INTEGER NOT NULL,
    is_system      INTEGER NOT NULL DEFAULT 0,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO card_set_registry
    (set_key, display_name, spec_version, card_count, is_system)
VALUES
    ('v1', '套卡1 · 经典8张', 'v1', 8, 1),
    ('v2', '套卡2 · 新版7张', 'v2', 7, 1);

-- 2. 重建 default_card_configs（加 set_key，更新 UNIQUE 约束）
CREATE TABLE default_card_configs_new (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    set_key      TEXT    NOT NULL DEFAULT 'v1',
    card_id      TEXT    NOT NULL,
    card_index   INTEGER NOT NULL,
    card_title   TEXT    NOT NULL,
    config_json  TEXT    NOT NULL,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(set_key, card_id)
);

INSERT INTO default_card_configs_new
    (set_key, card_id, card_index, card_title, config_json, created_at)
SELECT 'v1', card_id, card_index, card_title, config_json, created_at
FROM default_card_configs;

DROP TABLE default_card_configs;
ALTER TABLE default_card_configs_new RENAME TO default_card_configs;

-- 插入 v2 套卡的 7 张默认配置
INSERT OR IGNORE INTO default_card_configs
    (set_key, card_id, card_index, card_title, config_json)
VALUES
('v2','v2_card_01',1,'封面',
 '{"fields":["company_name"],"media":["logo"],"template_id":"cover_v2"}'),
('v2','v2_card_02',2,'公司概览',
 '{"fields":["location","company_type","company_def","company_achievement","website_url"],"media":["website_screenshot"],"template_id":"overview_v2"}'),
('v2','v2_card_03',3,'产品与定位',
 '{"fields":["main_product_name","main_product_def","main_product_highlight","main_product_achievement","tech_stack","ecosystem_niche"],"media":["chart_ecosystem","product_main"],"template_id":"product_v2"}'),
('v2','v2_card_04',4,'创始人与团队',
 '{"fields":["founder_name","founder_edu","founder_bg","founder_achievement","team_size","team_highlight"],"media":["founder_photo"],"template_id":"founder_v2"}'),
('v2','v2_card_05',5,'财务与市场',
 '{"fields":["customer_segment","revenue_metrics","growth_metrics","regional_markets","funding_info"],"media":[],"template_id":"finance_v2"}'),
('v2','v2_card_06',6,'GTM与增长',
 '{"fields":["gtm_strategy","growth_flywheel"],"media":["flywheel"],"template_id":"gtm_v2"}'),
('v2','v2_card_07',7,'竞争格局',
 '{"fields":["moat","competitors","competitors_summary"],"media":["competitors_logo_strip","chart_competitive"],"template_id":"competitive_v2"}');

-- 3. 重建 card_compositions（加 card_set_key，更新 UNIQUE 约束）
CREATE TABLE card_compositions_new (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT    NOT NULL,
    card_set_key TEXT    NOT NULL DEFAULT 'v1',
    card_id      TEXT    NOT NULL,
    card_index   INTEGER NOT NULL,
    card_title   TEXT    NOT NULL,
    enabled      INTEGER DEFAULT 1,
    template_id  TEXT,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(company_name, card_set_key, card_id)
);

INSERT INTO card_compositions_new
    (id, company_name, card_set_key, card_id, card_index,
     card_title, enabled, template_id, created_at, updated_at)
SELECT id, company_name, 'v1', card_id, card_index,
       card_title, enabled, template_id, created_at, updated_at
FROM card_compositions;

DROP TABLE card_compositions;
ALTER TABLE card_compositions_new RENAME TO card_compositions;
CREATE INDEX idx_card_compositions_company
    ON card_compositions(company_name, card_set_key);

-- 4. card_items 加 card_set_key
ALTER TABLE card_items ADD COLUMN card_set_key TEXT NOT NULL DEFAULT 'v1';
CREATE INDEX IF NOT EXISTS idx_card_items_set
    ON card_items(company_name, card_set_key, card_id);
