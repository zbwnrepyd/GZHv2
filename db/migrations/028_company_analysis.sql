-- 028: 公司分析表 company_analysis
-- PDF §5.9 — 推理结果，不存原始事实，尽量引用 evidence_spans
CREATE TABLE IF NOT EXISTS company_analysis (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    ecosystem_niche TEXT,                  -- 生态位分析
    monetization_strategy TEXT,            -- 盈利策略
    pricing_strategy TEXT,                 -- 定价策略
    value_capture_score REAL,              -- 变现能力评分 0-10
    defensibility_score REAL,              -- 壁垒评分 0-10
    competitive_position TEXT,             -- 被研公司在竞争中的位置
    differentiation_opportunity TEXT,      -- 错位竞争机会
    competitive_advantage TEXT,            -- 竞争优势
    moat TEXT,                             -- 壁垒
    risk_window TEXT,                      -- 风险窗口
    gtm_motion TEXT,                       -- GTM 打法
    cold_start TEXT,                       -- 冷启动策略
    growth_strategy TEXT,                  -- 增长策略
    growth_flywheel TEXT,                  -- 增长飞轮
    analysis_version INTEGER DEFAULT 1,
    confidence TEXT DEFAULT 'medium',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_key) REFERENCES companies(company_key)
);

CREATE INDEX IF NOT EXISTS idx_company_analysis_key ON company_analysis(company_key);
