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

FIELD_DEFAULTS = {
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


def defensibility(row: dict) -> float:
    data = normalize_fields(row)
    d1 = AI_MODEL_MAP[data["ai_model_dependency"]]
    d2 = WORKFLOW_MAP[data["workflow_integration_level"]]
    d3 = FLYWHEEL_MAP[data["data_flywheel"]]
    d4 = DATA_ASSET_MAP[data["proprietary_data_asset"]]
    return round(0.35 * d1 + 0.30 * d2 + 0.20 * d3 + 0.15 * d4, 2)


def incumbent_attention(row: dict) -> float:
    data = normalize_fields(row)
    i1 = INCUMBENT_MAP[data["incumbent_direct_competitor"]]
    i2 = CUSTOMER_MAP[data["customer_segment_type"]]
    i3 = FUNDING_MAP[data["funding_stage"]]
    return round(0.50 * i1 + 0.30 * i2 + 0.20 * i3, 2)


def value_capture(row: dict) -> float:
    data = normalize_fields(row)
    v1 = PRICING_MAP[data["pricing_model"]]
    v2 = INFERENCE_MAP[data["inference_cost_exposure"]]
    v3 = CUSTOMER_MAP[data["customer_segment_type"]]
    v4 = AI_MODEL_MAP[data["ai_model_dependency"]]
    return round(0.35 * v1 + 0.30 * v2 + 0.20 * v3 + 0.15 * v4, 2)


def compute_scores(row: dict) -> dict:
    data = normalize_fields(row)
    return {
        "funding_stage_score": FUNDING_MAP[data["funding_stage"]],
        "score_defensibility": defensibility(data),
        "score_incumbent_attention": incumbent_attention(data),
        "score_value_capture": value_capture(data),
    }
