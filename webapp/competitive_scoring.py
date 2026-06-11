from __future__ import annotations

import re


AI_MODEL_MAP = {
    "proprietary_model": 10,
    "fine_tuned": 7,
    "multi_model": 5,
    "openai_only": 2,
    "no_ai_core": 0,
}

WORKFLOW_MAP = {
    "system_of_record": 10,
    "workflow_embedded": 7,
    "plugin_addon": 4,
    "standalone_tool": 1,
}

FLYWHEEL_MAP = {
    "yes": 10,
    "partial": 5,
    "no": 0,
}

DATA_ASSET_MAP = {
    "yes_core": 10,
    "yes_supplementary": 5,
    "no": 0,
}

INCUMBENT_MAP = {
    "openai": 10,
    "google": 10,
    "multiple": 9,
    "microsoft": 8,
    "other": 5,
    "none": 1,
}

CUSTOMER_MAP = {
    "b2b_enterprise": 9,
    "developer_api": 7,
    "b2b2c": 6,
    "b2b_smb": 5,
    "b2c": 3,
}

FUNDING_MAP = {
    "series_c_plus": 9,
    "series_b": 7,
    "series_a": 5,
    "seed": 3,
    "pre_seed": 1,
}

PRICING_MAP = {
    "outcome_based": 10,
    "enterprise_contract": 8,
    "subscription": 6,
    "usage_based": 4,
    "freemium": 2,
    "free": 0,
}

INFERENCE_MAP = {
    "none": 10,
    "low": 7,
    "medium": 4,
    "high": 1,
}

STACK_LAYER_MAP = {
    "infrastructure": 1,
    "foundation_model": 2,
    "middleware": 3,
    "vertical_app": 4,
    "distribution": 5,
}

# ═══════════════════════════════════════════════════════════════
# v2 新字段映射表（评分体系改造）
# ═══════════════════════════════════════════════════════════════

# 护城河子项
INCUMBENT_OVERLAP_MAP = {
    "none": 1,
    "adjacent": 4,
    "partial_overlap": 7,
    "direct_overlap": 10,
}

WORKFLOW_LOCK_IN_MAP = {
    "system_of_record": 10,
    "workflow_embedded": 7,
    "plugin_addon": 4,
    "standalone_tool": 1,
}

DATA_LOCK_IN_MAP = {
    "strong": 10,
    "moderate": 5,
    "weak": 0,
}

TECHNICAL_UNIQUENESS_MAP = {
    "strong": 10,
    "moderate": 5,
    "weak": 0,
}

DISTRIBUTION_LOCK_MAP = {
    "strong": 10,
    "moderate": 5,
    "weak": 0,
}

BRAND_COMMUNITY_MAP = {
    "strong": 10,
    "moderate": 5,
    "weak": 0,
}

# 巨头关注子项
MARKET_SIZE_MAP = {
    "large": 10,
    "medium": 6,
    "small": 3,
}

STRATEGIC_DEPENDENCY_MAP = {
    "high": 10,
    "medium": 6,
    "low": 3,
}

USER_VISIBILITY_MAP = {
    "high": 10,
    "medium": 6,
    "low": 3,
}

# 价值捕获子项
PRICING_POWER_MAP = {
    "outcome_based": 10,
    "enterprise_contract": 8,
    "subscription": 6,
    "usage_based": 4,
    "freemium": 2,
    "free": 0,
}

GROSS_MARGIN_MAP = {
    "high": 10,
    "medium": 6,
    "low": 3,
}

CUSTOMER_BUDGET_MAP = {
    "b2b_enterprise": 9,
    "developer_api": 7,
    "b2b2c": 6,
    "b2b_smb": 5,
    "b2c": 3,
}

FIELD_DEFAULTS = {
    # 旧字段默认值
    "ai_model_dependency": "no_ai_core",
    "workflow_integration_level": "standalone_tool",
    "data_flywheel": "no",
    "proprietary_data_asset": "no",
    "incumbent_direct_competitor": "none",
    "customer_segment_type": "b2c",
    "funding_stage": "pre_seed",
    "pricing_model": "free",
    "inference_cost_exposure": "high",
    "stack_layer": "vertical_app",
    # v2 新字段默认值
    "incumbent_overlap": "none",
    "workflow_lock_in": "standalone_tool",
    "data_lock_in": "weak",
    "technical_uniqueness": "weak",
    "distribution_lock": "weak",
    "brand_or_community": "weak",
    "market_size": "small",
    "strategic_dependency": "low",
    "user_visibility": "low",
    "pricing_power": "free",
    "gross_margin": "low",
    "customer_budget_level": "b2c",
}


def enum_value(row: dict, field: str, mapping: dict[str, int | float]) -> str:
    value = str(row.get(field) or "").strip()
    if value in mapping:
        return value
    return FIELD_DEFAULTS[field]


# 中文融资轮次 → 枚举映射（优先匹配，避免英文正则误判）
FUNDING_CN_MAP = [
    ("D轮", "series_c_plus"), ("C轮", "series_c_plus"),
    ("B轮", "series_b"), ("B+轮", "series_b"),
    ("A轮", "series_a"), ("A+轮", "series_a"), ("Pre-A", "seed"),
    ("种子轮", "seed"), ("天使轮", "seed"),
    ("战略融资", "series_a"),  # 兜底：战略融资通常不低于A轮
    ("自筹", "pre_seed"), ("未融资", "pre_seed"), ("未接受外部", "pre_seed"),
]


def infer_funding_stage(funding_info: str) -> str:
    text = str(funding_info or "")
    text_lower = text.lower()
    compact = re.sub(r"[\s_\-]+", "", text_lower)

    # 1. 中文关键词优先（精确匹配，避免被英文正则误判）
    for keyword, stage in FUNDING_CN_MAP:
        if keyword in text:
            return stage

    # 2. 英文轮次匹配
    if (
        re.search(r"series\s*[cdefgh]", text_lower)
        or "seriesc" in compact
        or "seriesd" in compact
    ):
        return "series_c_plus"
    if re.search(r"series\s*b", text_lower) or "seriesb" in compact:
        return "series_b"
    if re.search(r"series\s*a", text_lower) or "seriesa" in compact:
        return "series_a"
    if "preseed" in compact or "pre-seed" in text_lower:
        return "pre_seed"
    if re.search(r"\bseed\b", text_lower):
        return "seed"

    return "pre_seed"


def normalize_fields(row: dict) -> dict:
    normalized = dict(row)
    inferred_stage = infer_funding_stage(normalized.get("funding_info", ""))
    current_stage = str(normalized.get("funding_stage") or "").strip()
    if (
        not current_stage
        or current_stage not in FUNDING_MAP
        or FUNDING_MAP[inferred_stage] > FUNDING_MAP[current_stage]
    ):
        normalized["funding_stage"] = inferred_stage

    for field, mapping in [
        ("ai_model_dependency", AI_MODEL_MAP),
        ("workflow_integration_level", WORKFLOW_MAP),
        ("data_flywheel", FLYWHEEL_MAP),
        ("proprietary_data_asset", DATA_ASSET_MAP),
        ("incumbent_direct_competitor", INCUMBENT_MAP),
        ("customer_segment_type", CUSTOMER_MAP),
        ("funding_stage", FUNDING_MAP),
        ("pricing_model", PRICING_MAP),
        ("inference_cost_exposure", INFERENCE_MAP),
        ("stack_layer", STACK_LAYER_MAP),
    ]:
        normalized[field] = enum_value(normalized, field, mapping)
    return normalized


# ═══════════════════════════════════════════════════════════════
# 旧→新字段映射（向后兼容）
# ═══════════════════════════════════════════════════════════════

def _has_new_fields(row: dict) -> bool:
    """检查 row 中是否包含 v2 新评分字段。"""
    return (
        row.get("incumbent_overlap") is not None
        or row.get("workflow_lock_in") is not None
        or row.get("pricing_power") is not None
    )


def _resolve_data_lock_in(row: dict) -> int:
    """解析 data_lock_in 分数，优先新字段，回退到旧字段映射。"""
    val = row.get("data_lock_in")
    if val and str(val).strip() in DATA_LOCK_IN_MAP:
        return DATA_LOCK_IN_MAP[str(val).strip()]
    # fallback: 从旧字段推算
    d1 = DATA_ASSET_MAP.get(str(row.get("proprietary_data_asset") or "").strip(), 0)
    d2 = FLYWHEEL_MAP.get(str(row.get("data_flywheel") or "").strip(), 0)
    return int(round(0.6 * d1 + 0.4 * d2))


def _resolve_workflow_lock_in(row: dict) -> int:
    val = row.get("workflow_lock_in")
    if val and str(val).strip() in WORKFLOW_LOCK_IN_MAP:
        return WORKFLOW_LOCK_IN_MAP[str(val).strip()]
    return WORKFLOW_MAP.get(
        str(row.get("workflow_integration_level") or "").strip(), 1
    )


def _resolve_technical_uniqueness(row: dict) -> int:
    val = row.get("technical_uniqueness")
    if val and str(val).strip() in TECHNICAL_UNIQUENESS_MAP:
        return TECHNICAL_UNIQUENESS_MAP[str(val).strip()]
    return AI_MODEL_MAP.get(
        str(row.get("ai_model_dependency") or "").strip(), 0
    )


def _resolve_distribution_lock(row: dict) -> int:
    val = row.get("distribution_lock")
    if val and str(val).strip() in DISTRIBUTION_LOCK_MAP:
        return DISTRIBUTION_LOCK_MAP[str(val).strip()]
    return 5  # 默认中等


def _resolve_brand_community(row: dict) -> int:
    val = row.get("brand_or_community")
    if val and str(val).strip() in BRAND_COMMUNITY_MAP:
        return BRAND_COMMUNITY_MAP[str(val).strip()]
    return 5  # 默认中等


def _resolve_incumbent_overlap(row: dict) -> int:
    val = row.get("incumbent_overlap")
    if val and str(val).strip() in INCUMBENT_OVERLAP_MAP:
        return INCUMBENT_OVERLAP_MAP[str(val).strip()]
    return INCUMBENT_MAP.get(
        str(row.get("incumbent_direct_competitor") or "").strip(), 1
    )


def _resolve_market_size(row: dict) -> int:
    val = row.get("market_size")
    if val and str(val).strip() in MARKET_SIZE_MAP:
        return MARKET_SIZE_MAP[str(val).strip()]
    # fallback: 从 customer_segment_type 粗略推断
    cs = str(row.get("customer_segment_type") or "").strip()
    if cs == "b2b_enterprise":
        return 10
    elif cs in ("b2b_smb", "b2b2c"):
        return 6
    return 3


def _resolve_strategic_dependency(row: dict) -> int:
    val = row.get("strategic_dependency")
    if val and str(val).strip() in STRATEGIC_DEPENDENCY_MAP:
        return STRATEGIC_DEPENDENCY_MAP[str(val).strip()]
    # fallback: 从 ai_model_dependency 推测
    ai = str(row.get("ai_model_dependency") or "").strip()
    if ai in ("openai_only",):
        return 10
    elif ai in ("multi_model",):
        return 6
    return 3


def _resolve_user_visibility(row: dict) -> int:
    val = row.get("user_visibility")
    if val and str(val).strip() in USER_VISIBILITY_MAP:
        return USER_VISIBILITY_MAP[str(val).strip()]
    # fallback: 从 customer_segment_type 推断
    cs = str(row.get("customer_segment_type") or "").strip()
    if cs in ("b2c", "b2b2c"):
        return 10
    elif cs == "b2b_smb":
        return 6
    return 3


def _resolve_pricing_power(row: dict) -> int:
    val = row.get("pricing_power")
    if val and str(val).strip() in PRICING_POWER_MAP:
        return PRICING_POWER_MAP[str(val).strip()]
    return PRICING_MAP.get(
        str(row.get("pricing_model") or "").strip(), 0
    )


def _resolve_gross_margin(row: dict) -> int:
    val = row.get("gross_margin")
    if val and str(val).strip() in GROSS_MARGIN_MAP:
        return GROSS_MARGIN_MAP[str(val).strip()]
    # fallback: 从 inference_cost_exposure 逆映射（推理成本低 → 毛利高）
    infer = str(row.get("inference_cost_exposure") or "").strip()
    if infer == "none":
        return 10
    elif infer == "low":
        return 6
    elif infer == "medium":
        return 4
    return 1


def _resolve_customer_budget_level(row: dict) -> int:
    val = row.get("customer_budget_level")
    if val and str(val).strip() in CUSTOMER_BUDGET_MAP:
        return CUSTOMER_BUDGET_MAP[str(val).strip()]
    return CUSTOMER_MAP.get(
        str(row.get("customer_segment_type") or "").strip(), 3
    )


# ═══════════════════════════════════════════════════════════════
# 核心评分公式（v2 改造版）
# ═══════════════════════════════════════════════════════════════

def defensibility(row: dict) -> float:
    """护城河强度 (0–10)

    v2 公式:
      0.30 × data_lock_in + 0.25 × workflow_lock_in + 0.20 × technical_uniqueness
      + 0.15 × distribution_lock + 0.10 × brand_or_community
    """
    data = normalize_fields(row)
    return round(
        0.30 * _resolve_data_lock_in(data)
        + 0.25 * _resolve_workflow_lock_in(data)
        + 0.20 * _resolve_technical_uniqueness(data)
        + 0.15 * _resolve_distribution_lock(data)
        + 0.10 * _resolve_brand_community(data),
        2,
    )


def incumbent_attention(row: dict) -> float:
    """巨头关注度 (0–10)

    v2 公式:
      0.40 × incumbent_overlap + 0.25 × market_size
      + 0.20 × strategic_dependency + 0.15 × user_visibility
    """
    data = normalize_fields(row)
    return round(
        0.40 * _resolve_incumbent_overlap(data)
        + 0.25 * _resolve_market_size(data)
        + 0.20 * _resolve_strategic_dependency(data)
        + 0.15 * _resolve_user_visibility(data),
        2,
    )


def value_capture(row: dict) -> float:
    """价值捕获能力 (0–10)

    v2 公式:
      0.35 × pricing_power + 0.25 × gross_margin
      + 0.25 × workflow_lock_in + 0.15 × customer_budget_level
    """
    data = normalize_fields(row)
    return round(
        0.35 * _resolve_pricing_power(data)
        + 0.25 * _resolve_gross_margin(data)
        + 0.25 * _resolve_workflow_lock_in(data)
        + 0.15 * _resolve_customer_budget_level(data),
        2,
    )


# ═══════════════════════════════════════════════════════════════
# 旧版评分函数（保留，供回退参考）
# ═══════════════════════════════════════════════════════════════

def defensibility_legacy(row: dict) -> float:
    """旧版护城河公式"""
    data = normalize_fields(row)
    d1 = AI_MODEL_MAP[data["ai_model_dependency"]]
    d2 = WORKFLOW_MAP[data["workflow_integration_level"]]
    d3 = FLYWHEEL_MAP[data["data_flywheel"]]
    d4 = DATA_ASSET_MAP[data["proprietary_data_asset"]]
    return round(0.35 * d1 + 0.30 * d2 + 0.20 * d3 + 0.15 * d4, 2)


def incumbent_attention_legacy(row: dict) -> float:
    """旧版巨头关注度公式"""
    data = normalize_fields(row)
    i1 = INCUMBENT_MAP[data["incumbent_direct_competitor"]]
    i2 = CUSTOMER_MAP[data["customer_segment_type"]]
    i3 = FUNDING_MAP[data["funding_stage"]]
    return round(0.50 * i1 + 0.30 * i2 + 0.20 * i3, 2)


def value_capture_legacy(row: dict) -> float:
    """旧版价值捕获公式"""
    data = normalize_fields(row)
    v1 = PRICING_MAP[data["pricing_model"]]
    v2 = INFERENCE_MAP[data["inference_cost_exposure"]]
    v3 = CUSTOMER_MAP[data["customer_segment_type"]]
    v4 = AI_MODEL_MAP[data["ai_model_dependency"]]
    return round(0.35 * v1 + 0.30 * v2 + 0.20 * v3 + 0.15 * v4, 2)


def compute_scores(row: dict) -> dict:
    """计算全部评分，返回 dict。向后兼容：字段名不变，公式升级。"""
    data = normalize_fields(row)
    return {
        "funding_stage_score": FUNDING_MAP[data["funding_stage"]],
        "score_defensibility": defensibility(data),
        "score_incumbent_attention": incumbent_attention(data),
        "score_value_capture": value_capture(data),
    }
