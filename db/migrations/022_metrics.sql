-- 022: 指标表 metrics
-- PDF §5.3 — 公司运营与市场指标，entity_type/entity_id 支持公司级和产品级指标
CREATE TABLE IF NOT EXISTS metrics (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    entity_type TEXT NOT NULL,            -- 'company' | 'product'
    entity_id TEXT,                        -- companies.id or products.id
    metric_key TEXT NOT NULL,              -- market_size|cagr|tam|sam|som|arr|mrr|mau|ltv|cac|...
    metric_value REAL,
    metric_text TEXT,
    unit TEXT,                             -- 'USD'|'count'|'percent'|...
    period TEXT,                           -- '2024Q1'|'2024'|...
    region TEXT,                           -- 'global'|'US'|'China'|...
    segment TEXT,                          -- 细分赛道
    source_id TEXT,                        -- source_documents.id
    status TEXT DEFAULT 'unavailable',     -- confirmed|derived|proxy|industry_avg|unavailable
    estimate_method TEXT,
    confidence TEXT DEFAULT 'medium',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_key) REFERENCES companies(company_key)
);

CREATE INDEX IF NOT EXISTS idx_metrics_company ON metrics(company_key);
CREATE INDEX IF NOT EXISTS idx_metrics_key ON metrics(company_key, metric_key);
CREATE INDEX IF NOT EXISTS idx_metrics_entity ON metrics(entity_type, entity_id);
