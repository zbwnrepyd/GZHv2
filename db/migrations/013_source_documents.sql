-- 013_source_documents: 来源文档表
-- P1: 采集结果先入 source_documents，再抽取 evidence_spans
-- 替代当前 evidence_items 的轻量存储

CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    company_key TEXT NOT NULL,
    source_type TEXT,       -- official_site|official_blog|pricing_page|case_study|press_release|media_article|github|youtube|youtube_transcript|product_hunt|hacker_news|reddit|market_report|database|manual
    source_url TEXT,
    title TEXT,
    publisher TEXT,
    published_at TEXT,
    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    raw_text TEXT,
    content_hash TEXT,
    trust_tier TEXT,        -- official|trusted_media|financial_database|community|search
    intent TEXT             -- 采集意图 (overview|founders|funding|...)
);

CREATE INDEX IF NOT EXISTS idx_source_docs_company ON source_documents(company_key);
CREATE INDEX IF NOT EXISTS idx_source_docs_run ON source_documents(run_id);
CREATE INDEX IF NOT EXISTS idx_source_docs_type ON source_documents(source_type);
