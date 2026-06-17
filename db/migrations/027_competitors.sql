-- 027: 竞品表 competitors
-- PDF §5.8 — 竞争态势，映射第8页字段
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    competitor_name TEXT NOT NULL,
    competitor_url TEXT,
    product_summary TEXT,                  -- 产品简介
    company_summary TEXT,                  -- Top3公司简介
    rank INTEGER,
    overlap_area TEXT,                     -- 重合领域
    difference_area TEXT,                  -- 差异领域
    competitor_strength TEXT,
    competitor_weakness TEXT,
    source_id TEXT,                        -- source_documents.id
    confidence TEXT DEFAULT 'medium',
    FOREIGN KEY (company_key) REFERENCES companies(company_key)
);

CREATE INDEX IF NOT EXISTS idx_competitors_company ON competitors(company_key);
CREATE INDEX IF NOT EXISTS idx_competitors_rank ON competitors(company_key, rank);
