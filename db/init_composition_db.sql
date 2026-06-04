-- composition_db.sqlite — 卡片编排系统
-- 卡片不保存内容本身，只保存字段和图片的引用关系

-- 卡片表
CREATE TABLE IF NOT EXISTS card_compositions (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT    NOT NULL,
  card_id      TEXT    NOT NULL,   -- 稳定 ID，如 card_01
  card_index   INTEGER NOT NULL,   -- 显示排序
  card_title   TEXT    NOT NULL,   -- 卡片名称
  enabled      INTEGER DEFAULT 1,  -- 是否参与导出
  template_id  TEXT,               -- 默认模板
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(company_name, card_id)
);

CREATE INDEX IF NOT EXISTS idx_card_compositions_company
  ON card_compositions(company_name);

-- 卡片内容项表
CREATE TABLE IF NOT EXISTS card_items (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT    NOT NULL,
  card_id      TEXT    NOT NULL,   -- 关联 card_compositions.card_id
  item_type    TEXT    NOT NULL,   -- field | media
  item_key     TEXT    NOT NULL,   -- field_key 或 media_key
  item_label   TEXT,               -- 显示名称
  sort_order   INTEGER DEFAULT 0,
  display_role TEXT    DEFAULT 'body',  -- title|subtitle|body|caption|logo|hero_image|chart|background|decoration
  enabled      INTEGER DEFAULT 1,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_card_items_card
  ON card_items(company_name, card_id);

-- 默认卡片配置（新公司首次进入定稿台时自动创建）
-- card_id, card_index, card_title, fields[], media[], template_id
CREATE TABLE IF NOT EXISTS default_card_configs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  card_id      TEXT    NOT NULL UNIQUE,
  card_index   INTEGER NOT NULL,
  card_title   TEXT    NOT NULL,
  config_json  TEXT    NOT NULL,   -- JSON: {fields: [...], media: [...], template_id: "..."}
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 插入默认 8 张卡片配置
INSERT OR IGNORE INTO default_card_configs (card_id, card_index, card_title, config_json) VALUES
('card_01', 1, '首页', '{"fields":["company_name","company_type"],"media":["logo"],"template_id":"cover_default"}'),
('card_02', 2, '公司介绍', '{"fields":["location","company_def","founder_name","founder_edu","founder_bg","founder_achievement","team_size","team_highlight","funding_info","website_url"],"media":["office","website_screenshot"],"template_id":"image_top_text_bottom"}'),
('card_03', 3, '发展沿袭', '{"fields":["timeline_events"],"media":["timeline"],"template_id":"chart_top_text_bottom"}'),
('card_04', 4, '主产品', '{"fields":["main_product_name","main_product_def","main_product_highlight","main_product_achievement"],"media":["product_main"],"template_id":"image_top_text_bottom"}'),
('card_05', 5, '其他产品', '{"fields":["other_products"],"media":["products_other"],"template_id":"image_top_text_bottom"}'),
('card_06', 6, '商业模式', '{"fields":["revenue_model","gtm_strategy","cold_start","customer_segment","growth_flywheel"],"media":["flywheel"],"template_id":"chart_top_text_bottom"}'),
('card_07', 7, '竞争格局', '{"fields":["moat","ecosystem_niche","competitors"],"media":["competitors_logo_strip","chart_competitive","chart_ecosystem"],"template_id":"multi_chart"}'),
('card_08', 8, '总结', '{"fields":["market_opportunity","data_confidence"],"media":[],"template_id":"text_focus"}');
