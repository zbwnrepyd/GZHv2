"""公司图片资产读写层 — company_assets 表 CRUD"""
from __future__ import annotations
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


ASSET_KEYS = [
    "logo", "office", "product_main", "products_other",
    "competitors", "flywheel", "timeline", "positioning_charts",
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

# 每个 asset_key 对应的卡片索引。positioning_charts 先挂在卡片6图片定稿里，
# 不替换卡片6现有的 flywheel 主资产。
ASSET_TO_CARD = {v: k for k, v in CARD_ASSET_MAP.items()}
ASSET_TO_CARD["positioning_charts"] = 6


def init_assets_db(db_path: str):
    """建表（幂等）"""
    sql_file = Path(__file__).resolve().parent.parent / "db" / "init_assets_db.sql"
    with _get_db(db_path) as conn:
        conn.executescript(sql_file.read_text())
        _ensure_assets_schema(conn)
        conn.commit()


def _ensure_assets_schema(conn: sqlite3.Connection):
    """Migrate existing local DB files to the current image asset schema."""
    _add_missing_columns(conn, "company_assets", {
        "selected_variant_id": "INTEGER",
        "final_score": "REAL DEFAULT 0",
        "auto_selected": "INTEGER DEFAULT 0",
        "fail_reason": "TEXT",
    })
    _add_missing_columns(conn, "image_variants", {
        "width": "INTEGER",
        "height": "INTEGER",
        "file_size": "INTEGER",
        "aspect_ratio": "REAL",
        "quality_score": "REAL DEFAULT 0",
        "relevance_score": "REAL DEFAULT 0",
        "source_score": "REAL DEFAULT 0",
        "final_score": "REAL DEFAULT 0",
        "reject_reason": "TEXT",
        "meta_json": "TEXT",
    })


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]):
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


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
                 status: str = None, meta: dict = None,
                 selected_variant_id: int = None,
                 final_score: float = None,
                 auto_selected: bool | int = None,
                 fail_reason: str = None):
    """写入或更新单条资产"""
    with _get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM company_assets WHERE company_name=? AND asset_key=?",
            (company_name, asset_key),
        ).fetchone()

        if not row:
            card_index = ASSET_TO_CARD.get(asset_key, 0)
            conn.execute(
                """INSERT INTO company_assets
                   (company_name, asset_key, card_index, local_path, source_type, source_url,
                    prompt, status, selected_variant_id, final_score, auto_selected, fail_reason, meta_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (company_name, asset_key, card_index,
                 normalize_browser_image_path(local_path), source_type, source_url, prompt,
                 status or "missing", selected_variant_id, final_score or 0,
                 int(bool(auto_selected)) if auto_selected is not None else 0,
                 fail_reason, json.dumps(meta, ensure_ascii=False) if meta else None),
            )
        else:
            updates = {}
            if local_path is not None:
                updates["local_path"] = normalize_browser_image_path(local_path)
            if source_type is not None:
                updates["source_type"] = source_type
            if source_url is not None:
                updates["source_url"] = source_url
            if prompt is not None:
                updates["prompt"] = prompt
            if status is not None:
                updates["status"] = status
            if selected_variant_id is not None:
                updates["selected_variant_id"] = selected_variant_id
            if final_score is not None:
                updates["final_score"] = final_score
            if auto_selected is not None:
                updates["auto_selected"] = int(bool(auto_selected))
            if fail_reason is not None:
                updates["fail_reason"] = fail_reason
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


# ═══════════════════════════════════════════════════════════════
# image_variants 变体库 CRUD
# ═══════════════════════════════════════════════════════════════

def list_variants(db_path: str, company_name: str, asset_key: str) -> list[dict]:
    """返回某公司某 asset_key 的全部变体，选中优先，然后按 final_score 倒序"""
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM image_variants
               WHERE company_name=? AND asset_key=?
               ORDER BY is_selected DESC, final_score DESC, created_at DESC""",
            (company_name, asset_key),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def insert_variant(db_path: str, company_name: str, asset_key: str,
                   local_path: str, source_type: str,
                   source_url: str = "", source_page: str = "",
                   author: str = "", license: str = "",
                   attribution_req: int = 0, prompt: str = "",
                   width: int = None, height: int = None,
                   file_size: int = None, aspect_ratio: float = None,
                   quality_score: float = 0, relevance_score: float = 0,
                   source_score: float = 0, final_score: float = 0,
                   reject_reason: str = "", meta: dict = None) -> int:
    """插入一条变体记录，返回 id"""
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO image_variants
               (company_name, asset_key, local_path, source_type,
                source_url, source_page, author, license,
                attribution_req, prompt, width, height, file_size, aspect_ratio,
                quality_score, relevance_score, source_score, final_score,
                reject_reason, meta_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (company_name, asset_key, normalize_browser_image_path(local_path), source_type,
             source_url, source_page, author, license,
             attribution_req, prompt, width, height, file_size, aspect_ratio,
             quality_score, relevance_score, source_score, final_score,
             reject_reason, json.dumps(meta, ensure_ascii=False) if meta else None),
        )
        conn.commit()
        return cur.lastrowid


def select_variant(db_path: str, company_name: str, asset_key: str,
                   variant_id: int, auto_selected: bool = False) -> bool:
    """将指定变体设为选中，其他取消选中；同时写回 company_assets"""
    with _get_db(db_path) as conn:
        row = conn.execute(
            """SELECT local_path, source_type, source_url, prompt, final_score
               FROM image_variants
               WHERE id=? AND company_name=? AND asset_key=?""",
            (variant_id, company_name, asset_key),
        ).fetchone()
        if not row:
            return False

        # 取消该 asset_key 下所有变体的选中
        conn.execute(
            """UPDATE image_variants SET is_selected=0
               WHERE company_name=? AND asset_key=?""",
            (company_name, asset_key),
        )
        # 选中目标变体
        conn.execute(
            """UPDATE image_variants SET is_selected=1
               WHERE id=? AND company_name=? AND asset_key=?""",
            (variant_id, company_name, asset_key),
        )

        conn.commit()

    # 写回 company_assets
    upsert_asset(db_path, company_name, asset_key,
                 local_path=normalize_browser_image_path(row["local_path"]),
                 source_type=row["source_type"],
                 source_url=row["source_url"],
                 prompt=row["prompt"],
                 status="ready",
                 selected_variant_id=variant_id,
                 final_score=row["final_score"] or 0,
                 auto_selected=auto_selected,
                 fail_reason="")
    return True


def update_variant_scores(db_path: str, variant_id: int, *,
                          width: int = None, height: int = None,
                          file_size: int = None, aspect_ratio: float = None,
                          quality_score: float = None,
                          relevance_score: float = None,
                          source_score: float = None,
                          final_score: float = None,
                          reject_reason: str = None,
                          meta: dict = None) -> bool:
    updates = {}
    for key, value in {
        "width": width,
        "height": height,
        "file_size": file_size,
        "aspect_ratio": aspect_ratio,
        "quality_score": quality_score,
        "relevance_score": relevance_score,
        "source_score": source_score,
        "final_score": final_score,
        "reject_reason": reject_reason,
    }.items():
        if value is not None:
            updates[key] = value
    if meta is not None:
        updates["meta_json"] = json.dumps(meta, ensure_ascii=False)
    if not updates:
        return False
    sets = ", ".join(f"{k}=?" for k in updates)
    with _get_db(db_path) as conn:
        cur = conn.execute(
            f"UPDATE image_variants SET {sets} WHERE id=?",
            [*updates.values(), variant_id],
        )
        conn.commit()
        return cur.rowcount > 0


def delete_variant(db_path: str, company_name: str, asset_key: str,
                   variant_id: int) -> bool:
    """删除变体记录（不删本地文件）"""
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """DELETE FROM image_variants
               WHERE id=? AND company_name=? AND asset_key=?""",
            (variant_id, company_name, asset_key),
        )
        conn.commit()
        return cur.rowcount > 0


def _row_to_dict(row) -> dict | None:
    if not row:
        return None
    d = dict(row)
    d["local_path"] = normalize_browser_image_path(d.get("local_path"))
    if d.get("meta_json"):
        try:
            d["meta"] = json.loads(d["meta_json"])
        except (json.JSONDecodeError, TypeError):
            d["meta"] = {}
    else:
        d["meta"] = {}
    return d


def normalize_browser_image_path(path: str | None) -> str | None:
    """Normalize image paths stored before browser-safe URLs were introduced."""
    if not path:
        return path
    if path.startswith(("/images/", "http://", "https://", "data:")):
        return path
    marker = "/images/"
    idx = path.find(marker)
    if idx >= 0:
        return path[idx:]
    return path
