-- 017_card_schema: 卡片配置表
-- P2: 8 页卡片不再写死在代码里，由 card_schema 控制
-- 预置默认 8 页配置（与 v3 保持兼容）

CREATE TABLE IF NOT EXISTS card_schema (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_no INTEGER NOT NULL,               -- 页码 1-8
    card_title TEXT NOT NULL,               -- 卡片标题（如"首页"、"公司简介"）
    field_key TEXT NOT NULL,                -- 字段 key
    display_label TEXT,                     -- 卡片上的展示标签
    render_order INTEGER,                   -- 字段在卡片上的渲染顺序
    required INTEGER DEFAULT 0,             -- 是否必填
    max_length INTEGER,                     -- 最大字数
    render_type TEXT DEFAULT 'text',        -- text|markdown|image|chart|metric
    card_set_key TEXT DEFAULT 'v3'         -- v1|v2|v3
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_card_schema_unique ON card_schema(card_no, field_key, card_set_key);

-- 预置 v3 8 页卡片配置
INSERT OR IGNORE INTO card_schema (card_no, card_title, field_key, display_label, render_order, required, render_type, card_set_key) VALUES
-- 第1页：首页
(1, '首页', 'company_name', '公司名称', 1, 1, 'text', 'v3'),
(1, '首页', 'company_category', '公司分类', 2, 1, 'text', 'v3'),
-- 第2页：公司简介
(2, '公司简介', 'market_landscape_summary', '赛道市场格局', 1, 1, 'text', 'v3'),
(2, '公司简介', 'market_landscape_top_players', '赛道主要玩家', 2, 0, 'text', 'v3'),
(2, '公司简介', 'market_size_value', '赛道市场规模', 3, 0, 'metric', 'v3'),
(2, '公司简介', 'market_cagr', '赛道年复合增长率', 4, 0, 'metric', 'v3'),
(2, '公司简介', 'tam_value', '总潜在市场', 5, 0, 'metric', 'v3'),
(2, '公司简介', 'location', '地理位置', 6, 0, 'text', 'v3'),
(2, '公司简介', 'founded_date', '成立时间', 7, 0, 'text', 'v3'),
(2, '公司简介', 'core_business', '主营业务', 8, 1, 'text', 'v3'),
(2, '公司简介', 'core_competency', '核心竞争优势', 9, 1, 'text', 'v3'),
(2, '公司简介', 'funding_info', '融资情况', 10, 0, 'text', 'v3'),
(2, '公司简介', 'company_achievements', '公司成就', 11, 0, 'markdown', 'v3'),
(2, '公司简介', 'industry_positioning', '行业定位', 12, 0, 'text', 'v3'),
-- 第3页：主产品
(3, '主产品', 'main_product_name', '产品名称', 1, 1, 'text', 'v3'),
(3, '主产品', 'product_pain_points', '针对的痛点', 2, 1, 'text', 'v3'),
(3, '主产品', 'product_core_features', '核心功能', 3, 1, 'markdown', 'v3'),
(3, '主产品', 'product_usage_playbook', '核心用法', 4, 0, 'markdown', 'v3'),
(3, '主产品', 'product_tech_stack', '技术栈', 5, 0, 'text', 'v3'),
(3, '主产品', 'regional_market_focus', '地区市场', 6, 0, 'text', 'v3'),
(3, '主产品', 'mau', '月活跃用户', 7, 0, 'metric', 'v3'),
(3, '主产品', 'retention_rate', '留存率', 8, 0, 'metric', 'v3'),
(3, '主产品', 'retention_definition', '留存定义', 9, 0, 'text', 'v3'),
(3, '主产品', 'pricing_summary', '定价简述', 10, 0, 'text', 'v3'),
(3, '主产品', 'pricing_tiers', '定价明细', 11, 0, 'markdown', 'v3'),
-- 第4页：创始团队
(4, '创始团队', 'founder_name', '创始人姓名', 1, 1, 'text', 'v3'),
(4, '创始团队', 'founder_edu', '学历背景', 2, 0, 'text', 'v3'),
(4, '创始团队', 'founder_bg', '职业背景', 3, 1, 'markdown', 'v3'),
(4, '创始团队', 'founder_achievement', '关键成就', 4, 0, 'markdown', 'v3'),
(4, '创始团队', 'team_size', '团队规模', 5, 0, 'metric', 'v3'),
(4, '创始团队', 'team_highlight', '团队亮点', 6, 0, 'text', 'v3'),
-- 第5页：用户群体
(5, '用户群体', 'ideal_customer_profile', '用户画像', 1, 1, 'text', 'v3'),
(5, '用户群体', 'customer_segment_primary', '主要客户群', 2, 1, 'text', 'v3'),
(5, '用户群体', 'customer_names', '具体客户名称', 3, 0, 'text', 'v3'),
(5, '用户群体', 'customer_selection_reasons', '客户选择理由', 4, 1, 'markdown', 'v3'),
(5, '用户群体', 'customer_choice_evidence', '数据与事实支撑', 5, 0, 'markdown', 'v3'),
-- 第6页：公司能力分析
(6, '公司能力分析', 'ecosystem_niche', '生态位分析', 1, 1, 'markdown', 'v3'),
(6, '公司能力分析', 'revenue_model', '盈利策略', 2, 1, 'text', 'v3'),
(6, '公司能力分析', 'pricing_strategy', '定价策略', 3, 0, 'text', 'v3'),
(6, '公司能力分析', 'ltv', 'LTV', 4, 0, 'metric', 'v3'),
(6, '公司能力分析', 'cac', 'CAC', 5, 0, 'metric', 'v3'),
(6, '公司能力分析', 'ltv_cac_ratio', 'LTV/CAC', 6, 0, 'metric', 'v3'),
-- 第7页：增长与GTM
(7, '增长与GTM', 'growth_strategy', '增长策略', 1, 1, 'markdown', 'v3'),
(7, '增长与GTM', 'gtm_motion', 'GTM打法', 2, 1, 'text', 'v3'),
(7, '增长与GTM', 'cold_start', '冷启动策略', 3, 1, 'markdown', 'v3'),
(7, '增长与GTM', 'growth_flywheel', '增长飞轮', 4, 0, 'text', 'v3'),
(7, '增长与GTM', 'acquisition_channels', '渠道结构', 5, 0, 'text', 'v3'),
-- 第8页：竞争态势
(8, '竞争态势', 'competitors_top3', 'Top3 公司简介', 1, 1, 'markdown', 'v3'),
(8, '竞争态势', 'competitive_position', '被研公司竞争位置', 2, 1, 'markdown', 'v3'),
(8, '竞争态势', 'differentiated_opportunity', '错位竞争机会', 3, 0, 'markdown', 'v3'),
(8, '竞争态势', 'competitive_advantages', '竞争优势', 4, 1, 'text', 'v3');
