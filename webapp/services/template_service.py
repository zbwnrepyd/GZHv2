"""模板服务 — 模板管理、校验"""
from __future__ import annotations
import json
from pathlib import Path

from repositories.template_repo import (
    get_all_templates, get_template, create_template,
    update_template, delete_template, duplicate_template,
)


VALID_REGION_TYPES = {"text", "image", "shape", "chart", "logo", "background"}
VALID_ROLES = {"title", "subtitle", "body", "caption", "label", "quote",
               "logo", "hero_image", "chart", "background_image", "decoration"}


def validate_template_json(template_json: dict) -> list[str]:
    """校验 template JSON，返回错误列表（空=合法）"""
    errors = []

    canvas = template_json.get("canvas", {})
    if not canvas.get("width") or not canvas.get("height"):
        errors.append("canvas.width 和 canvas.height 为必填")

    regions = template_json.get("regions", [])
    if not isinstance(regions, list):
        errors.append("regions 必须是数组")
        return errors

    seen_ids = set()
    for i, region in enumerate(regions):
        rid = region.get("id")
        if not rid:
            errors.append(f"regions[{i}] 缺少 id")
        elif rid in seen_ids:
            errors.append(f"regions[{i}] id={rid!r} 重复")
        else:
            seen_ids.add(rid)

        rtype = region.get("type", "")
        if rtype not in VALID_REGION_TYPES:
            errors.append(f"regions[{i}] type={rtype!r} 不在允许值: {VALID_REGION_TYPES}")

        role = region.get("role", "")
        if role and role not in VALID_ROLES:
            errors.append(f"regions[{i}] role={role!r} 不在允许值: {VALID_ROLES}")

        for coord in ("x", "y", "w", "h"):
            if not isinstance(region.get(coord), (int, float)):
                errors.append(f"regions[{i}] {coord} 必须是数字")

    return errors


def list_templates(db_path: str) -> list[dict]:
    return get_all_templates(db_path)


def save_template(db_path: str, template_id: str, template_name: str,
                  template_json: dict, **kwargs) -> tuple[bool, list[str]]:
    """保存模板，返回 (成功, 错误列表)"""
    errors = validate_template_json(template_json)
    if errors:
        return False, errors
    canvas = template_json.get("canvas", {})
    bg = template_json.get("background", {})
    create_template(
        db_path, template_id, template_name,
        template_json=template_json,
        canvas_width=kwargs.get("canvas_width", canvas.get("width", 900)),
        canvas_height=kwargs.get("canvas_height", canvas.get("height", 1200)),
        background_type=kwargs.get("background_type", bg.get("type", "color")),
        background_value=kwargs.get("background_value", bg.get("value", "#FFFFFF")),
        is_builtin=kwargs.get("is_builtin", False),
    )
    return True, []
