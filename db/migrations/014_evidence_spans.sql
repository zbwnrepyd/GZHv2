-- 014_evidence_spans: 证据片段表
-- P1: 从 source_documents 抽取字段级证据片段，解决字段可追溯问题

CREATE TABLE IF NOT EXISTS evidence_spans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    company_key TEXT NOT NULL,
    field_key TEXT,             -- 关联的目标字段
    quote_text TEXT,            -- 原文引用片段
    normalized_fact TEXT,       -- 规范化的陈述
    start_offset INTEGER,
    end_offset INTEGER,
    confidence REAL,
    created_by_agent TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (document_id) REFERENCES source_documents(id)
);

CREATE INDEX IF NOT EXISTS idx_evidence_spans_company ON evidence_spans(company_key);
CREATE INDEX IF NOT EXISTS idx_evidence_spans_doc ON evidence_spans(document_id);
CREATE INDEX IF NOT EXISTS idx_evidence_spans_field ON evidence_spans(field_key);
