"""排版实例仓库 — card_layout_instances 数据访问"""
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager


@contextmanager
def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_layout(db_path: str, company_name: str, card_id: str) -> dict | None:
    with _get_db(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM card_layout_instances
               WHERE company_name=? AND card_id=?""",
            (company_name, card_id)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["layout_json"] = json.loads(d.get("layout_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["layout_json"] = {}
        return d


def get_all_layouts(db_path: str, company_name: str) -> dict[str, dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM card_layout_instances
               WHERE company_name=?""",
            (company_name,)).fetchall()
        result = {}
        for r in rows:
            d = dict(r)
            try:
                d["layout_json"] = json.loads(d.get("layout_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                d["layout_json"] = {}
            result[d["card_id"]] = d
        return result


def save_layout(db_path: str, company_name: str, card_id: str,
                layout_json: dict, template_id: str = "") -> int:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO card_layout_instances
               (company_name, card_id, template_id, layout_json, updated_at)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(company_name, card_id) DO UPDATE SET
               template_id=excluded.template_id,
               layout_json=excluded.layout_json,
               updated_at=CURRENT_TIMESTAMP""",
            (company_name, card_id, template_id,
             json.dumps(layout_json, ensure_ascii=False)))
        conn.commit()
        return cur.lastrowid


def reset_layout(db_path: str, company_name: str, card_id: str) -> bool:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """DELETE FROM card_layout_instances
               WHERE company_name=? AND card_id=?""",
            (company_name, card_id))
        conn.commit()
        return cur.rowcount > 0
