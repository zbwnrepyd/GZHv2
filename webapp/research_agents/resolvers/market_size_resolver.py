"""市场字段解析器 — market_size_resolver

PDF §10: 专门处理市场规模、CAGR、TAM/SAM/SOM 等市场字段。
- 必须有 region/segment/year 口径
- 允许 proxy/industry_avg 但不允许未经口径检查的 confirmed
- 不满足口径要求 → manual_needed
"""
from __future__ import annotations
from typing import Optional


# 市场字段列表
MARKET_FIELD_KEYS = {
    "market_size", "market_cagr", "tam", "sam", "som",
    "market_landscape", "market_opportunity",
}

# 口径检查延迟：允许先标记 llm_extracted，口径补齐后才能 confirmed
REQUIRED_CONTEXT = {"region", "segment", "year"}


def _extract_context(field_value: str) -> dict[str, str]:
    """从字段文本中提取口径信息。"""
    ctx: dict[str, str] = {}
    text = (field_value or "").strip()
    if not text:
        return ctx

    text_lower = text.lower()

    # 年份检测
    import re
    year_patterns = [
        r'\b(20\d{2})\b',           # 2024
        r'\b(FY\d{2,4})\b',         # FY2024
        r'\b(\d{4}Q[1-4])\b',       # 2024Q1
        r'\b(\d{4}-\d{4})\b',       # 2023-2024
        r'(\d{4})年',
    ]
    for pat in year_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            ctx["year"] = m.group(1)
            break

    # 地区检测
    region_map = {
        "全球": "global", "global": "global", "worldwide": "global",
        "美国": "US", "us": "US", "united states": "US", "u.s.": "US",
        "中国": "China", "china": "China",
        "欧洲": "Europe", "europe": "Europe", "eu": "Europe",
        "亚太": "APAC", "apac": "APAC", "asia pacific": "APAC",
        "北美": "North America", "north america": "North America",
        "日本": "Japan", "japan": "Japan",
        "东南亚": "SEA", "southeast asia": "SEA",
        "印度": "India", "india": "India",
    }
    for cn, en in region_map.items():
        if cn in text_lower:
            ctx["region"] = en
            break

    # 细分赛道检测
    segment_indicators = [
        "ai", "saas", "fintech", "healthtech", "edtech",
        "enterprise", "consumer", "developer", "b2b", "b2c",
        "cloud", "infrastructure", "platform", "marketplace",
        "generative", "open source", "api",
    ]
    found_segments = []
    for si in segment_indicators:
        if si in text_lower:
            found_segments.append(si)
    if found_segments:
        ctx["segment"] = ", ".join(found_segments[:3])

    return ctx


def check_market_context(field_value: str) -> tuple[bool, list[str]]:
    """检查市场字段是否满足口径要求。

    Returns:
        (is_complete, missing_parts) — 是否完整，缺失哪些口径
    """
    ctx = _extract_context(field_value)
    missing = [k for k in REQUIRED_CONTEXT if k not in ctx]
    return len(missing) == 0, missing


def resolve_market_field(field_key: str, field_value: str,
                         evidence_ids: list[int] = None,
                         manifest_entry: dict = None) -> dict:
    """解析市场字段状态。

    Returns:
        {
            "field_key": str,
            "field_value": str,
            "status": "confirmed"|"llm_extracted"|"proxy"|"manual_needed",
            "context": {...},
            "missing_context": [...],
            "reason": str,
        }
    """
    evidence_ids = evidence_ids or []
    manifest_entry = manifest_entry or {}

    result = {
        "field_key": field_key,
        "field_value": field_value,
        "status": "llm_extracted",
        "context": {},
        "missing_context": [],
        "reason": "",
    }

    if not field_value or str(field_value).strip() in ("", "暂缺", "N/A"):
        result["status"] = "unavailable"
        result["reason"] = "no value"
        return result

    # 1. 口径检查
    is_complete, missing = check_market_context(field_value)
    result["context"] = _extract_context(field_value)
    result["missing_context"] = missing

    if not is_complete:
        result["status"] = "manual_needed"
        result["reason"] = f"missing context: {', '.join(missing)}"
        return result

    # 2. 证据检查
    if not evidence_ids:
        result["status"] = "llm_extracted"
        result["reason"] = "no evidence bound — 口径完整但无来源证据"
        return result

    # 3. 有口径有证据 → confirmed
    result["status"] = "confirmed"
    result["reason"] = f"market field with complete context ({len(evidence_ids)} evidence spans)"
    return result


def get_market_summary(db_path: str, company_key: str) -> dict:
    """获取公司的市场数据摘要（从 metrics 表聚合）。"""
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """SELECT metric_key, metric_value, metric_text, unit, period, region, segment, status
               FROM metrics WHERE company_key=? AND metric_key IN ('market_size','market_cagr','tam','sam','som')
               ORDER BY metric_key""",
            (company_key,),
        ).fetchall()

        conn.close()

        summary = {}
        for r in rows:
            mk = r["metric_key"]
            summary[mk] = {
                "value": r["metric_value"],
                "text": r["metric_text"],
                "unit": r["unit"],
                "period": r["period"],
                "region": r["region"],
                "segment": r["segment"],
                "status": r["status"],
            }
        return summary
    except Exception:
        return {}


def format_market_metric(metric_key: str, value: float, unit: str = "",
                         period: str = "", region: str = "",
                         segment: str = "") -> str:
    """格式化市场指标为标准展示文本。

    示例输出:
        "$12.5B (2024, global, enterprise SaaS)"
    """
    parts = []

    # 数值
    if value >= 1_000_000_000:
        parts.append(f"${value / 1_000_000_000:.1f}B")
    elif value >= 1_000_000:
        parts.append(f"${value / 1_000_000:.0f}M")
    elif value > 0:
        parts.append(f"${value:,.0f}")
    else:
        parts.append(f"{value}")

    # 单位
    if unit and unit != "USD":
        parts[-1] = f"{parts[-1]} {unit}"

    # 口径: (period, region, segment)
    context_parts = []
    if period:
        context_parts.append(period)
    if region and region != "global":
        context_parts.append(region)
    if segment:
        context_parts.append(segment)

    if context_parts:
        parts.append(f"({', '.join(context_parts)})")

    return " ".join(parts)
