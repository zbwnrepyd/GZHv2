-- 026: 客户与用户群体表 customers
-- PDF §5.7 — 用户画像/具体客户/行业分类
CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    customer_type TEXT,                    -- 'persona'|'named_customer'|'industry_segment'
    persona_name TEXT,
    customer_name TEXT,
    industry TEXT,
    customer_pain TEXT,                    -- 客户痛点
    choice_reason TEXT,                    -- 客户选择理由
    evidence_summary TEXT,                 -- 数据与事实支撑
    source_id TEXT,                        -- source_documents.id
    confidence TEXT DEFAULT 'medium',
    FOREIGN KEY (company_key) REFERENCES companies(company_key)
);

CREATE INDEX IF NOT EXISTS idx_customers_company ON customers(company_key);
CREATE INDEX IF NOT EXISTS idx_customers_type ON customers(company_key, customer_type);
