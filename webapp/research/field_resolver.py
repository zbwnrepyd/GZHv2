"""字段解析器 — 按字段类型走不同解析路径，输出统一 FieldResult"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FieldResult:
    field_key: str
    value: Optional[str] = None
    resolution_status: str = "unavailable"  # confirmed|derived|proxy|unavailable|manual_needed|not_applicable
    confidence: str = "medium"  # high|medium|low
    source_fields: list[str] = field(default_factory=list)
    formula: str = ""
    assumptions: list[str] = field(default_factory=list)
    unavailable_reason: str = ""
    resolution_method: str = ""


def resolve_field(field_key: str, field_value: str | None,
                  resolved_pool: dict[str, FieldResult],
                  manifest_entry: dict | None = None) -> FieldResult:
    """对单个字段运行解析策略

    Args:
        field_key: 字段名
        field_value: LLM 提取的原始值
        resolved_pool: 已完成解析的字段池（用于公式计算）
        manifest_entry: field_manifest.yaml 中的条目

    Returns:
        FieldResult with resolution_status and metadata
    """
    entry = manifest_entry or {}
    resolution_type = entry.get("resolution_type", "llm_extract")

    # -- 有值时：根据 resolution_type 标记 --
    if not _is_missing(field_value):
        return _resolve_with_value(field_key, str(field_value), resolution_type,
                                   resolved_pool, entry)

    # -- 无值时：按 if_missing 策略处理 --
    if_missing = entry.get("if_missing", "unavailable")

    if resolution_type == "derived":
        return _resolve_derived(field_key, resolved_pool, entry)

    if resolution_type == "market_model":
        return _resolve_market_model(field_key, entry)

    if resolution_type == "private_metric":
        return FieldResult(
            field_key=field_key,
            value=None,
            resolution_status="unavailable",
            confidence="high",
            resolution_method="private_metric_policy",
            unavailable_reason=f"{field_key}: 私有经营指标，公开来源未披露。"
                               f"仅公司财报/投资人材料/创始人访谈/Latka等数据库可确认",
        )

    if resolution_type == "b2b_remap":
        return FieldResult(
            field_key=field_key,
            value=None,
            resolution_status="not_applicable",
            confidence="high",
            resolution_method="b2b_remap",
            unavailable_reason=f"{field_key}: B2B 业务模式不适用用户数口径，"
                               f"建议使用 {entry.get('b2b_replace', 'account/logos 数')}",
        )

    if if_missing == "manual_needed":
        return FieldResult(
            field_key=field_key,
            resolution_status="manual_needed",
            resolution_method="marked_manual",
            unavailable_reason=f"{field_key}: 需要人工估算或付费数据源确认",
        )

    # 默认：标记 unavailable
    return FieldResult(
        field_key=field_key,
        resolution_status="unavailable" if if_missing != "not_applicable" else "not_applicable",
        resolution_method="default_unavailable",
        unavailable_reason=f"{field_key}: 公开信息中未找到可靠来源",
    )


def _resolve_with_value(field_key: str, value: str, resolution_type: str,
                        resolved_pool: dict, entry: dict) -> FieldResult:
    """有值时的状态判定"""
    status_map = {
        "official_fact": "confirmed",
        "enum_extraction": "confirmed",
        "private_metric": "confirmed",  # 有值即确认（来源可能是财报/访谈）
        "derived": "derived",
        "market_model": "proxy",
        "b2b_remap": "confirmed",
        "llm_extract": "llm_extracted",
    }
    status = status_map.get(resolution_type, "llm_extracted")
    return FieldResult(
        field_key=field_key,
        value=value,
        resolution_status=status,
        confidence="medium",
        resolution_method=resolution_type,
    )


def _resolve_derived(field_key: str, resolved_pool: dict,
                     entry: dict) -> FieldResult:
    """公式字段：检查所有输入是否 confirmed，是则标记 derived，否则 unavailable"""
    required = entry.get("required_inputs", [])
    formula = entry.get("formula", "")

    if not required:
        return FieldResult(
            field_key=field_key, resolution_status="derived",
            resolution_method="formula", formula=formula,
            unavailable_reason="缺少公式定义",
        )

    # 检查输入字段
    for inp in required:
        inp_result = resolved_pool.get(inp)
        if not inp_result or inp_result.value is None:
            return FieldResult(
                field_key=field_key,
                resolution_status="unavailable",
                resolution_method="blocked_formula",
                formula=formula,
                source_fields=required,
                unavailable_reason=f"依赖字段 {inp} 缺失，公式无法计算",
            )

    return FieldResult(
        field_key=field_key,
        resolution_status="derived",
        resolution_method="formula",
        formula=formula,
        source_fields=required,
    )


def _resolve_market_model(field_key: str, entry: dict) -> FieldResult:
    """市场估算：允许 proxy，但需要标注"""
    allow_proxy = entry.get("allow_proxy", False)
    if allow_proxy:
        return FieldResult(
            field_key=field_key,
            resolution_status="proxy",
            resolution_method="market_model",
            unavailable_reason=f"{field_key}: 公开市场数据可得，但需要确认市场边界",
        )
    return FieldResult(
        field_key=field_key,
        resolution_status="manual_needed",
        resolution_method="market_model",
        unavailable_reason=f"{field_key}: 需要市场报告或分析师数据确认边界",
    )


def resolve_all(field_map: dict[str, str | None],
                manifest: dict | None = None) -> dict[str, FieldResult]:
    """批量解析所有字段，按依赖顺序处理"""
    if manifest is None:
        from research.field_status import _load_manifest
        manifest = _load_manifest()

    # 第一遍：先解析非公式字段，构建 resolved_pool
    resolved_pool: dict[str, FieldResult] = {}
    deferred: list[tuple[str, str | None, dict]] = []

    for fk, fv in field_map.items():
        entry = manifest.get(fk, manifest.get("_default", {}))
        if entry.get("resolution_type") == "derived":
            deferred.append((fk, fv, entry))
        else:
            resolved_pool[fk] = resolve_field(fk, fv, resolved_pool, entry)

    # 第二遍：解析公式字段（此时 resolved_pool 已包含所有非公式字段）
    for fk, fv, entry in deferred:
        resolved_pool[fk] = resolve_field(fk, fv, resolved_pool, entry)

    return resolved_pool


MISSING_VALUES = {"", "暂缺", "unknown", "Unknown", "N/A", "n/a", "none", "None", "NULL"}


def _is_missing(value) -> bool:
    if value is None:
        return True
    return str(value).strip() in MISSING_VALUES
