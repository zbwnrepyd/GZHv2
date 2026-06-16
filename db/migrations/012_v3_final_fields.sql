-- 012_v3_final_fields.sql — v3 定稿字段层扩列
-- 应用于: final_db.sqlite

ALTER TABLE final_fields ADD COLUMN card_set_key TEXT DEFAULT 'v1';
ALTER TABLE final_fields ADD COLUMN page_no INTEGER;
ALTER TABLE final_fields ADD COLUMN block_key TEXT;
ALTER TABLE final_fields ADD COLUMN block_type TEXT DEFAULT 'field';
ALTER TABLE final_fields ADD COLUMN render_json TEXT;
ALTER TABLE final_fields ADD COLUMN export_targets TEXT DEFAULT '["markdown","pdf","notion"]';
