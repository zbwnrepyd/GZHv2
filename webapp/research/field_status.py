"""字段状态标记 — 根据 field_manifest.yaml 给 research_fields 打 resolution_status"""
from __future__ import annotations
import os
from pathlib import Path

# 加载 manifest（模块级缓存）
_manifest: dict = {}
_manifest_loaded = False


def _load_manifest() -> dict:
    global _manifest, _manifest_loaded
    if _manifest_loaded:
        return _manifest

    try:
        import yaml
        path = Path(__file__).resolve().parent.parent.parent / "references" / "field_manifest.yaml"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            _manifest = raw.get("fields", {}) if isinstance(raw, dict) else {}
    except Exception:
        _manifest = {}
    _manifest_loaded = True
    return _manifest


# 视为"暂缺"的值
MISSING_VALUES = {"", "暂缺", "unknown", "Unknown", "N/A", "n/a", "none", "None", "NULL"}


def is_missing(value: str | None) -> bool:
    if value is None:
        return True
    return str(value).strip() in MISSING_VALUES


def mark_field(field_key: str, field_value: str | None) -> dict:
    """返回单个字段的分辨率标签"""
    manifest = _load_manifest()
    entry = manifest.get(field_key, manifest.get("_default", {}))
    category = entry.get("category", "A")
    resolution_type = entry.get("resolution_type", "llm_extract")
    if_missing = entry.get("if_missing", "unavailable")

    val = str(field_value).strip() if field_value else ""

    if not is_missing(field_value):
        # 有值：根据 resolution_type 标记
        status_map = {
            "official_fact": "confirmed",
            "enum_extraction": "confirmed",
            "private_metric": "confirmed",  # 有值就确认（来源可能是财报/访谈）
            "derived": "derived",
            "market_model": "proxy",
            "b2b_remap": "confirmed",
            "llm_extract": "llm_extracted",
        }
        status = status_map.get(resolution_type, "llm_extracted")
        return {
            "resolution_status": status,
            "unavailable_reason": None,
            "resolution_method": resolution_type,
        }

    # 无值：根据 if_missing 标记
    if if_missing == "unavailable":
        reason = _unavailable_reason(field_key, category)
        return {
            "resolution_status": "unavailable",
            "unavailable_reason": reason,
            "resolution_method": "marked_unavailable",
        }
    elif if_missing == "manual_needed":
        return {
            "resolution_status": "manual_needed",
            "unavailable_reason": f"{field_key} 需要人工估算或付费数据源",
            "resolution_method": "marked_unavailable",
        }
    elif if_missing == "not_applicable":
        return {
            "resolution_status": "not_applicable",
            "unavailable_reason": _b2b_unavailable_reason(field_key),
            "resolution_method": "marked_unavailable",
        }
    elif if_missing == "derived":
        return {
            "resolution_status": "derived",
            "unavailable_reason": "输入字段缺失，无法计算",
            "resolution_method": "formula",
        }
    else:
        return {
            "resolution_status": "unavailable",
            "unavailable_reason": f"{field_key} 暂缺",
            "resolution_method": "marked_unavailable",
        }


def _unavailable_reason(field_key: str, category: str) -> str:
    reasons = {
        "D": f"{field_key}: 私有经营指标，公开来源未披露",
        "C": f"{field_key}: 市场估算字段，需要市场报告或人工确认边界",
        "A": f"{field_key}: 公开信息中未找到",
    }
    return reasons.get(category, f"{field_key}: 未找到可靠来源")


def _b2b_unavailable_reason(field_key: str) -> str:
    remap = {
        "active_users": "B2B 企业不适用用户数口径，建议使用 account/logo 数",
        "registered_users": "B2B 企业不适用注册用户口径",
        "paying_users": "B2B 企业应使用 paying_customers",
    }
    return remap.get(field_key, f"{field_key}: B2B 业务模式不适用此字段")


def mark_all_fields(fields: dict[str, str | None]) -> list[dict]:
    """批量标记，返回 [(field_key, status_dict), ...]"""
    results = []
    for key, val in fields.items():
        result = mark_field(key, val)
        results.append({"field_key": key, "field_value": val, **result})
    return results
