"""排版服务 — 排版实例的保存和合并"""
from __future__ import annotations
import json

from repositories.layout_repo import (
    get_layout, get_all_layouts, save_layout, reset_layout,
)
from repositories.template_repo import get_template


def get_effective_layout(db_path_template: str, db_path_composition: str,
                         company_name: str, card_id: str) -> dict:
    """返回合并后的有效排版（模板默认 + 用户微调）"""
    instance = get_layout(db_path_composition, company_name, card_id)
    template_id = instance.get("template_id") if instance else None

    # 从 card_compositions 读取 template_id
    if not template_id:
        from repositories.card_config_repo import get_card
        card = get_card(db_path_composition, company_name, card_id)
        template_id = card.get("template_id") if card else None

    template = get_template(db_path_template, template_id) if template_id else None
    template_json = template.get("template_json", {}) if template else {}

    # 合并：模板打底，layout overrides 覆盖
    result = dict(template_json)
    result["template_id"] = template_id

    if instance:
        overrides = instance.get("layout_json", {}).get("overrides", {})
        regions = result.get("regions", [])
        for i, region in enumerate(regions):
            rid = region.get("id", "")
            if rid in overrides:
                regions[i] = _deep_merge(region, overrides[rid])
        result["regions"] = regions

    return result


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def update_layout_override(db_path_composition: str, company_name: str,
                           card_id: str, region_id: str,
                           overrides: dict,
                           template_id: str = "") -> int:
    """更新单个区域的排版覆盖"""
    existing = get_layout(db_path_composition, company_name, card_id)
    layout_json = existing.get("layout_json", {}) if existing else {"template_id": template_id, "overrides": {}}
    layout_json.setdefault("overrides", {})
    layout_json["template_id"] = template_id or layout_json.get("template_id", "")

    # deep merge the override for this region
    current = layout_json["overrides"].get(region_id, {})
    layout_json["overrides"][region_id] = _deep_merge(current, overrides)

    return save_layout(db_path_composition, company_name, card_id,
                       layout_json, template_id=layout_json.get("template_id", ""))
