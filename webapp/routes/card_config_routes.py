"""卡片编排 API — /api/card-config/... """
from __future__ import annotations
from flask import Blueprint, request, jsonify
from config import config
from services.card_config_service import (
    get_company_composition, get_card_composition,
    create_default_cards_for_company,
    add_field_to_card, add_media_to_card,
)
from repositories.card_config_repo import (
    create_card, get_cards, get_card, get_enabled_cards,
    update_card, delete_card, reorder_cards,
    add_card_item, get_card_items, update_card_item,
    remove_card_item, clear_card_items, batch_set_card_items,
)


def register(bp: Blueprint):
    """将路由注册到 Blueprint"""

    # ── 公司卡片编排总览 ──
    @bp.route("/card-config/<company>")
    def get_company_cards(company: str):
        try:
            composition = get_company_composition(config.DB_PATH_COMPOSITION, company)
            # 如果没有卡片，自动创建默认配置
            if not composition["cards"]:
                create_default_cards_for_company(config.DB_PATH_COMPOSITION, company)
                composition = get_company_composition(config.DB_PATH_COMPOSITION, company)
            return jsonify(composition)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── 单张卡片编排 ──
    @bp.route("/card-config/<company>/cards/<card_id>")
    def get_single_card(company: str, card_id: str):
        try:
            card = get_card_composition(config.DB_PATH_COMPOSITION, company, card_id)
            if not card:
                return jsonify({"error": "卡片不存在"}), 404
            return jsonify(card)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── 创建卡片 ──
    @bp.route("/card-config/<company>/cards", methods=["POST"])
    def create_new_card(company: str):
        try:
            data = request.get_json() or {}
            card_id = data.get("card_id", "")
            card_title = data.get("card_title", "")
            card_index = data.get("card_index", 99)
            template_id = data.get("template_id", "")
            if not card_id or not card_title:
                return jsonify({"error": "缺少 card_id 或 card_title"}), 400

            rid = create_card(config.DB_PATH_COMPOSITION, company,
                            card_id=card_id, card_index=int(card_index),
                            card_title=card_title, template_id=template_id)
            card = get_card_composition(config.DB_PATH_COMPOSITION, company, card_id)
            return jsonify({"status": "ok", "id": rid, "card": card})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── 更新卡片 ──
    @bp.route("/card-config/<company>/cards/<card_id>", methods=["PATCH"])
    def update_existing_card(company: str, card_id: str):
        try:
            data = request.get_json() or {}
            ok = update_card(config.DB_PATH_COMPOSITION, company, card_id, **data)
            if not ok:
                return jsonify({"error": "更新失败或卡片不存在"}), 404
            card = get_card_composition(config.DB_PATH_COMPOSITION, company, card_id)
            return jsonify({"status": "ok", "card": card})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── 删除卡片 ──
    @bp.route("/card-config/<company>/cards/<card_id>", methods=["DELETE"])
    def delete_existing_card(company: str, card_id: str):
        try:
            ok = delete_card(config.DB_PATH_COMPOSITION, company, card_id)
            if not ok:
                return jsonify({"error": "删除失败或卡片不存在"}), 404
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── 重新排序 ──
    @bp.route("/card-config/<company>/cards/reorder", methods=["POST"])
    def reorder_company_cards(company: str):
        try:
            data = request.get_json() or {}
            card_ids = data.get("card_ids", [])
            if not card_ids:
                return jsonify({"error": "缺少 card_ids"}), 400
            reorder_cards(config.DB_PATH_COMPOSITION, company, card_ids)
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # ── 卡片 items ──
    @bp.route("/card-config/<company>/cards/<card_id>/items")
    def get_card_items_route(company: str, card_id: str):
        try:
            items = get_card_items(config.DB_PATH_COMPOSITION, company, card_id)
            return jsonify({"card_id": card_id, "items": items})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/card-config/<company>/cards/<card_id>/items", methods=["POST"])
    def add_card_item_route(company: str, card_id: str):
        try:
            data = request.get_json() or {}
            item_type = data.get("item_type", "field")
            item_key = data.get("item_key", "")
            if not item_key:
                return jsonify({"error": "缺少 item_key"}), 400
            rid = add_card_item(config.DB_PATH_COMPOSITION, company, card_id,
                               item_type=item_type, item_key=item_key,
                               item_label=data.get("item_label", ""),
                               sort_order=data.get("sort_order", 0),
                               display_role=data.get("display_role", "body"))
            return jsonify({"status": "ok", "id": rid})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/card-config/<company>/cards/<card_id>/items/<int:item_id>",
              methods=["PATCH"])
    def update_card_item_route(company: str, card_id: str, item_id: int):
        try:
            data = request.get_json() or {}
            ok = update_card_item(config.DB_PATH_COMPOSITION, company, card_id,
                                 item_id, **data)
            if not ok:
                return jsonify({"error": "更新失败"}), 404
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/card-config/<company>/cards/<card_id>/items/<int:item_id>",
              methods=["DELETE"])
    def delete_card_item_route(company: str, card_id: str, item_id: int):
        try:
            ok = remove_card_item(config.DB_PATH_COMPOSITION, company, card_id, item_id)
            if not ok:
                return jsonify({"error": "删除失败"}), 404
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/card-config/<company>/cards/<card_id>/items/batch",
              methods=["POST"])
    def batch_card_items_route(company: str, card_id: str):
        try:
            data = request.get_json() or {}
            items = data.get("items", [])
            count = batch_set_card_items(config.DB_PATH_COMPOSITION, company,
                                        card_id, items)
            return jsonify({"status": "ok", "count": count})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
