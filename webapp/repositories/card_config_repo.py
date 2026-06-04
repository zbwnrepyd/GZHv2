"""卡片编排仓库 — card_compositions + card_items 数据访问"""
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


# ═══════════════════════════════════════════
# card_compositions
# ═══════════════════════════════════════════

def create_card(db_path: str, company_name: str, card_id: str,
                card_index: int, card_title: str, template_id: str = "",
                enabled: bool = True) -> int:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO card_compositions
               (company_name, card_id, card_index, card_title, template_id, enabled)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (company_name, card_id, card_index, card_title, template_id,
             1 if enabled else 0))
        conn.commit()
        return cur.lastrowid


def get_cards(db_path: str, company_name: str) -> list[dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM card_compositions
               WHERE company_name=?
               ORDER BY card_index""",
            (company_name,)).fetchall()
        return [dict(r) for r in rows]


def get_card(db_path: str, company_name: str, card_id: str) -> dict | None:
    with _get_db(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM card_compositions
               WHERE company_name=? AND card_id=?""",
            (company_name, card_id)).fetchone()
        return dict(row) if row else None


def get_enabled_cards(db_path: str, company_name: str) -> list[dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM card_compositions
               WHERE company_name=? AND enabled=1
               ORDER BY card_index""",
            (company_name,)).fetchall()
        return [dict(r) for r in rows]


def update_card(db_path: str, company_name: str, card_id: str, **kwargs) -> bool:
    allowed = {"card_index", "card_title", "template_id", "enabled"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return False
    sets = ", ".join(f"{k}=?" for k in updates)
    with _get_db(db_path) as conn:
        cur = conn.execute(
            f"""UPDATE card_compositions SET {sets},
                updated_at=CURRENT_TIMESTAMP
                WHERE company_name=? AND card_id=?""",
            [*updates.values(), company_name, card_id])
        conn.commit()
        return cur.rowcount > 0


def delete_card(db_path: str, company_name: str, card_id: str) -> bool:
    with _get_db(db_path) as conn:
        conn.execute("DELETE FROM card_items WHERE company_name=? AND card_id=?",
                     (company_name, card_id))
        cur = conn.execute(
            "DELETE FROM card_compositions WHERE company_name=? AND card_id=?",
            (company_name, card_id))
        conn.commit()
        return cur.rowcount > 0


def reorder_cards(db_path: str, company_name: str,
                  card_ids: list[str]) -> bool:
    with _get_db(db_path) as conn:
        for idx, card_id in enumerate(card_ids, 1):
            conn.execute(
                """UPDATE card_compositions SET card_index=?,
                   updated_at=CURRENT_TIMESTAMP
                   WHERE company_name=? AND card_id=?""",
                (idx, company_name, card_id))
        conn.commit()
        return True


# ═══════════════════════════════════════════
# card_items
# ═══════════════════════════════════════════

def add_card_item(db_path: str, company_name: str, card_id: str,
                  item_type: str, item_key: str, item_label: str = "",
                  sort_order: int = 0, display_role: str = "body") -> int:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO card_items
               (company_name, card_id, item_type, item_key, item_label,
                sort_order, display_role)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (company_name, card_id, item_type, item_key, item_label or "",
             sort_order, display_role))
        conn.commit()
        return cur.lastrowid


def get_card_items(db_path: str, company_name: str,
                   card_id: str) -> list[dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM card_items
               WHERE company_name=? AND card_id=? AND enabled=1
               ORDER BY sort_order""",
            (company_name, card_id)).fetchall()
        return [dict(r) for r in rows]


def update_card_item(db_path: str, company_name: str, card_id: str,
                     item_id: int, **kwargs) -> bool:
    allowed = {"sort_order", "display_role", "item_label", "enabled"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return False
    sets = ", ".join(f"{k}=?" for k in updates)
    with _get_db(db_path) as conn:
        cur = conn.execute(
            f"""UPDATE card_items SET {sets}
                WHERE id=? AND company_name=? AND card_id=?""",
            [*updates.values(), item_id, company_name, card_id])
        conn.commit()
        return cur.rowcount > 0


def remove_card_item(db_path: str, company_name: str, card_id: str,
                     item_id: int) -> bool:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """DELETE FROM card_items
               WHERE id=? AND company_name=? AND card_id=?""",
            (item_id, company_name, card_id))
        conn.commit()
        return cur.rowcount > 0


def clear_card_items(db_path: str, company_name: str, card_id: str) -> int:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM card_items WHERE company_name=? AND card_id=?",
            (company_name, card_id))
        conn.commit()
        return cur.rowcount


def batch_set_card_items(db_path: str, company_name: str, card_id: str,
                         items: list[dict]) -> int:
    """批量替换卡片的所有 items（先删后插）"""
    clear_card_items(db_path, company_name, card_id)
    count = 0
    for item in items:
        add_card_item(db_path, company_name, card_id,
                      item_type=item["item_type"],
                      item_key=item["item_key"],
                      item_label=item.get("item_label", ""),
                      sort_order=item.get("sort_order", count),
                      display_role=item.get("display_role", "body"))
        count += 1
    return count


# ═══════════════════════════════════════════
# default_card_configs
# ═══════════════════════════════════════════

def get_default_card_configs(db_path: str) -> list[dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM default_card_configs ORDER BY card_index"""
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["config"] = json.loads(d.get("config_json", "{}"))
            except (json.JSONDecodeError, TypeError):
                d["config"] = {}
            result.append(d)
        return result
