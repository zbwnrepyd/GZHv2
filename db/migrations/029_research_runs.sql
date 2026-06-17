-- 029: 研究运行表 research_runs
-- PDF §5.12 — 追踪每次研究运行的配置、状态和结果
CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    display_name TEXT,
    input_query TEXT,                      -- 初始搜索词
    research_depth TEXT,                   -- 'standard'|'deep'
    status TEXT,                           -- 'pending'|'running'|'completed'|'failed'
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    config_json TEXT,                      -- 运行时的完整配置快照
    FOREIGN KEY (company_key) REFERENCES companies(company_key)
);

CREATE INDEX IF NOT EXISTS idx_research_runs_company ON research_runs(company_key);
CREATE INDEX IF NOT EXISTS idx_research_runs_status ON research_runs(status);
