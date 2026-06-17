"""来源文档存储 — 采集结果写入 source_documents 表。

P1: 替代当前 evidence_items 的轻量存储。
将 Tavily/GitHub/YouTube/官网的完整结果保存为 source_documents 行，
后续由 evidence_extractor 抽取 evidence_spans。
"""
from __future__ import annotations
import hashlib
import sqlite3
from datetime import datetime, timezone


def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def insert_document(db_path: str, company_key: str, source_type: str,
                    source_url: str = "", title: str = "",
                    raw_text: str = "", publisher: str = "",
                    published_at: str = "", trust_tier: str = "search",
                    intent: str = "", run_id: str = "") -> int:
    """写入一条 source_document。返回 rowid，失败返回 -1。"""
    try:
        conn = _get_db(db_path)
        chash = _content_hash(raw_text or "")
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 截断过长文本
        text = (raw_text or "").strip()
        if len(text) > 50000:
            text = text[:49997] + "..."

        cur = conn.execute(
            """INSERT INTO source_documents
               (run_id, company_key, source_type, source_url, title,
                publisher, published_at, fetched_at, raw_text, content_hash,
                trust_tier, intent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id or "", company_key, source_type, source_url, title,
             publisher, published_at or "", now, text, chash,
             trust_tier, intent or ""),
        )
        conn.commit()
        doc_id = cur.lastrowid
        conn.close()
        return doc_id
    except Exception:
        return -1


def get_documents_for_company(db_path: str, company_key: str,
                              source_type: str = "") -> list[dict]:
    """获取公司的所有 source_documents。"""
    try:
        conn = _get_db(db_path)
        if source_type:
            rows = conn.execute(
                "SELECT id, source_type, title, source_url, trust_tier, "
                "intent, fetched_at FROM source_documents "
                "WHERE company_key=? AND source_type=? "
                "ORDER BY fetched_at DESC LIMIT 100",
                (company_key, source_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, source_type, title, source_url, trust_tier, "
                "intent, fetched_at FROM source_documents "
                "WHERE company_key=? "
                "ORDER BY fetched_at DESC LIMIT 200",
                (company_key,),
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_document_text(db_path: str, document_id: int) -> str:
    """获取单篇文档的全文。"""
    try:
        conn = _get_db(db_path)
        row = conn.execute(
            "SELECT raw_text FROM source_documents WHERE id=?",
            (document_id,),
        ).fetchone()
        conn.close()
        return row["raw_text"] if row else ""
    except Exception:
        return ""


def count_documents(db_path: str, company_key: str) -> dict:
    """统计公司各类来源文档数。"""
    try:
        conn = _get_db(db_path)
        rows = conn.execute(
            "SELECT source_type, COUNT(*) as cnt FROM source_documents "
            "WHERE company_key=? GROUP BY source_type",
            (company_key,),
        ).fetchall()
        conn.close()
        return {r["source_type"]: r["cnt"] for r in rows}
    except Exception:
        return {}
