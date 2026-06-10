-- 007_card_sets_final.sql — 套卡系统（final_db）
-- 执行：sqlite3 db/final_db.sqlite < db/migrations/007_card_sets_final.sql

-- 重建 final_content（加 card_set_key，更新 UNIQUE 约束）
CREATE TABLE final_content_new (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name    TEXT    NOT NULL,
    card_set_key    TEXT    NOT NULL DEFAULT 'v1',
    card_index      INTEGER NOT NULL,
    field_name      TEXT    NOT NULL,
    field_value     TEXT,
    img_local_path  TEXT,
    confirmed_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO final_content_new
    (id, company_name, card_set_key, card_index,
     field_name, field_value, img_local_path, confirmed_at)
SELECT id, company_name, 'v1', card_index,
       field_name, field_value, img_local_path, confirmed_at
FROM final_content;

DROP TABLE final_content;
ALTER TABLE final_content_new RENAME TO final_content;

CREATE INDEX idx_final_company ON final_content(company_name);
CREATE INDEX idx_final_card
    ON final_content(company_name, card_set_key, card_index);
CREATE UNIQUE INDEX idx_final_unique_field
    ON final_content(company_name, card_set_key, card_index, field_name);
