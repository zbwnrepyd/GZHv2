-- 024: 创始团队表 founders
-- PDF §5.5 — 创始人信息，新增 credibility_note
CREATE TABLE IF NOT EXISTS founders (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT,                             -- CEO|CTO|Co-Founder|...
    education TEXT,                        -- 学历背景
    career_background TEXT,                -- 职业背景
    founder_achievement TEXT,              -- 关键成就
    credibility_note TEXT,                 -- 为什么这个团队适合做这家公司？
    linkedin_url TEXT,
    confidence TEXT DEFAULT 'medium',
    FOREIGN KEY (company_key) REFERENCES companies(company_key)
);

CREATE INDEX IF NOT EXISTS idx_founders_company ON founders(company_key);
