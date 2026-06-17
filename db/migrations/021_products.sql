-- 021: 产品表 products
-- PDF §5.2 — 公司产品信息，is_primary 标识主产品
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    name TEXT NOT NULL,
    is_primary INTEGER DEFAULT 0,
    product_definition TEXT,
    target_pain_points TEXT,
    core_features TEXT,
    usage_play TEXT,
    tech_stack TEXT,
    regional_markets TEXT,
    pricing_detail TEXT,
    product_url TEXT,
    screenshot_asset_id TEXT,
    confidence TEXT DEFAULT 'medium',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_key) REFERENCES companies(company_key)
);

CREATE INDEX IF NOT EXISTS idx_products_company ON products(company_key);
CREATE INDEX IF NOT EXISTS idx_products_primary ON products(company_key, is_primary);
