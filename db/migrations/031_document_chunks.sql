-- 031_document_chunks: 文档切块表
-- 噪音与上下文治理层 — source_documents 切块、打分、召回
-- 每篇 source_document 切为 N 个 chunk，按字段维度召回

CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    company_key TEXT NOT NULL,
    source_type TEXT,
    source_url TEXT,
    title TEXT,
    chunk_text TEXT NOT NULL,
    chunk_type TEXT DEFAULT 'unknown',
    token_estimate INTEGER DEFAULT 0,

    -- 五维评分
    source_score REAL DEFAULT 0,
    entity_score REAL DEFAULT 0,
    field_relevance_score REAL DEFAULT 0,
    freshness_score REAL DEFAULT 0,
    info_density_score REAL DEFAULT 0,
    noise_score REAL DEFAULT 0,
    final_score REAL DEFAULT 0,

    -- 标记
    is_noise INTEGER DEFAULT 0,
    matched_fields TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (document_id) REFERENCES source_documents(id)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_company
ON document_chunks(company_key);

CREATE INDEX IF NOT EXISTS idx_document_chunks_doc
ON document_chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_document_chunks_score
ON document_chunks(company_key, final_score DESC);

CREATE INDEX IF NOT EXISTS idx_document_chunks_noise
ON document_chunks(company_key, is_noise);
