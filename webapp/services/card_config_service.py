"""卡片编排服务 — 默认卡片创建、字段/图片分配到卡片"""
from __future__ import annotations
import json

from repositories.card_config_repo import (
    create_card, get_cards, get_card, get_enabled_cards,
    update_card, delete_card, reorder_cards,
    add_card_item, get_card_items, update_card_item,
    remove_card_item, clear_card_items, batch_set_card_items,
    get_default_card_configs,
)


def create_default_cards_for_company(db_path: str, company_name: str) -> list[str]:
    """为新公司创建默认 8 张卡片配置，返回 card_id 列表"""
    defaults = get_default_card_configs(db_path)
    if not defaults:
        return []

    card_ids = []
    for cfg in defaults:
        card_id = cfg["card_id"]
        create_card(
            db_path, company_name,
            card_id=card_id,
            card_index=cfg["card_index"],
            card_title=cfg["card_title"],
            template_id=cfg.get("config", {}).get("template_id", ""),
        )
        config = cfg.get("config", {})
        # 添加字段
        for idx, field_key in enumerate(config.get("fields", [])):
            add_card_item(db_path, company_name, card_id,
                         item_type="field", item_key=field_key,
                         sort_order=idx, display_role=_default_role_for_field(field_key))
        # 添加图片
        for idx, media_key in enumerate(config.get("media", [])):
            add_card_item(db_path, company_name, card_id,
                         item_type="media", item_key=media_key,
                         sort_order=idx + 100,
                         display_role=_default_role_for_media(media_key))
        card_ids.append(card_id)

    return card_ids


def _default_role_for_field(field_key: str) -> str:
    if field_key in ("company_name",):
        return "title"
    if field_key in ("company_type",):
        return "subtitle"
    return "body"


def _default_role_for_media(media_key: str) -> str:
    if media_key == "logo":
        return "logo"
    if media_key in ("flywheel", "timeline", "chart_competitive", "chart_ecosystem"):
        return "chart"
    if media_key in ("competitors_logo_strip",):
        return "decoration"
    return "hero_image"


def get_card_composition(db_path: str, company_name: str,
                         card_id: str) -> dict | None:
    """返回单张卡片的完整编排（卡片 + items）"""
    card = get_card(db_path, company_name, card_id)
    if not card:
        return None
    items = get_card_items(db_path, company_name, card_id)
    card["items"] = items
    return card


def get_company_composition(db_path: str, company_name: str) -> dict:
    """返回公司的完整卡片编排"""
    cards = get_cards(db_path, company_name)
    for card in cards:
        card["items"] = get_card_items(db_path, company_name, card["card_id"])
    return {
        "company_name": company_name,
        "cards": cards,
    }


def add_field_to_card(db_path: str, company_name: str, card_id: str,
                      field_key: str, field_label: str = "",
                      display_role: str = "body") -> int:
    items = get_card_items(db_path, company_name, card_id)
    max_order = max((it["sort_order"] for it in items), default=0)
    return add_card_item(db_path, company_name, card_id,
                        item_type="field", item_key=field_key,
                        item_label=field_label,
                        sort_order=max_order + 1,
                        display_role=display_role)


def add_media_to_card(db_path: str, company_name: str, card_id: str,
                      media_key: str, media_label: str = "",
                      display_role: str = "hero_image") -> int:
    items = get_card_items(db_path, company_name, card_id)
    max_order = max((it["sort_order"] for it in items), default=99)
    return add_card_item(db_path, company_name, card_id,
                        item_type="media", item_key=media_key,
                        item_label=media_label,
                        sort_order=max_order + 1,
                        display_role=display_role)
