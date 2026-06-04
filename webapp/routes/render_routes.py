"""渲染数据 API — /api/render-data/...
返回卡片渲染所需的完整数据：字段值 + 图片 URL + 模板 + 排版实例
"""
from __future__ import annotations
from flask import Blueprint, request, jsonify
from config import config
from repositories.card_config_repo import get_enabled_cards, get_card_items
from repositories.field_repo import get_final_field_value, get_research_field_value
from repositories.template_repo import get_template
from repositories.layout_repo import get_layout
from asset_store import ensure_assets_rows, get_asset
from services.card_config_service import create_default_cards_for_company


def _enabled_cards_or_defaults(company: str) -> list[dict]:
    cards = get_enabled_cards(config.DB_PATH_COMPOSITION, company)
    if cards:
        return cards
    create_default_cards_for_company(config.DB_PATH_COMPOSITION, company)
    return get_enabled_cards(config.DB_PATH_COMPOSITION, company)


def _media_url(company: str, media_key: str) -> str:
    ensure_assets_rows(config.DB_PATH_ASSETS, company)
    asset = get_asset(config.DB_PATH_ASSETS, company, media_key) or {}
    return asset.get("local_path") or ""


def register(bp: Blueprint):
    """将路由注册到 Blueprint"""

    @bp.route("/render-data/<company>")
    def get_render_data(company: str):
        """返回某公司全部启用卡片的渲染数据"""
        try:
            cards = _enabled_cards_or_defaults(company)
            result_cards = []
            for card in cards:
                card_id = card["card_id"]
                items = get_card_items(config.DB_PATH_COMPOSITION, company, card_id)

                # 解析每个 item 的值
                resolved_items = []
                for item in items:
                    resolved = dict(item)
                    if item["item_type"] == "field":
                        # 优先 final_fields，fallback research_fields
                        value = (
                            get_final_field_value(config.DB_PATH_FINAL, company,
                                                  item["item_key"])
                            or get_research_field_value(config.DB_PATH_RESEARCH,
                                                        company, item["item_key"])
                            or ""
                        )
                        resolved["value"] = value
                    elif item["item_type"] == "media":
                        resolved["url"] = _media_url(company, item["item_key"])
                        resolved["media_label"] = item.get("item_label", "")
                    resolved_items.append(resolved)

                # 模板
                template_id = card.get("template_id")
                template = get_template(config.DB_PATH_TEMPLATE, template_id) if template_id else None

                # 排版实例
                layout = get_layout(config.DB_PATH_TEMPLATE, company, card_id)

                result_cards.append({
                    "card_id": card_id,
                    "card_index": card["card_index"],
                    "card_title": card["card_title"],
                    "enabled": bool(card["enabled"]),
                    "template_id": template_id,
                    "items": resolved_items,
                    "template": template.get("template_json") if template else None,
                    "layout": layout.get("layout_json") if layout else None,
                })

            return jsonify({
                "company_name": company,
                "cards": result_cards,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/render-data/<company>/<card_id>")
    def get_single_render_data(company: str, card_id: str):
        """返回单张卡片的渲染数据"""
        try:
            from repositories.card_config_repo import get_card
            card = get_card(config.DB_PATH_COMPOSITION, company, card_id)
            if not card:
                return jsonify({"error": "卡片不存在"}), 404

            items = get_card_items(config.DB_PATH_COMPOSITION, company, card_id)
            resolved_items = []
            for item in items:
                resolved = dict(item)
                if item["item_type"] == "field":
                    value = (
                        get_final_field_value(config.DB_PATH_FINAL, company,
                                              item["item_key"])
                        or get_research_field_value(config.DB_PATH_RESEARCH,
                                                    company, item["item_key"])
                        or ""
                    )
                    resolved["value"] = value
                elif item["item_type"] == "media":
                    resolved["url"] = _media_url(company, item["item_key"])
                resolved_items.append(resolved)

            template = get_template(config.DB_PATH_TEMPLATE, card.get("template_id")) if card.get("template_id") else None
            layout = get_layout(config.DB_PATH_TEMPLATE, company, card_id)

            return jsonify({
                "card_id": card_id,
                "card_index": card["card_index"],
                "card_title": card["card_title"],
                "enabled": bool(card["enabled"]),
                "template_id": card.get("template_id"),
                "items": resolved_items,
                "template": template.get("template_json") if template else None,
                "layout": layout.get("layout_json") if layout else None,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
