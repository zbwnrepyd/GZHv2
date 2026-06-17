-- 015_field_candidates: 候选字段表
-- P1: 替代混在一起的 Standard/Business/Spread 三版本
-- 每个 Agent 产生的候选值独立存储，附带证据绑定与置信度

CREATE TABLE IF NOT EXISTS field_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    company_key TEXT NOT NULL,
    field_key TEXT NOT NULL,
    agent_name TEXT,                -- 产生候选的 Agent
    candidate_value TEXT,           -- 候选值
    evidence_span_ids TEXT,         -- JSON 数组: [span_id, ...]
    confidence REAL,                -- 0.0-1.0
    status TEXT DEFAULT 'active',   -- active|selected|rejected|superseded
    conflict_group_id TEXT,         -- 冲突分组 ID
    reasoning_summary TEXT,         -- LLM 推理摘要
    selected INTEGER DEFAULT 0,    -- 1=被选为最终候选
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_field_candidates_company ON field_candidates(company_key);
CREATE INDEX IF NOT EXISTS idx_field_candidates_run ON field_candidates(run_id);
CREATE INDEX IF NOT EXISTS idx_field_candidates_field ON field_candidates(company_key, field_key);
