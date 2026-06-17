"""旧宽表 → 规范化实体表 数据迁移

用法:
    python3 -m webapp.db.migrate_entities [--dry-run] [--company-key KEY]

将 research 宽表 + research_fields 的历史数据回填到:
    companies, products, metrics, sectors, founders,
    funding_rounds, customers, competitors, company_analysis

安全策略:
    - 按 company_key 去重，优先选 standard 版本
    - 每次 upsert 覆盖（可重复运行）
    - 不删除旧宽表数据
"""
from __future__ import annotations
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id():
    return str(uuid.uuid4())


def _safe_str(v, default=""):
    s = str(v or "").strip()
    return s if s not in ("暂缺", "N/A", "None", "") else default


def _safe_num(v):
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _parse_aliases(row: dict) -> list:
    """收集所有已知名称作为别名。"""
    aliases = set()
    for k in ("input_name", "display_name", "company_name"):
        v = _safe_str(row.get(k))
        if v:
            aliases.add(v)
    # 移除 company_key 自身
    ck = _safe_str(row.get("company_key"))
    aliases.discard(ck)
    return sorted(aliases)


def _parse_location(loc: str) -> tuple[str, str]:
    """解析 location → (city, country)。"""
    if not loc or not loc.strip():
        return "", ""
    parts = [p.strip() for p in loc.replace("，", ",").split(",")]
    if len(parts) == 1:
        return parts[0], ""
    return ", ".join(parts[:-1]), parts[-1]


def _extract_numeric(text: str) -> float | None:
    """从文本中提取数值（如 "$1.5M" → 1500000）。"""
    import re
    t = str(text or "").strip()
    if not t:
        return None
    # $1.5M / $150B / 1,000,000
    m = re.search(r'\$?([\d,]+\.?\d*)\s*(B|b|M|m|K|k|亿|万)?', t)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower()
        if unit in ("b",):
            num *= 1_000_000_000
        elif unit in ("m",):
            num *= 1_000_000
        elif unit in ("k",):
            num *= 1_000
        elif unit == "亿":
            num *= 100_000_000
        elif unit == "万":
            num *= 10_000
        return num
    except ValueError:
        return None


def migrate(db_path: str, dry_run: bool = False, company_key: str = ""):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # 获取所有已研究公司
    where = "WHERE company_key=?" if company_key else ""
    params = (company_key,) if company_key else ()

    all_companies = conn.execute(
        f"""SELECT company_name, display_name, input_name, company_key,
                   website_url, company_type, company_def, founded_date,
                   location, core_business, core_competency,
                   industry_positioning, data_confidence, version, created_at,
                   website_host
            FROM research
            WHERE company_name IS NOT NULL AND company_name != ''
            {where}
            ORDER BY company_name, CASE version WHEN 'standard' THEN 0 ELSE 1 END""",
        params,
    ).fetchall()

    # 生成/回填 company_key，按 key 去重取 standard 版本优先
    def _derive_company_key(row) -> str:
        """从行数据推导 company_key：优先用已有值，其次 website_host，最后 lower(name)"""
        ck = _safe_str(row["company_key"] if "company_key" in row.keys() else "")
        if ck and ck.strip():
            return ck.strip().lower()
        host = _safe_str(row["website_host"] if "website_host" in row.keys() else "")
        if host:
            from urllib.parse import urlparse
            parsed = urlparse(f"https://{host}" if "://" not in host else host)
            return parsed.netloc or parsed.hostname or host.lower()
        return row["company_name"].lower().strip()

    seen_keys = set()
    unique_companies = []
    for r in all_companies:
        ck = _derive_company_key(r)
        if ck in seen_keys:
            continue
        seen_keys.add(ck)
        # 将推导的 key 写入 row（原 row 是 sqlite3.Row 不可变，转为 dict）
        r_dict = dict(r)
        r_dict["company_key"] = ck
        unique_companies.append(r_dict)

    stats = {
        "companies": 0, "products": 0, "metrics": 0,
        "sectors": 0, "founders": 0, "funding_rounds": 0,
        "customers": 0, "competitors": 0, "company_analysis": 0,
        "skipped": 0,
    }

    from repositories.entity_repo import (
        upsert_company, upsert_product, upsert_metric,
        upsert_sector, upsert_founder, upsert_funding_round,
        upsert_customer, upsert_competitor, upsert_analysis,
    )

    for row in unique_companies:
        ck = row["company_key"]
        cn = row["company_name"]
        if dry_run:
            print(f"[DRY RUN] {cn} ({ck})")
            stats["companies"] += 1
            continue

        # ── 1. companies ──
        hq_city, hq_country = _parse_location(row["location"] or "")
        aliases = _parse_aliases(row)

        company_data = {
            "company_key": ck,
            "name": cn,
            "canonical_name": _safe_str(row.get("display_name")) or cn,
            "aliases": aliases,
            "website_url": _safe_str(row.get("website_url")),
            "company_category": _safe_str(row.get("company_type")),
            "company_definition": _safe_str(row.get("company_def")),
            "founded_date": _safe_str(row.get("founded_date")),
            "hq_country": hq_country,
            "hq_city": hq_city,
            "main_business": _safe_str(row.get("core_business")),
            "core_advantage": _safe_str(row.get("core_competency")),
            "industry_positioning": _safe_str(row.get("industry_positioning")),
            "data_confidence": _safe_str(row.get("data_confidence"), "medium"),
        }
        if upsert_company(db_path, company_data):
            stats["companies"] += 1

        # ── 2. products ──
        product_names = set()
        main_name = _safe_str(row.get("main_product_name"))
        if main_name:
            upsert_product(db_path, {
                "company_key": ck,
                "name": main_name,
                "is_primary": 1,
                "product_definition": _safe_str(row.get("main_product_def")),
                "core_features": (_safe_str(row.get("main_product_highlight")) or
                                _safe_str(row.get("product_core_features"))),
                "usage_play": _safe_str(row.get("product_usage_playbook")),
                "tech_stack": _safe_str(row.get("product_tech_stack")) or
                              _safe_str(row.get("tech_stack")),
                "regional_markets": _safe_str(row.get("regional_market_focus")) or
                                    _safe_str(row.get("regional_markets")),
                "pricing_detail": (_safe_str(row.get("pricing_summary")) + "\n" +
                                 _safe_str(row.get("pricing_tiers"))).strip(),
                "screenshot_asset_id": _safe_str(row.get("main_product_img_src")),
            })
            stats["products"] += 1
            product_names.add(main_name.lower())

        # other_products
        other_raw = row.get("other_products") or ""
        if other_raw and other_raw.strip():
            try:
                other_list = json.loads(other_raw) if other_raw.startswith("[") else []
            except json.JSONDecodeError:
                other_list = []
            for op in other_list:
                if isinstance(op, dict):
                    op_name = _safe_str(op.get("name"))
                    if op_name and op_name.lower() not in product_names:
                        upsert_product(db_path, {
                            "company_key": ck,
                            "name": op_name,
                            "is_primary": 0,
                            "product_definition": _safe_str(op.get("def")) or
                                                _safe_str(op.get("product_definition")),
                            "core_features": _safe_str(op.get("highlight")),
                        })
                        stats["products"] += 1
                        product_names.add(op_name.lower())

        # ── 3. metrics ──
        metric_map = {
            "market_size": ("market_size_value", "market_size_currency", "market_size_year"),
            "cagr": ("market_cagr",),
            "tam": ("tam_value", "tam_currency", "tam_year"),
            "sam": ("sam",),
            "som": ("som",),
            "arr": ("arr",),
            "mrr": ("mrr",),
            "mau": ("mau", "mau_as_of"),
            "registered_users": ("registered_users",),
            "active_users": ("active_users",),
            "paying_users": ("paying_users",),
            "retention_rate": ("retention_rate", "retention_definition"),
            "churn_rate": ("churn_rate",),
            "cac": ("cac",),
            "ltv": ("ltv",),
            "ltv_cac_ratio": ("ltv_cac_ratio",),
            "gross_margin": ("gross_margin",),
            "burn_rate": ("burn_rate",),
            "runway_months": ("runway_months",),
            "team_size": ("team_size",),
        }

        for mkey, columns in metric_map.items():
            val = None
            unit = "USD" if mkey not in ("retention_rate", "churn_rate", "mau",
                                         "registered_users", "active_users",
                                         "paying_users", "runway_months", "team_size") else ""
            period = ""
            text_val = ""

            for col in columns:
                raw_val = row.get(col)
                if raw_val is not None and str(raw_val).strip() not in ("", "暂缺"):
                    if col.endswith("_value") or col in ("market_cagr", "retention_rate",
                                                         "cac", "ltv", "ltv_cac_ratio", "mau"):
                        num = _safe_num(raw_val)
                        if num is not None:
                            val = num
                    elif col.endswith("_currency"):
                        unit = str(raw_val).strip()
                    elif col.endswith("_year") or col.endswith("_as_of"):
                        period = str(raw_val).strip()
                    else:
                        text_val = str(raw_val).strip()

            if val is not None or text_val:
                num_val = val if val is not None else (_extract_numeric(text_val) if text_val else None)
                upsert_metric(db_path, {
                    "company_key": ck,
                    "entity_type": "company",
                    "metric_key": mkey,
                    "metric_value": num_val,
                    "metric_text": str(val) if val is not None else text_val,
                    "unit": unit,
                    "period": period,
                    "status": "llm_extracted",
                })
                stats["metrics"] += 1

        # ── 4. sectors ──
        landscape = (_safe_str(row.get("market_landscape_summary")) + "\n" +
                    _safe_str(row.get("market_landscape_top_players"))).strip()
        tam_text = (_safe_str(row.get("tam")) or
                   f"{_safe_str(row.get('tam_value'))} {_safe_str(row.get('tam_currency'))} "
                   f"({_safe_str(row.get('tam_year'))})")

        if landscape or tam_text or _safe_str(row.get("market_cagr")):
            upsert_sector(db_path, {
                "company_key": ck,
                "sector_name": _safe_str(row.get("company_type")),
                "market_landscape": landscape,
                "market_size_summary": _safe_str(row.get("market_size_source_note")),
                "market_cagr_summary": str(row.get("market_cagr") or ""),
                "tam_summary": tam_text.strip(),
            })
            stats["sectors"] += 1

        # ── 5. founders ──
        founder_name = _safe_str(row.get("founder_name"))
        if founder_name:
            upsert_founder(db_path, {
                "company_key": ck,
                "name": founder_name,
                "role": "Co-Founder & CEO",
                "education": _safe_str(row.get("founder_edu")),
                "career_background": _safe_str(row.get("founder_bg")),
                "founder_achievement": (_safe_str(row.get("founder_achievement")) or
                                       _safe_str(row.get("company_achievement")) or
                                       _safe_str(row.get("company_achievements"))),
                "credibility_note": _safe_str(row.get("team_highlight")),
            })
            stats["founders"] += 1

        # ── 6. funding_rounds ──
        funding_raw = row.get("funding_rounds") or row.get("funding_info") or ""
        if funding_raw and funding_raw.strip() not in ("", "暂缺"):
            # 尝试 JSON 解析
            rounds = []
            if funding_raw.startswith("[") or funding_raw.startswith("{"):
                try:
                    parsed = json.loads(funding_raw)
                    if isinstance(parsed, list):
                        rounds = parsed
                    elif isinstance(parsed, dict):
                        rounds = [parsed]
                except json.JSONDecodeError:
                    pass

            if rounds:
                for fr in rounds:
                    if isinstance(fr, dict):
                        upsert_funding_round(db_path, {
                            "company_key": ck,
                            "round_name": _safe_str(fr.get("round") or fr.get("round_name") or
                                                    fr.get("name")),
                            "announced_date": _safe_str(fr.get("date") or fr.get("announced_date")),
                            "amount_usd": _extract_numeric(fr.get("amount")) or
                                         _safe_num(fr.get("amount_usd")),
                            "lead_investor": _safe_str(fr.get("lead_investor") or fr.get("lead")),
                            "investors": _safe_str(fr.get("investors")) or
                                        _safe_str(fr.get("investor")),
                            "confidence": "medium",
                        })
                        stats["funding_rounds"] += 1
            else:
                # 自由文本 — 创建单条记录
                upsert_funding_round(db_path, {
                    "company_key": ck,
                    "round_name": _safe_str(row.get("funding_stage")) or "Total Funding",
                    "amount_usd": _extract_numeric(funding_raw),
                    "investors": funding_raw[:500],
                    "confidence": "low",
                })
                stats["funding_rounds"] += 1

        # ── 7. customers ──
        customer_names_raw = _safe_str(row.get("customer_names"))
        if customer_names_raw:
            for cn_name in customer_names_raw.replace("、", ",").replace("，", ",").split(","):
                cn_name = cn_name.strip()
                if cn_name and len(cn_name) > 1:
                    upsert_customer(db_path, {
                        "company_key": ck,
                        "customer_type": "named_customer",
                        "customer_name": cn_name,
                        "choice_reason": _safe_str(row.get("customer_selection_reasons")),
                        "evidence_summary": _safe_str(row.get("customer_choice_evidence")),
                    })
                    stats["customers"] += 1

        # 客户画像
        persona = (_safe_str(row.get("ideal_customer_profile")) or
                  _safe_str(row.get("customer_segment_primary")))
        if persona:
            upsert_customer(db_path, {
                "company_key": ck,
                "customer_type": "persona",
                "persona_name": persona,
                "industry": _safe_str(row.get("customer_segment")) or
                           _safe_str(row.get("customer_segment_secondary")),
            })
            stats["customers"] += 1

        # ── 8. competitors ──
        competitors_raw = row.get("competitors") or ""
        if competitors_raw and competitors_raw.strip():
            try:
                comp_list = json.loads(competitors_raw) if competitors_raw.startswith("[") else []
            except json.JSONDecodeError:
                comp_list = []
            for i, comp in enumerate(comp_list):
                if isinstance(comp, dict):
                    upsert_competitor(db_path, {
                        "company_key": ck,
                        "competitor_name": _safe_str(comp.get("name") or comp.get("competitor_name")),
                        "product_summary": _safe_str(comp.get("product") or comp.get("data")),
                        "rank": i + 1,
                    })
                    stats["competitors"] += 1

        # competitors_top3 文本解析
        top3_raw = _safe_str(row.get("competitors_top3"))
        if top3_raw and not competitors_raw.strip():
            for i, line in enumerate(top3_raw.split("\n")[:3]):
                line = line.strip()
                if line and len(line) > 2:
                    upsert_competitor(db_path, {
                        "company_key": ck,
                        "competitor_name": line[:100],
                        "company_summary": line,
                        "rank": i + 1,
                    })
                    stats["competitors"] += 1

        # ── 9. company_analysis ──
        analysis_data = {
            "company_key": ck,
            "ecosystem_niche": (_safe_str(row.get("ecosystem_niche")) or
                              _safe_str(row.get("ecosystem_positioning"))),
            "monetization_strategy": _safe_str(row.get("revenue_model")),
            "pricing_strategy": (_safe_str(row.get("pricing_strategy")) or
                               _safe_str(row.get("pricing_model"))),
            "value_capture_score": _safe_num(row.get("score_value_capture")),
            "defensibility_score": _safe_num(row.get("score_defensibility")),
            "competitive_position": _safe_str(row.get("competitive_position")),
            "differentiation_opportunity": (_safe_str(row.get("differentiated_opportunity")) or
                                          _safe_str(row.get("differentiation_strategy"))),
            "competitive_advantage": (_safe_str(row.get("competitive_advantages")) or
                                     _safe_str(row.get("cost_advantage"))),
            "moat": (_safe_str(row.get("moat")) + "; " +
                    _safe_str(row.get("technical_barrier")) + "; " +
                    _safe_str(row.get("switching_cost"))).strip("; "),
            "gtm_motion": _safe_str(row.get("gtm_motion")),
            "cold_start": _safe_str(row.get("cold_start")),
            "growth_strategy": _safe_str(row.get("growth_strategy")),
            "growth_flywheel": _safe_str(row.get("growth_flywheel")),
            "analysis_version": 1,
            "confidence": _safe_str(row.get("data_confidence"), "medium"),
        }
        # 只写入有内容的分析记录
        has_content = any(
            v not in (None, "", 0, 0.0)
            for k, v in analysis_data.items()
            if k not in ("company_key", "analysis_version", "confidence")
        )
        if has_content:
            upsert_analysis(db_path, analysis_data)
            stats["company_analysis"] += 1
        else:
            stats["skipped"] += 1

    conn.close()
    return stats


def main():
    import argparse
    p = argparse.ArgumentParser(description="迁移 research 宽表 → 规范化实体表")
    p.add_argument("db_path", default="db/research_db.sqlite", nargs="?")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--company-key", default="")
    args = p.parse_args()

    print(f"数据库: {args.db_path}")
    if args.dry_run:
        print("模式: DRY RUN (不写入)")
    if args.company_key:
        print(f"限制: company_key={args.company_key}")

    stats = migrate(args.db_path, args.dry_run, args.company_key)
    print("\n迁移统计:")
    for table, count in stats.items():
        if count > 0:
            print(f"  {table}: {count}")


if __name__ == "__main__":
    main()
