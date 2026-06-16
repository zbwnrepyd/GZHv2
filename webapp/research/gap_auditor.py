"""缺口审计 — 检测缺失字段 + 持久化审计结果 + 关联 field_manifest 分类"""
from __future__ import annotations
import json
import sqlite3
from collections import defaultdict


def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def audit_gaps(db_path: str, company_name: str, version: str,
               parsed_data: dict, business_type: str = "",
               data_availability: str = "") -> dict:
    """检测缺口 + 分类 + 持久化。返回审计摘要。"""
    from gap_detector import detect_gaps, CRITICAL_GAPS

    gaps = detect_gaps(parsed_data)

    # 按 field_manifest 分类缺口
    categorized = _categorize_gaps(gaps)

    # 持久化
    _persist_audit(db_path, company_name, version, gaps, categorized,
                   business_type, data_availability)

    # 返回摘要
    summary = {
        "total_gap_intents": len(gaps),
        "total_missing_fields": sum(len(v) for v in gaps.values()),
        "by_category": {cat: len(fields) for cat, fields in categorized.items()},
        "actionable": _actionable_summary(categorized),
    }
    return summary


def _categorize_gaps(gaps: dict[str, list[str]]) -> dict[str, list[str]]:
    """将缺失字段按 manifest 分类归入 A/B/C/D/E"""
    from research.field_status import _load_manifest

    manifest = _load_manifest()
    categorized: dict[str, list[str]] = defaultdict(list)

    for intent, fields in gaps.items():
        for fk in fields:
            entry = manifest.get(fk, {})
            cat = entry.get("category", "A")
            categorized[cat].append(fk)

    return dict(categorized)


def _actionable_summary(categorized: dict[str, list[str]]) -> dict:
    """生成可操作建议"""
    tips = {
        "A": "公开信息中缺失，建议搜索官网/Crunchbase/LinkedIn",
        "B": "依赖字段缺失，公式无法计算",
        "C": "需要市场报告或人工确认边界",
        "D": "私有经营指标，公开来源通常不可得。建议标记 unavailable，不补搜",
        "E": "B2B 不适配字段，建议从字段体系中排除",
    }
    return {cat: {"fields": fields, "tip": tips.get(cat, "")}
            for cat, fields in categorized.items()}


def _persist_audit(db_path: str, company_name: str, version: str,
                   gaps: dict[str, list[str]],
                   categorized: dict[str, list[str]],
                   business_type: str, data_availability: str):
    """将缺口审计结果写入 field_resolution_logs"""
    try:
        conn = _get_db(db_path)
        for intent, fields in gaps.items():
            for fk in fields:
                cat = ""
                for c, flist in categorized.items():
                    if fk in flist:
                        cat = c
                        break
                detail = json.dumps({
                    "gap_intent": intent,
                    "field_category": cat,
                    "business_type": business_type,
                    "data_availability": data_availability,
                }, ensure_ascii=False)
                conn.execute(
                    """INSERT OR IGNORE INTO field_resolution_logs
                       (company_name, version, field_key, resolution_status,
                        resolution_method, evidence_count, detail_json)
                       VALUES (?, ?, ?, 'unavailable', 'gap_audit', 0, ?)""",
                    (company_name, version, fk, detail),
                )
        conn.commit()
        conn.close()
    except Exception:
        pass
