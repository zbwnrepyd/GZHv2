-- final_db: 人工确认后的定稿内容，按卡片组织（v2: 加 card_set_key）
CREATE TABLE IF NOT EXISTS final_content (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  company_name    TEXT    NOT NULL,
  card_set_key    TEXT    NOT NULL DEFAULT 'v1',
  card_index      INTEGER NOT NULL,
  field_name      TEXT    NOT NULL,
  field_value     TEXT,
  img_local_path  TEXT,
  confirmed_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_final_company ON final_content(company_name);
CREATE INDEX IF NOT EXISTS idx_final_card ON final_content(company_name, card_set_key, card_index);
CREATE UNIQUE INDEX IF NOT EXISTS idx_final_unique_field
  ON final_content(company_name, card_set_key, card_index, field_name);
