-- 020: 公司主体表 companies
-- PDF §5.1 — 公司主体信息，company_key 作为主身份
CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    canonical_name TEXT,
    aliases TEXT,                          -- JSON array
    website_url TEXT,
    company_category TEXT,
    company_definition TEXT,
    founded_date TEXT,
    hq_country TEXT,
    hq_city TEXT,
    main_business TEXT,
    core_advantage TEXT,
    industry_positioning TEXT,
    data_confidence TEXT DEFAULT 'medium',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_companies_key ON companies(company_key);
CREATE INDEX IF NOT EXISTS idx_companies_category ON companies(company_category);
