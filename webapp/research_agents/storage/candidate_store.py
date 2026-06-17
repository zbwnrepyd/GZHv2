"""候选值存储 — field_candidates 表 CRUD。

P1: 替代混在一起的 Standard/Business/Spread 三版本。
"""
from __future__ import annotations
import json
import sqlite3


def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def insert_candidate(db_path: str, company_key: str, field_key: str,
                     candidate_value: str, agent_name: str = "",
                     evidence_span_ids: list[int] | None = None,
                     confidence: float = 0.5,
                     status: str = "active",
                     conflict_group_id: str = "",
                     reasoning_summary: str = "",
                     run_id: str = "") -> int:
    """写入一条候选值。返回 rowid，失败返回 -1。"""
    try:
        conn = _get_db(db_path)
        ev_ids_json = json.dumps(evidence_span_ids or [], ensure_ascii=False)
        cur = conn.execute(
            """INSERT INTO field_candidates
               (run_id, company_key, field_key, agent_name, candidate_value,
                evidence_span_ids, confidence, status, conflict_group_id,
                reasoning_summary)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id or "", company_key, field_key, agent_name,
             candidate_value, ev_ids_json, confidence, status,
             conflict_group_id or "", reasoning_summary or ""),
        )
        conn.commit()
        cid = cur.lastrowid
        conn.close()
        return cid
    except Exception:
        return -1


def get_candidates_for_field(db_path: str, company_key: str,
                             field_key: str) -> list[dict]:
    """获取某字段的所有候选值。"""
    try:
        conn = _get_db(db_path)
        rows = conn.execute(
            """SELECT * FROM field_candidates
               WHERE company_key=? AND field_key=?
               ORDER BY confidence DESC, created_at DESC""",
            (company_key, field_key),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def select_candidate(db_path: str, candidate_id: int) -> bool:
    """标记候选值为选中，同一字段其他候选标记 rejected。"""
    try:
        conn = _get_db(db_path)
        row = conn.execute(
            "SELECT company_key, field_key FROM field_candidates WHERE id=?",
            (candidate_id,),
        ).fetchone()
        if not row:
            conn.close()
            return False
        ckey = row["company_key"]
        fkey = row["field_key"]
        # 该字段所有候选 → rejected
        conn.execute(
            "UPDATE field_candidates SET selected=0, status='rejected' "
            "WHERE company_key=? AND field_key=?",
            (ckey, fkey),
        )
        # 选中目标
        conn.execute(
            "UPDATE field_candidates SET selected=1, status='selected' WHERE id=?",
            (candidate_id,),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_selected_candidates(db_path: str, company_key: str) -> dict[str, dict]:
    """获取公司所有被选中的候选值。返回 {field_key: {candidate_value, agent_name, ...}}"""
    try:
        conn = _get_db(db_path)
        rows = conn.execute(
            """SELECT * FROM field_candidates
               WHERE company_key=? AND selected=1
               ORDER BY field_key""",
            (company_key,),
        ).fetchall()
        conn.close()
        return {r["field_key"]: dict(r) for r in rows}
    except Exception:
        return {}
