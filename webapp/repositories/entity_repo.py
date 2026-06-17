"""实体仓库 — 10 张归一化实体表的数据访问层

companies, products, metrics, sectors, founders, funding_rounds,
customers, competitors, company_analysis, research_runs
"""
from __future__ import annotations
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

@contextmanager
def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 1. companies  (id PK; has created_at + updated_at)
# ---------------------------------------------------------------------------

_COMPANY_COLS = [
    "id", "company_key", "name", "canonical_name", "aliases", "website_url",
    "company_category", "company_definition", "founded_date",
    "hq_country", "hq_city", "main_business", "core_advantage",
    "industry_positioning", "data_confidence", "updated_at",
]


def upsert_company(db_path: str, data: dict) -> bool:
    """INSERT OR REPLACE a company row.  data 必须包含 company_key."""
    try:
        with _get_db(db_path) as conn:
            ckey = data.get("company_key", "")
            # 保留已有 created_at，否则用当前时间
            existing = conn.execute(
                "SELECT created_at FROM companies WHERE company_key=?",
                (ckey,),
            ).fetchone()
            created_at = existing["created_at"] if existing else _now_utc()

            row_id = data.get("id") or _new_id()
            conn.execute(
                """INSERT OR REPLACE INTO companies
                   (id, company_key, name, canonical_name, aliases, website_url,
                    company_category, company_definition, founded_date,
                    hq_country, hq_city, main_business, core_advantage,
                    industry_positioning, data_confidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id, ckey,
                    data.get("name", ""),
                    data.get("canonical_name", ""),
                    json.dumps(data.get("aliases", []), ensure_ascii=False)
                    if isinstance(data.get("aliases"), list)
                    else data.get("aliases", "[]"),
                    data.get("website_url", ""),
                    data.get("company_category", ""),
                    data.get("company_definition", ""),
                    data.get("founded_date", ""),
                    data.get("hq_country", ""),
                    data.get("hq_city", ""),
                    data.get("main_business", ""),
                    data.get("core_advantage", ""),
                    data.get("industry_positioning", ""),
                    data.get("data_confidence", "medium"),
                    data.get("created_at", created_at),
                    _now_utc(),
                ),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_company(db_path: str, company_key: str) -> dict | None:
    try:
        with _get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM companies WHERE company_key=?",
                (company_key,),
            ).fetchone()
            if not row:
                return None
            d = dict(row)
            try:
                d["aliases"] = json.loads(d.get("aliases", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["aliases"] = []
            return d
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 2. products  (id PK; has created_at, no updated_at)
# ---------------------------------------------------------------------------

def upsert_product(db_path: str, data: dict) -> bool:
    try:
        with _get_db(db_path) as conn:
            row_id = data.get("id") or _new_id()
            conn.execute(
                """INSERT OR REPLACE INTO products
                   (id, company_key, name, is_primary, product_definition,
                    target_pain_points, core_features, usage_play, tech_stack,
                    regional_markets, pricing_detail, product_url,
                    screenshot_asset_id, confidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id,
                    data.get("company_key", ""),
                    data.get("name", ""),
                    1 if data.get("is_primary") else 0,
                    data.get("product_definition", ""),
                    data.get("target_pain_points", ""),
                    data.get("core_features", ""),
                    data.get("usage_play", ""),
                    data.get("tech_stack", ""),
                    data.get("regional_markets", ""),
                    data.get("pricing_detail", ""),
                    data.get("product_url", ""),
                    data.get("screenshot_asset_id", ""),
                    data.get("confidence", "medium"),
                    data.get("created_at", _now_utc()),
                ),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_products(db_path: str, company_key: str) -> list[dict]:
    try:
        with _get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM products
                   WHERE company_key=? ORDER BY is_primary DESC, name""",
                (company_key,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def get_primary_product(db_path: str, company_key: str) -> dict | None:
    try:
        with _get_db(db_path) as conn:
            row = conn.execute(
                """SELECT * FROM products
                   WHERE company_key=? AND is_primary=1 LIMIT 1""",
                (company_key,),
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 3. metrics  (id PK; has created_at, no updated_at)
#    upsert 按 (company_key, metric_key, entity_type, entity_id) 去重
# ---------------------------------------------------------------------------

def upsert_metric(db_path: str, data: dict) -> bool:
    try:
        with _get_db(db_path) as conn:
            ckey = data.get("company_key", "")
            mkey = data.get("metric_key", "")
            etype = data.get("entity_type", "company")
            eid = data.get("entity_id", "")
            existing = conn.execute(
                """SELECT id, created_at FROM metrics
                   WHERE company_key=? AND metric_key=?
                   AND entity_type=? AND entity_id IS ?""",
                (ckey, mkey, etype, eid if eid else None),
            ).fetchone()

            if existing:
                conn.execute(
                    """UPDATE metrics SET metric_value=?, metric_text=?,
                       unit=?, period=?, region=?, segment=?, source_id=?,
                       status=?, estimate_method=?, confidence=?
                       WHERE id=?""",
                    (
                        data.get("metric_value"),
                        data.get("metric_text", ""),
                        data.get("unit", ""),
                        data.get("period", ""),
                        data.get("region", ""),
                        data.get("segment", ""),
                        data.get("source_id", ""),
                        data.get("status", "unavailable"),
                        data.get("estimate_method", ""),
                        data.get("confidence", "medium"),
                        existing["id"],
                    ),
                )
            else:
                row_id = data.get("id") or _new_id()
                conn.execute(
                    """INSERT INTO metrics
                       (id, company_key, entity_type, entity_id, metric_key,
                        metric_value, metric_text, unit, period, region, segment,
                        source_id, status, estimate_method, confidence, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        row_id, ckey, etype, eid if eid else None, mkey,
                        data.get("metric_value"), data.get("metric_text", ""),
                        data.get("unit", ""), data.get("period", ""),
                        data.get("region", ""), data.get("segment", ""),
                        data.get("source_id", ""),
                        data.get("status", "unavailable"),
                        data.get("estimate_method", ""),
                        data.get("confidence", "medium"),
                        data.get("created_at", _now_utc()),
                    ),
                )
            conn.commit()
            return True
    except Exception:
        return False


def get_metrics(db_path: str, company_key: str, metric_key: str = "") -> list[dict]:
    try:
        with _get_db(db_path) as conn:
            if metric_key:
                rows = conn.execute(
                    """SELECT * FROM metrics
                       WHERE company_key=? AND metric_key=? ORDER BY metric_key""",
                    (company_key, metric_key),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM metrics
                       WHERE company_key=? ORDER BY metric_key""",
                    (company_key,),
                ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 4. sectors  (id PK; no timestamps)
# ---------------------------------------------------------------------------

def upsert_sector(db_path: str, data: dict) -> bool:
    """按 company_key 去重；一家公司只有一条赛道记录。"""
    try:
        with _get_db(db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM sectors WHERE company_key=?",
                (data.get("company_key", ""),),
            ).fetchone()
            row_id = existing["id"] if existing else (data.get("id") or _new_id())
            conn.execute(
                """INSERT OR REPLACE INTO sectors
                   (id, company_key, sector_name, market_landscape,
                    market_size_summary, market_cagr_summary, tam_summary,
                    source_note, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id,
                    data.get("company_key", ""),
                    data.get("sector_name", ""),
                    data.get("market_landscape", ""),
                    data.get("market_size_summary", ""),
                    data.get("market_cagr_summary", ""),
                    data.get("tam_summary", ""),
                    data.get("source_note", ""),
                    data.get("confidence", "medium"),
                ),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_sector(db_path: str, company_key: str) -> dict | None:
    try:
        with _get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM sectors WHERE company_key=?",
                (company_key,),
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 5. founders  (id PK; no timestamps)
# ---------------------------------------------------------------------------

def upsert_founder(db_path: str, data: dict) -> bool:
    try:
        with _get_db(db_path) as conn:
            row_id = data.get("id") or _new_id()
            conn.execute(
                """INSERT OR REPLACE INTO founders
                   (id, company_key, name, role, education, career_background,
                    founder_achievement, credibility_note, linkedin_url, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id,
                    data.get("company_key", ""),
                    data.get("name", ""),
                    data.get("role", ""),
                    data.get("education", ""),
                    data.get("career_background", ""),
                    data.get("founder_achievement", ""),
                    data.get("credibility_note", ""),
                    data.get("linkedin_url", ""),
                    data.get("confidence", "medium"),
                ),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_founders(db_path: str, company_key: str) -> list[dict]:
    try:
        with _get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM founders
                   WHERE company_key=? ORDER BY name""",
                (company_key,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 6. funding_rounds  (id PK; no timestamps)
# ---------------------------------------------------------------------------

def upsert_funding_round(db_path: str, data: dict) -> bool:
    try:
        with _get_db(db_path) as conn:
            row_id = data.get("id") or _new_id()
            conn.execute(
                """INSERT OR REPLACE INTO funding_rounds
                   (id, company_key, round_name, announced_date, amount_usd,
                    valuation_usd, lead_investor, investors, source_id, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id,
                    data.get("company_key", ""),
                    data.get("round_name", ""),
                    data.get("announced_date", ""),
                    data.get("amount_usd"),
                    data.get("valuation_usd"),
                    data.get("lead_investor", ""),
                    data.get("investors", ""),
                    data.get("source_id", ""),
                    data.get("confidence", "medium"),
                ),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_funding_rounds(db_path: str, company_key: str) -> list[dict]:
    try:
        with _get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM funding_rounds
                   WHERE company_key=? ORDER BY announced_date""",
                (company_key,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def get_total_funding(db_path: str, company_key: str) -> float:
    try:
        with _get_db(db_path) as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(amount_usd), 0) AS total
                   FROM funding_rounds WHERE company_key=?""",
                (company_key,),
            ).fetchone()
            return float(row["total"]) if row else 0.0
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# 7. customers  (id PK; no timestamps)
# ---------------------------------------------------------------------------

def upsert_customer(db_path: str, data: dict) -> bool:
    try:
        with _get_db(db_path) as conn:
            row_id = data.get("id") or _new_id()
            conn.execute(
                """INSERT OR REPLACE INTO customers
                   (id, company_key, customer_type, persona_name, customer_name,
                    industry, customer_pain, choice_reason, evidence_summary,
                    source_id, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id,
                    data.get("company_key", ""),
                    data.get("customer_type", ""),
                    data.get("persona_name", ""),
                    data.get("customer_name", ""),
                    data.get("industry", ""),
                    data.get("customer_pain", ""),
                    data.get("choice_reason", ""),
                    data.get("evidence_summary", ""),
                    data.get("source_id", ""),
                    data.get("confidence", "medium"),
                ),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_customers(db_path: str, company_key: str, customer_type: str = "") -> list[dict]:
    try:
        with _get_db(db_path) as conn:
            if customer_type:
                rows = conn.execute(
                    """SELECT * FROM customers
                       WHERE company_key=? AND customer_type=?
                       ORDER BY customer_name""",
                    (company_key, customer_type),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM customers
                       WHERE company_key=? ORDER BY customer_type, customer_name""",
                    (company_key,),
                ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 8. competitors  (id PK; no timestamps)
# ---------------------------------------------------------------------------

def upsert_competitor(db_path: str, data: dict) -> bool:
    try:
        with _get_db(db_path) as conn:
            row_id = data.get("id") or _new_id()
            conn.execute(
                """INSERT OR REPLACE INTO competitors
                   (id, company_key, competitor_name, competitor_url,
                    product_summary, company_summary, rank, overlap_area,
                    difference_area, competitor_strength, competitor_weakness,
                    source_id, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id,
                    data.get("company_key", ""),
                    data.get("competitor_name", ""),
                    data.get("competitor_url", ""),
                    data.get("product_summary", ""),
                    data.get("company_summary", ""),
                    data.get("rank"),
                    data.get("overlap_area", ""),
                    data.get("difference_area", ""),
                    data.get("competitor_strength", ""),
                    data.get("competitor_weakness", ""),
                    data.get("source_id", ""),
                    data.get("confidence", "medium"),
                ),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_competitors(db_path: str, company_key: str) -> list[dict]:
    try:
        with _get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM competitors
                   WHERE company_key=? ORDER BY rank, competitor_name""",
                (company_key,),
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# 9. company_analysis  (id PK; has created_at, no updated_at)
#    — 一家公司一条分析记录，按 company_key 去重
# ---------------------------------------------------------------------------

def upsert_analysis(db_path: str, data: dict) -> bool:
    try:
        with _get_db(db_path) as conn:
            ckey = data.get("company_key", "")
            existing = conn.execute(
                "SELECT id, created_at FROM company_analysis WHERE company_key=?",
                (ckey,),
            ).fetchone()
            row_id = existing["id"] if existing else (data.get("id") or _new_id())
            created_at = existing["created_at"] if existing else data.get("created_at", _now_utc())
            conn.execute(
                """INSERT OR REPLACE INTO company_analysis
                   (id, company_key, ecosystem_niche, monetization_strategy,
                    pricing_strategy, value_capture_score, defensibility_score,
                    competitive_position, differentiation_opportunity,
                    competitive_advantage, moat, risk_window, gtm_motion,
                    cold_start, growth_strategy, growth_flywheel,
                    analysis_version, confidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row_id, ckey,
                    data.get("ecosystem_niche", ""),
                    data.get("monetization_strategy", ""),
                    data.get("pricing_strategy", ""),
                    data.get("value_capture_score"),
                    data.get("defensibility_score"),
                    data.get("competitive_position", ""),
                    data.get("differentiation_opportunity", ""),
                    data.get("competitive_advantage", ""),
                    data.get("moat", ""),
                    data.get("risk_window", ""),
                    data.get("gtm_motion", ""),
                    data.get("cold_start", ""),
                    data.get("growth_strategy", ""),
                    data.get("growth_flywheel", ""),
                    data.get("analysis_version", 1),
                    data.get("confidence", "medium"),
                    created_at,
                ),
            )
            conn.commit()
            return True
    except Exception:
        return False


def get_analysis(db_path: str, company_key: str) -> dict | None:
    try:
        with _get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM company_analysis WHERE company_key=?",
                (company_key,),
            ).fetchone()
            return dict(row) if row else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 10. research_runs  (id PK; started_at + finished_at, 无 created_at/updated_at)
# ---------------------------------------------------------------------------

def create_research_run(db_path: str, data: dict) -> str:
    """创建研究运行记录，返回 run_id (UUID string)。"""
    run_id = data.get("id") or _new_id()
    try:
        with _get_db(db_path) as conn:
            conn.execute(
                """INSERT INTO research_runs
                   (id, company_key, display_name, input_query, research_depth,
                    status, started_at, config_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    data.get("company_key", ""),
                    data.get("display_name", ""),
                    data.get("input_query", ""),
                    data.get("research_depth", "standard"),
                    data.get("status", "pending"),
                    data.get("started_at", _now_utc()),
                    json.dumps(data.get("config_json", {}), ensure_ascii=False)
                    if isinstance(data.get("config_json"), dict)
                    else data.get("config_json", "{}"),
                ),
            )
            conn.commit()
            return run_id
    except Exception:
        return ""


def update_research_run(db_path: str, run_id: str, status: str,
                        finished_at: str = "") -> bool:
    try:
        with _get_db(db_path) as conn:
            finish = finished_at or (
                _now_utc() if status in ("completed", "failed") else None
            )
            if finish:
                conn.execute(
                    """UPDATE research_runs
                       SET status=?, finished_at=? WHERE id=?""",
                    (status, finish, run_id),
                )
            else:
                conn.execute(
                    """UPDATE research_runs SET status=? WHERE id=?""",
                    (status, run_id),
                )
            conn.commit()
            return True
    except Exception:
        return False
