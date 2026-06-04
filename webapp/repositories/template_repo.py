"""模板仓库 — card_templates 数据访问"""
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


def get_all_templates(db_path: str) -> list[dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM card_templates ORDER BY is_builtin DESC, template_name"""
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["template_json"] = json.loads(d.get("template_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                d["template_json"] = {}
            result.append(d)
        return result


def get_template(db_path: str, template_id: str) -> dict | None:
    with _get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM card_templates WHERE template_id=?",
            (template_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        try:
            d["template_json"] = json.loads(d.get("template_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["template_json"] = {}
        return d


def create_template(db_path: str, template_id: str, template_name: str,
                    template_json: dict, canvas_width: int = 900,
                    canvas_height: int = 1200, background_type: str = "color",
                    background_value: str = "#FFFFFF",
                    is_builtin: bool = False) -> int:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT OR REPLACE INTO card_templates
               (template_id, template_name, canvas_width, canvas_height,
                background_type, background_value, template_json, is_builtin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (template_id, template_name, canvas_width, canvas_height,
             background_type, background_value,
             json.dumps(template_json, ensure_ascii=False),
             1 if is_builtin else 0))
        conn.commit()
        return cur.lastrowid


def update_template(db_path: str, template_id: str, **kwargs) -> bool:
    allowed = {"template_name", "canvas_width", "canvas_height",
               "background_type", "background_value", "template_json"}
    updates = {}
    for k, v in kwargs.items():
        if k in allowed and v is not None:
            if k == "template_json" and isinstance(v, dict):
                updates[k] = json.dumps(v, ensure_ascii=False)
            else:
                updates[k] = v
    if not updates:
        return False
    sets = ", ".join(f"{k}=?" for k in updates)
    with _get_db(db_path) as conn:
        cur = conn.execute(
            f"""UPDATE card_templates SET {sets},
                updated_at=CURRENT_TIMESTAMP
                WHERE template_id=? AND is_builtin=0""",
            [*updates.values(), template_id])
        conn.commit()
        return cur.rowcount > 0


def delete_template(db_path: str, template_id: str) -> bool:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """DELETE FROM card_templates
               WHERE template_id=? AND is_builtin=0""",
            (template_id,))
        conn.commit()
        return cur.rowcount > 0


def duplicate_template(db_path: str, template_id: str,
                       new_id: str, new_name: str) -> int | None:
    tpl = get_template(db_path, template_id)
    if not tpl:
        return None
    return create_template(
        db_path, new_id, new_name,
        template_json=tpl.get("template_json", {}),
        canvas_width=tpl.get("canvas_width", 900),
        canvas_height=tpl.get("canvas_height", 1200),
        background_type=tpl.get("background_type", "color"),
        background_value=tpl.get("background_value", "#FFFFFF"),
        is_builtin=False,
    )
