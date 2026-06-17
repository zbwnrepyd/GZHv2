-- 023: 赛道表 sectors
-- PDF §5.4 — 文本判断存 sectors，具体数字进 metrics
CREATE TABLE IF NOT EXISTS sectors (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    sector_name TEXT,
    market_landscape TEXT,                 -- 赛道市场格局
    market_size_summary TEXT,              -- 文本摘要（口径：年份+地区+细分+来源）
    market_cagr_summary TEXT,
    tam_summary TEXT,
    source_note TEXT,
    confidence TEXT DEFAULT 'medium',
    FOREIGN KEY (company_key) REFERENCES companies(company_key)
);

CREATE INDEX IF NOT EXISTS idx_sectors_company ON sectors(company_key);
