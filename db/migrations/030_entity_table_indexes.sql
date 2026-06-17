-- 030: 规范化实体表补充索引 + 外键关联优化
-- 为 source_documents/evidence_spans/field_candidates 增加 company_key 外键

-- source_documents 增加外键（源表已有 company_key 列）
CREATE INDEX IF NOT EXISTS idx_source_docs_company ON source_documents(company_key);
CREATE INDEX IF NOT EXISTS idx_source_docs_type ON source_documents(source_type);

-- evidence_spans 补充索引（源表已有 company_key + document_id 列）
CREATE INDEX IF NOT EXISTS idx_evidence_spans_company_key ON evidence_spans(company_key);
CREATE INDEX IF NOT EXISTS idx_evidence_spans_doc ON evidence_spans(document_id);
CREATE INDEX IF NOT EXISTS idx_evidence_spans_field ON evidence_spans(field_key, company_key);

-- field_candidates 补充索引
CREATE INDEX IF NOT EXISTS idx_field_candidates_run ON field_candidates(run_id);
CREATE INDEX IF NOT EXISTS idx_field_candidates_field ON field_candidates(company_key, field_key);
CREATE INDEX IF NOT EXISTS idx_field_candidates_selected ON field_candidates(company_key, field_key, selected);
