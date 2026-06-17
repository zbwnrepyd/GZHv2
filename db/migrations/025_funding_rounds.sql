-- 025: 融资表 funding_rounds
-- PDF §5.6 — 融资轮次聚合生成第2页融资情况
CREATE TABLE IF NOT EXISTS funding_rounds (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    round_name TEXT,                       -- Seed|Series A|Series B|...
    announced_date TEXT,
    amount_usd REAL,
    valuation_usd REAL,
    lead_investor TEXT,
    investors TEXT,                        -- JSON array or comma-separated
    source_id TEXT,                        -- source_documents.id
    confidence TEXT DEFAULT 'medium',
    FOREIGN KEY (company_key) REFERENCES companies(company_key)
);

CREATE INDEX IF NOT EXISTS idx_funding_rounds_company ON funding_rounds(company_key);
CREATE INDEX IF NOT EXISTS idx_funding_rounds_date ON funding_rounds(company_key, announced_date);
