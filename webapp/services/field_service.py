"""字段服务 — 字段拆分、版本比较、定稿"""
from __future__ import annotations
import json
from typing import Optional

from repositories.field_repo import (
    insert_research_fields_batch, get_research_fields,
    upsert_final_field, get_final_fields, get_final_field_value,
    confirm_all_fields, set_field_status,
)


def load_field_contract() -> dict:
    """加载 fields.json 契约"""
    from pathlib import Path
    contract_path = Path(__file__).resolve().parent.parent.parent / "contracts" / "fields.json"
    with open(contract_path) as f:
        return json.load(f)


def split_research_to_fields(research_row: dict, version: str = "standard") -> list[dict]:
    """将 research 宽表一行拆分为 research_fields 列表（按 fields.json 契约）"""
    contract = load_field_contract()
    result = []
    company_name = research_row.get("company_name", "")
    for group in contract.get("groups", []):
        for field_def in group.get("fields", []):
            key = field_def["field_key"]
            value = research_row.get(key)
            if value is None:
                continue
            result.append({
                "company_name": company_name,
                "version": version,
                "field_key": key,
                "field_label": field_def.get("field_label", key),
                "field_value": str(value) if not isinstance(value, str) else value,
                "source_type": "llm_extract",
                "confidence": "medium",
            })
    return result


def get_field_versions(db_path_research: str, company_name: str) -> dict[str, dict[str, str]]:
    """返回 {field_key: {standard: "...", business: "...", spread: "..."}}"""
    versions = {}
    for ver in ("standard", "business", "spread"):
        fields = get_research_fields(db_path_research, company_name, ver)
        for f in fields:
            versions.setdefault(f["field_key"], {})[ver] = f.get("field_value", "")
    return versions


def get_fields_with_versions(db_path_research: str, db_path_final: str,
                             company_name: str) -> list[dict]:
    """返回完整的字段列表（含三版本 + 定稿状态）"""
    contract = load_field_contract()
    versioned = get_field_versions(db_path_research, company_name)
    final_fields = {f["field_key"]: f for f in get_final_fields(db_path_final, company_name)}

    result = []
    for group in contract.get("groups", []):
        group_fields = []
        for field_def in group.get("fields", []):
            key = field_def["field_key"]
            vers = versioned.get(key, {})
            final = final_fields.get(key, {})
            group_fields.append({
                "field_key": key,
                "field_label": field_def["field_label"],
                "type": field_def["type"],
                "group_key": group["group_key"],
                "versions": vers,
                "final_value": final.get("final_value", vers.get("standard", "")),
                "status": final.get("status", "draft"),
            })
        if group_fields:
            result.append({
                "group_key": group["group_key"],
                "group_label": group["group_label"],
                "fields": group_fields,
            })

    return result


def finalize_field(db_path_final: str, company_name: str, field_key: str,
                   final_value: str, status: str = "confirmed") -> bool:
    """定稿单个字段（写入 final_fields）"""
    contract = load_field_contract()
    label = field_key
    for group in contract.get("groups", []):
        for f in group.get("fields", []):
            if f["field_key"] == field_key:
                label = f["field_label"]
                break
    upsert_final_field(db_path_final, company_name, field_key, final_value,
                       field_label=label, status=status)
    return True


def batch_finalize(db_path_final: str, company_name: str,
                   field_values: dict[str, str]) -> int:
    """批量定稿字段"""
    count = 0
    for key, value in field_values.items():
        finalize_field(db_path_final, company_name, key, value)
        count += 1
    return count
