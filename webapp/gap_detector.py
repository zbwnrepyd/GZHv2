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
    "market_size": ["tam", "sam", "som", "market_cagr"],
    "revenue_metrics": ["arr", "mrr", "revenue_metrics"],
    "user_metrics": ["registered_users", "active_users", "paying_users",
                     "growth_metrics"],
    "retention_metrics": ["retention_rate", "churn_rate"],
    "unit_economics": ["cac", "ltv", "ltv_cac_ratio", "gross_margin"],
    "capital_efficiency": ["burn_rate", "runway_months"],
    # v3 新增缺口意图
    "customers": ["customer_names", "customer_selection_reasons", "customer_choice_evidence"],
    "pricing_details": ["pricing_summary", "pricing_tiers", "pricing_strategy"],
    "competitive_position": ["competitors_top3", "competitive_position", "competitive_advantages"],
    "differentiated_opportunity": ["differentiated_opportunity"],
    "company_profile_v3": ["founded_date", "core_business", "core_competency",
                            "funding_rounds", "company_achievements", "industry_positioning"],
    "product_v3": ["product_pain_points", "product_core_features", "product_usage_playbook",
                   "product_tech_stack", "regional_market_focus", "mau", "mau_as_of",
                   "retention_definition"],
    "gtm_v3": ["acquisition_channels"],
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
    "market_size": [
        '"{display_name}" TAM SAM SOM market size CAGR',
        '"{display_name}" total addressable market serviceable obtainable market',
    ],
    "revenue_metrics": [
        '"{display_name}" ARR MRR revenue annual recurring revenue',
        '"{display_name}" revenue run rate financial metrics',
    ],
    "user_metrics": [
        '"{display_name}" registered users active users MAU DAU paying users',
        '"{display_name}" customers users adoption growth metrics',
    ],
    "retention_metrics": [
        '"{display_name}" retention rate churn rate cohort retention',
        '"{display_name}" user retention engagement churn metrics',
    ],
    "unit_economics": [
        '"{display_name}" CAC LTV LTV CAC gross margin payback period',
        '"{display_name}" customer acquisition cost lifetime value unit economics',
    ],
    "capital_efficiency": [
        '"{display_name}" burn rate runway cash runway gross margin',
        '"{display_name}" operating metrics burn runway funding efficiency',
    ],
    "customers": [
        '"{display_name}" customers case study enterprise clients testimonials',
        '"{display_name}" customer success stories client list logos',
    ],
    "pricing_details": [
        "site:{website_host} pricing plans",
        '"{display_name}" pricing tiers detailed breakdown subscription',
    ],
    "competitive_position": [
        '"{display_name}" competitive advantage differentiation market position',
        '"{display_name}" vs competitors comparison analysis alternatives',
    ],
    "differentiated_opportunity": [
        '"{display_name}" market gap opportunity niche blue ocean',
        '"{display_name}" differentiation strategy competitive white space',
    ],
    "company_profile_v3": [
        '"{display_name}" founded date year headquarters location',
        '"{display_name}" core business mission company overview achievements',
    ],
    "product_v3": [
        '"{display_name}" product features tech stack architecture MAU',
        '"{display_name}" product usage pain points core functionality pricing',
    ],
    "gtm_v3": [
        '"{display_name}" acquisition channels marketing SEO social media growth',
        '"{display_name}" go to market distribution channels user acquisition',
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
