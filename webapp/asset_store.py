"""公司图片资产读写层 — company_assets 表 CRUD"""
from __future__ import annotations
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


ASSET_KEYS = [
    "logo", "office", "product_main", "products_other",
    "competitors", "flywheel", "timeline",
]

CARD_ASSET_MAP = {
    1: "logo",
    2: "office",
    3: "timeline",
    4: "product_main",
    5: "products_other",
    6: "flywheel",
    7: "competitors",
}

# 每个 asset_key 对应的卡片索引
ASSET_TO_CARD = {v: k for k, v in CARD_ASSET_MAP.items()}


def init_assets_db(db_path: str):
    """建表（幂等）"""
    sql_file = Path(__file__).resolve().parent.parent / "db" / "init_assets_db.sql"
    with _get_db(db_path) as conn:
        conn.executescript(sql_file.read_text())
        conn.commit()


@contextmanager
def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def ensure_assets_rows(db_path: str, company_name: str):
    """确保某公司有全部 7 条资产行（幂等）"""
    with _get_db(db_path) as conn:
        for key in ASSET_KEYS:
            card_index = ASSET_TO_CARD.get(key, 0)
            conn.execute(
                """INSERT OR IGNORE INTO company_assets (company_name, asset_key, card_index)
                   VALUES (?, ?, ?)""",
                (company_name, key, card_index),
            )
        conn.commit()


def upsert_asset(db_path: str, company_name: str, asset_key: str,
                 local_path: str = None, source_type: str = None,
                 source_url: str = None, prompt: str = None,
                 status: str = None, meta: dict = None):
    """写入或更新单条资产"""
    with _get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id, local_path, source_type, source_url, prompt, status, meta_json FROM company_assets WHERE company_name=? AND asset_key=?",
            (company_name, asset_key),
        ).fetchone()

        if not row:
            card_index = ASSET_TO_CARD.get(asset_key, 0)
            conn.execute(
                """INSERT INTO company_assets
                   (company_name, asset_key, card_index, local_path, source_type, source_url, prompt, status, meta_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (company_name, asset_key, card_index,
                 local_path, source_type, source_url, prompt,
                 status or "missing", json.dumps(meta, ensure_ascii=False) if meta else None),
            )
        else:
            updates = {}
            if local_path is not None:
                updates["local_path"] = local_path
            if source_type is not None:
                updates["source_type"] = source_type
            if source_url is not None:
                updates["source_url"] = source_url
            if prompt is not None:
                updates["prompt"] = prompt
            if status is not None:
                updates["status"] = status
            if meta is not None:
                updates["meta_json"] = json.dumps(meta, ensure_ascii=False)
            if updates:
                updates["updated_at"] = "CURRENT_TIMESTAMP"
                sets = [f"{k}=?" for k in updates if k != "updated_at"]
                values = [updates[k] for k in updates if k != "updated_at"] + [company_name, asset_key]
                conn.execute(
                    f"UPDATE company_assets SET {', '.join(sets)}, updated_at=CURRENT_TIMESTAMP WHERE company_name=? AND asset_key=?",
                    values,
                )
        conn.commit()


def get_asset(db_path: str, company_name: str, asset_key: str) -> dict | None:
    with _get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM company_assets WHERE company_name=? AND asset_key=?",
            (company_name, asset_key),
        ).fetchone()
        return _row_to_dict(row)


def get_assets(db_path: str, company_name: str) -> dict[str, dict]:
    """返回某公司全部资产，keyed by asset_key"""
    with _get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM company_assets WHERE company_name=? ORDER BY card_index",
            (company_name,),
        ).fetchall()
    result = {}
    for row in rows:
        d = _row_to_dict(row)
        result[d["asset_key"]] = d
    return result


def get_all_assets_grouped(db_path: str) -> dict[str, dict[str, dict]]:
    """返回全部公司的资产，{company_name: {asset_key: {...}}}"""
    with _get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM company_assets ORDER BY company_name, card_index"
        ).fetchall()
    result = {}
    for row in rows:
        d = _row_to_dict(row)
        result.setdefault(d["company_name"], {})[d["asset_key"]] = d
    return result


def _row_to_dict(row) -> dict | None:
    if not row:
        return None
    d = dict(row)
    if d.get("meta_json"):
        try:
            d["meta"] = json.loads(d["meta_json"])
        except (json.JSONDecodeError, TypeError):
            d["meta"] = {}
    else:
        d["meta"] = {}
    return d
