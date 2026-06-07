"""缺口检测 — L0 后检查关键字段缺失，生成定向补采 query。"""
from __future__ import annotations

CRITICAL_GAPS: dict[str, list[str]] = {
    "founders": ["founder_name", "founder_edu", "founder_bg",
                 "founder_achievement"],
    "funding": ["funding_info"],
    "pricing": ["pricing_model", "revenue_model"],
    "competitors": ["competitors"],
    "timeline": ["timeline_events"],
    "product": ["main_product_name", "main_product_def",
                "main_product_achievement"],
    "gtm": ["gtm_strategy", "cold_start", "customer_segment"],
}

GAP_QUERY_TEMPLATES: dict[str, list[str]] = {
    "founders": [
        '"{display_name}" founder LinkedIn education background',
        '"{display_name}" founder interview biography',
    ],
    "funding": [
        '"{display_name}" "{website_host}" funding investors raised',
        '"{display_name}" seed round series valuation',
    ],
    "pricing": [
        "site:{website_host} pricing",
        '"{display_name}" pricing plans subscription',
    ],
    "competitors": [
        '"{display_name}" competitors alternatives vs',
        '"{root_domain}" market map competitors',
    ],
    "timeline": [
        '"{display_name}" launch history timeline founded',
        '"{display_name}" announcement rebrand acquisition milestone',
    ],
    "product": [
        '"{display_name}" product features screenshot demo',
        '"{display_name}" use cases customer review',
    ],
    "gtm": [
        '"{display_name}" go to market growth strategy',
        '"{display_name}" Product Hunt launch users',
    ],
}


def is_missing(value) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return text in ("", "暂缺", "未知", "无可信信息")


def detect_gaps(parsed_data: dict) -> dict[str, list[str]]:
    """返回 {intent: [missing_field_names], ...}，每类至少一半字段缺失。"""
    gaps: dict[str, list[str]] = {}
    for intent, fields in CRITICAL_GAPS.items():
        missing = [f for f in fields if is_missing(parsed_data.get(f))]
        if len(missing) >= max(1, len(fields) // 2):
            gaps[intent] = missing
    return gaps


def build_gap_queries(display_name: str, website_host: str,
                      root_domain: str,
                      gaps: dict[str, list[str]]) -> list[dict]:
    """为缺失意图生成 Tavily 补采 query。"""
    queries: list[dict] = []
    for intent in gaps:
        templates = GAP_QUERY_TEMPLATES.get(intent, [])
        for tmpl in templates[:2]:
            q = tmpl.format(display_name=display_name,
                            website_host=website_host,
                            root_domain=root_domain)
            queries.append({"query": q, "intent": intent})
    return queries
