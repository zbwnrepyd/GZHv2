"""数据迁移服务 — 将旧数据结构迁移到 GZHv2 新结构

迁移步骤：
1. research 宽表 → research_fields
2. final_content markdown → final_fields
3. company_assets 状态 → 兼容新结构
4. 每公司创建默认 8 张 card_compositions + card_items
"""
from __future__ import annotations
import json
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _load_field_contract() -> dict:
    contract_path = Path(__file__).resolve().parent.parent.parent / "contracts" / "fields.json"
    with open(contract_path) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
# 1. research 宽表 → research_fields
# ═══════════════════════════════════════════════════════════════

def migrate_research_to_fields(research_db_path: str) -> dict[str, int]:
    """将 research 表中所有公司的数据拆分为 research_fields"""
    contract = _load_field_contract()
    field_keys = set()
    for group in contract.get("groups", []):
        for f in group.get("fields", []):
            field_keys.add(f["field_key"])

    stats = {"companies": 0, "fields": 0, "skipped": 0}

    with _get_db(research_db_path) as conn:
        # 检查表是否存在
        table_check = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='research_fields'"
        ).fetchone()
        if not table_check:
            print("  research_fields 表不存在，跳过")
            return stats

        companies = conn.execute(
            "SELECT DISTINCT company_name, version FROM research ORDER BY company_name, version"
        ).fetchall()

        for row in companies:
            company = row["company_name"]
            version = row["version"]
            research = conn.execute(
                "SELECT * FROM research WHERE company_name=? AND version=?",
                (company, version)
            ).fetchone()
            if not research:
                continue

            stats["companies"] += 1
            research_dict = dict(research)
            for key in field_keys:
                value = research_dict.get(key)
                if value is None or value == "":
                    continue
                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO research_fields
                           (company_name, version, field_key, field_label, field_value,
                            source_type, confidence, updated_at)
                           VALUES (?, ?, ?, ?, ?, 'llm_extract', 'medium', CURRENT_TIMESTAMP)""",
                        (company, version, key, key, str(value)))
                    stats["fields"] += 1
                except Exception:
                    stats["skipped"] += 1
        conn.commit()

    return stats


# ═══════════════════════════════════════════════════════════════
# 2. final_content → final_fields
# ═══════════════════════════════════════════════════════════════

def migrate_final_content_to_fields(final_db_path: str) -> dict[str, int]:
    """将 final_content 中的 markdown_full 拆分为 final_fields"""
    stats = {"companies": 0, "fields": 0, "skipped": 0}

    with _get_db(final_db_path) as conn:
        table_check = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='final_fields'"
        ).fetchone()
        if not table_check:
            print("  final_fields 表不存在，跳过")
            return stats

        companies = conn.execute(
            "SELECT DISTINCT company_name FROM final_content ORDER BY company_name"
        ).fetchall()

        for row in companies:
            company = row["company_name"]
            # 取每个 card_index 的 markdown_full
            cards = conn.execute(
                """SELECT card_index, field_value FROM final_content
                   WHERE company_name=? AND field_name='markdown_full'
                   ORDER BY card_index""",
                (company,)
            ).fetchall()

            if not cards:
                continue

            stats["companies"] += 1
            for card_row in cards:
                markdown = card_row["field_value"] or ""
                if not markdown.strip():
                    continue

                # 尝试按 ## 标题拆分为字段
                fields = _parse_markdown_to_fields(markdown)
                for field_key, field_value in fields.items():
                    if not field_value.strip():
                        continue
                    try:
                        conn.execute(
                            """INSERT INTO final_fields
                               (company_name, field_key, field_label, final_value,
                                source_version, status, updated_at)
                               VALUES (?, ?, ?, ?, 'standard', 'draft', CURRENT_TIMESTAMP)
                               ON CONFLICT(company_name, field_key) DO NOTHING""",
                            (company, field_key, field_key, field_value.strip()))
                        stats["fields"] += 1
                    except Exception:
                        stats["skipped"] += 1
        conn.commit()

    return stats


def _parse_markdown_to_fields(markdown: str) -> dict[str, str]:
    """Best-effort: 按 Markdown 标题拆分字段"""
    result = {}
    sections = re.split(r"\n(?=## )", markdown)
    # 粗略映射：标题名 → field_key
    label_to_key = {
        "公司定义": "company_def", "公司介绍": "company_def",
        "创始人": "founder_name", "创始人背景": "founder_bg",
        "融资": "funding_info", "融资信息": "funding_info",
        "主产品": "main_product_def", "产品": "main_product_def",
        "亮点": "main_product_highlight",
        "盈利": "revenue_model", "商业模式": "revenue_model",
        "GTM": "gtm_strategy", "增长策略": "gtm_strategy",
        "冷启动": "cold_start",
        "增长飞轮": "growth_flywheel",
        "壁垒": "moat", "竞争壁垒": "moat",
        "竞品": "competitors",
        "生态位": "ecosystem_niche",
        "赛道机会": "market_opportunity",
        "总结": "market_opportunity",
    }
    current_key = None
    current_value = []

    for section in sections:
        section = section.strip()
        if not section:
            continue
        title_match = re.match(r"^## (.+)", section)
        if title_match:
            if current_key and current_value:
                result[current_key] = "\n".join(current_value).strip()
            title = title_match.group(1).strip()
            current_key = None
            current_value = []
            for label, key in label_to_key.items():
                if label in title:
                    current_key = key
                    body = section[title_match.end():].strip()
                    if body:
                        current_value.append(body)
                    break
            if not current_key:
                body = section[title_match.end():].strip()
                if body:
                    current_value.append(body)
        else:
            if current_key is not None:
                current_value.append(section)

    if current_key and current_value:
        result[current_key] = "\n".join(current_value).strip()

    return result


# ═══════════════════════════════════════════════════════════════
# 3. 每公司创建默认卡片编排
# ═══════════════════════════════════════════════════════════════

def migrate_create_default_cards(composition_db_path: str,
                                 research_db_path: str) -> dict[str, int]:
    """为所有已在 research 中的公司创建默认 8 张卡片编排"""
    stats = {"companies": 0, "cards": 0, "items": 0}

    from repositories.card_config_repo import (
        get_default_card_configs, create_card, add_card_item,
        get_cards,
    )
    from services.card_config_service import (
        _default_role_for_field, _default_role_for_media,
    )

    with _get_db(research_db_path) as conn:
        companies = conn.execute(
            "SELECT DISTINCT company_name FROM research ORDER BY company_name"
        ).fetchall()

    defaults = get_default_card_configs(composition_db_path)
    if not defaults:
        print("  默认卡片配置为空，跳过")
        return stats

    for row in companies:
        company = row["company_name"]
        existing = get_cards(composition_db_path, company)
        if existing:
            continue  # 已有配置的不覆盖

        for cfg in defaults:
            card_id = cfg["card_id"]
            create_card(
                composition_db_path, company,
                card_id=card_id,
                card_index=cfg["card_index"],
                card_title=cfg["card_title"],
                template_id=cfg.get("config", {}).get("template_id", ""),
            )
            stats["cards"] += 1

            config = cfg.get("config", {})
            for idx, field_key in enumerate(config.get("fields", [])):
                add_card_item(composition_db_path, company, card_id,
                              item_type="field", item_key=field_key,
                              sort_order=idx,
                              display_role=_default_role_for_field(field_key))
                stats["items"] += 1

            for idx, media_key in enumerate(config.get("media", [])):
                add_card_item(composition_db_path, company, card_id,
                              item_type="media", item_key=media_key,
                              sort_order=idx + 100,
                              display_role=_default_role_for_media(media_key))
                stats["items"] += 1

        stats["companies"] += 1

    return stats


# ═══════════════════════════════════════════════════════════════
# 一键迁移
# ═══════════════════════════════════════════════════════════════

def run_full_migration(research_db: str, final_db: str,
                       composition_db: str) -> dict:
    """执行全部迁移步骤，返回各步骤统计"""
    results = {}

    t0 = time.time()
    results["research_fields"] = migrate_research_to_fields(research_db)
    results["final_fields"] = migrate_final_content_to_fields(final_db)
    results["card_compositions"] = migrate_create_default_cards(
        composition_db, research_db)
    results["elapsed"] = round(time.time() - t0, 2)

    return results
