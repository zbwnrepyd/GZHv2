"""字段仓库 — research_fields + final_fields 数据访问"""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from typing import Optional


@contextmanager
def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ═══════════════════════════════════════════
# research_fields — LLM 提取的原始字段
# ═══════════════════════════════════════════

def insert_research_field(db_path: str, company_name: str, version: str,
                          field_key: str, field_label: str = "",
                          field_value: str = "", source_type: str = "",
                          source_url: str = "", confidence: str = "",
                          raw_payload: str = "") -> int:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT OR REPLACE INTO research_fields
               (company_name, version, field_key, field_label, field_value,
                source_type, source_url, confidence, raw_payload, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (company_name, version, field_key, field_label, field_value,
             source_type, source_url, confidence, raw_payload))
        conn.commit()
        return cur.lastrowid


def insert_research_fields_batch(db_path: str, rows: list[dict]) -> int:
    """批量写入 research_fields，返回写入数"""
    with _get_db(db_path) as conn:
        count = 0
        for r in rows:
            conn.execute(
                """INSERT OR REPLACE INTO research_fields
                   (company_name, version, field_key, field_label, field_value,
                    source_type, source_url, confidence, raw_payload, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (r.get("company_name"), r.get("version", "standard"),
                 r["field_key"], r.get("field_label", ""),
                 r.get("field_value", ""), r.get("source_type", ""),
                 r.get("source_url", ""), r.get("confidence", ""),
                 r.get("raw_payload", "")))
            count += 1
        conn.commit()
        return count


def get_research_fields(db_path: str, company_name: str,
                        version: str = "standard") -> list[dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM research_fields
               WHERE company_name=? AND version=?
               ORDER BY field_key""",
            (company_name, version)).fetchall()
        return [dict(r) for r in rows]


def get_research_field_value(db_path: str, company_name: str,
                             field_key: str, version: str = "standard") -> Optional[str]:
    with _get_db(db_path) as conn:
        row = conn.execute(
            """SELECT field_value FROM research_fields
               WHERE company_name=? AND version=? AND field_key=?""",
            (company_name, version, field_key)).fetchone()
        return row["field_value"] if row else None


# ═══════════════════════════════════════════
# final_fields — 人工定稿字段
# ═══════════════════════════════════════════

def upsert_final_field(db_path: str, company_name: str, field_key: str,
                       final_value: str, field_label: str = "",
                       source_version: str = "standard",
                       status: str = "draft") -> int:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO final_fields
               (company_name, field_key, field_label, final_value,
                source_version, status, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(company_name, field_key) DO UPDATE SET
               final_value=excluded.final_value,
               field_label=excluded.field_label,
               source_version=excluded.source_version,
               status=excluded.status,
               updated_at=CURRENT_TIMESTAMP""",
            (company_name, field_key, field_label or "", final_value,
             source_version, status))
        conn.commit()
        return cur.lastrowid


def get_final_fields(db_path: str, company_name: str) -> list[dict]:
    with _get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM final_fields
               WHERE company_name=? AND status != 'hidden'
               ORDER BY field_key""",
            (company_name,)).fetchall()
        return [dict(r) for r in rows]


def get_final_field_value(db_path: str, company_name: str,
                          field_key: str) -> Optional[str]:
    with _get_db(db_path) as conn:
        row = conn.execute(
            """SELECT final_value FROM final_fields
               WHERE company_name=? AND field_key=? AND status != 'hidden'""",
            (company_name, field_key)).fetchone()
        return row["final_value"] if row else None


def set_field_status(db_path: str, company_name: str, field_key: str,
                     status: str) -> bool:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """UPDATE final_fields SET status=?, updated_at=CURRENT_TIMESTAMP
               WHERE company_name=? AND field_key=?""",
            (status, company_name, field_key))
        conn.commit()
        return cur.rowcount > 0


def confirm_all_fields(db_path: str, company_name: str) -> int:
    with _get_db(db_path) as conn:
        cur = conn.execute(
            """UPDATE final_fields SET status='confirmed',
               updated_at=CURRENT_TIMESTAMP
               WHERE company_name=? AND status='draft'""",
            (company_name,))
        conn.commit()
        return cur.rowcount
