-- 009_evidence_items.sql — 证据持久化层
-- 在 LLM 提取字段之前，先把采集到的原始证据写入此表，实现可追溯

CREATE TABLE IF NOT EXISTS evidence_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name TEXT NOT NULL,
  source_type TEXT NOT NULL,       -- tavily | github | youtube | website | manual
  source_url TEXT,
  source_title TEXT,
  evidence_text TEXT,              -- 证据原文片段（截断到 4000 字符）
  evidence_hash TEXT,              -- SHA256 前 16 位，用于去重
  relevance_score REAL DEFAULT 0,  -- 0-1，相关性
  reliability_score REAL DEFAULT 0,-- 0-1，来源可信度
  collected_at TEXT DEFAULT (datetime('now')),
  research_version TEXT DEFAULT 'standard',
  UNIQUE(company_name, evidence_hash, research_version)
);

CREATE INDEX IF NOT EXISTS idx_evidence_company ON evidence_items(company_name);
CREATE INDEX IF NOT EXISTS idx_evidence_hash ON evidence_items(evidence_hash);
