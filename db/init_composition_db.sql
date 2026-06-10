-- composition_db.sqlite — 卡片编排系统
-- v2: 加 card_set_key + card_set_registry

-- 卡片表
CREATE TABLE IF NOT EXISTS card_compositions (
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

CREATE INDEX IF NOT EXISTS idx_card_compositions_company
  ON card_compositions(company_name, card_set_key);

-- 卡片内容项表
CREATE TABLE IF NOT EXISTS card_items (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT    NOT NULL,
  card_set_key TEXT    NOT NULL DEFAULT 'v1',
  card_id      TEXT    NOT NULL,
  item_type    TEXT    NOT NULL,
  item_key     TEXT    NOT NULL,
  item_label   TEXT,
  sort_order   INTEGER DEFAULT 0,
  display_role TEXT    DEFAULT 'body',
  enabled      INTEGER DEFAULT 1,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_card_items_card
  ON card_items(company_name, card_set_key, card_id);

-- 套卡注册表
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

-- 默认卡片配置（v2: 加 set_key，UNIQUE 约束改为 (set_key, card_id)）
CREATE TABLE IF NOT EXISTS default_card_configs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  set_key      TEXT    NOT NULL DEFAULT 'v1',
  card_id      TEXT    NOT NULL,
  card_index   INTEGER NOT NULL,
  card_title   TEXT    NOT NULL,
  config_json  TEXT    NOT NULL,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(set_key, card_id)
);

-- v1 套卡的 8 张默认配置（set_key='v1'）
INSERT OR IGNORE INTO default_card_configs (set_key, card_id, card_index, card_title, config_json) VALUES
('v1','card_01',1,'首页','{"fields":["company_name","company_type"],"media":["logo"],"template_id":"cover_default"}'),
('v1','card_02',2,'公司介绍','{"fields":["location","company_def","founder_name","founder_edu","founder_bg","founder_achievement","team_size","team_highlight","funding_info","website_url"],"media":["office","website_screenshot"],"template_id":"image_top_text_bottom"}'),
('v1','card_03',3,'发展沿袭','{"fields":["timeline_events"],"media":["timeline"],"template_id":"chart_top_text_bottom"}'),
('v1','card_04',4,'主产品','{"fields":["main_product_name","main_product_def","main_product_highlight","main_product_achievement"],"media":["product_main"],"template_id":"image_top_text_bottom"}'),
('v1','card_05',5,'其他产品','{"fields":["other_products"],"media":["products_other"],"template_id":"image_top_text_bottom"}'),
('v1','card_06',6,'商业模式','{"fields":["revenue_model","gtm_strategy","cold_start","customer_segment","growth_flywheel"],"media":["flywheel"],"template_id":"chart_top_text_bottom"}'),
('v1','card_07',7,'竞争格局','{"fields":["moat","ecosystem_niche","competitors"],"media":["competitors_logo_strip","chart_competitive","chart_ecosystem"],"template_id":"multi_chart"}'),
('v1','card_08',8,'总结','{"fields":["market_opportunity","data_confidence"],"media":[],"template_id":"text_focus"}');

-- v2 套卡的 7 张默认配置（set_key='v2'）
INSERT OR IGNORE INTO default_card_configs (set_key, card_id, card_index, card_title, config_json) VALUES
('v2','v2_card_01',1,'封面','{"fields":["company_name"],"media":["logo"],"template_id":"cover_v2"}'),
('v2','v2_card_02',2,'公司概览','{"fields":["location","company_type","company_def","company_achievement","website_url"],"media":["website_screenshot"],"template_id":"overview_v2"}'),
('v2','v2_card_03',3,'产品与定位','{"fields":["main_product_name","main_product_def","main_product_highlight","main_product_achievement","tech_stack","ecosystem_niche"],"media":["chart_ecosystem","product_main"],"template_id":"product_v2"}'),
('v2','v2_card_04',4,'创始人与团队','{"fields":["founder_name","founder_edu","founder_bg","founder_achievement","team_size","team_highlight"],"media":["founder_photo"],"template_id":"founder_v2"}'),
('v2','v2_card_05',5,'财务与市场','{"fields":["customer_segment","revenue_metrics","growth_metrics","regional_markets","funding_info"],"media":[],"template_id":"finance_v2"}'),
('v2','v2_card_06',6,'GTM与增长','{"fields":["gtm_strategy","growth_flywheel"],"media":["flywheel"],"template_id":"gtm_v2"}'),
('v2','v2_card_07',7,'竞争格局','{"fields":["moat","competitors","competitors_summary"],"media":["competitors_logo_strip","chart_competitive"],"template_id":"competitive_v2"}');
