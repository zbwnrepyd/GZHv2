-- 032_packed_context_logs: 上下文打包日志表
-- 噪音与上下文治理层 — 记录每次给 LLM 的上下文预算使用情况

CREATE TABLE IF NOT EXISTS packed_context_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    company_key TEXT NOT NULL,
    target_type TEXT NOT NULL,    -- l0 | field | analysis | card
    target_key TEXT NOT NULL,     -- field_key or "l0_full" or "analysis"
    budget_tokens INTEGER,
    used_tokens INTEGER,
    chunk_ids TEXT,               -- JSON array of chunk ids
    evidence_span_ids TEXT,       -- JSON array of evidence_span ids
    dropped_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_packed_context_logs_company
ON packed_context_logs(company_key, target_type, target_key);
