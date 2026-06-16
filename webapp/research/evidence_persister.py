"""证据持久化 — 将内存 EvidenceItem 列表写入 evidence_items 表，可追溯"""
from __future__ import annotations
import hashlib
import sqlite3


def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def persist_evidence_pool(db_path: str, company_name: str,
                          evidence_items: list,
                          version: str = "standard") -> int:
    """将证据池写入 evidence_items 表。返回写入条数。"""
    count = 0
    try:
        conn = _get_db(db_path)
        for item in evidence_items:
            # EvidenceItem 属性: source, title, url, content, final_score, source_score
            url = (getattr(item, "url", "") or "").strip()
            title = (getattr(item, "title", "") or "").strip()
            text = (getattr(item, "content", "") or "").strip()
            source = (getattr(item, "source", "unknown") or "unknown").strip()
            relevance = float(getattr(item, "final_score", 0) or 0)
            reliability = float(getattr(item, "source_score", 0) or 0)

            if not text or len(text) < 10:
                continue

            # 去重 hash：URL + 文本前 200 字符
            raw = f"{url}|{text[:200]}"
            ev_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

            # 截断过长文本
            if len(text) > 4000:
                text = text[:3997] + "..."

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO evidence_items
                       (company_name, source_type, source_url, source_title,
                        evidence_text, evidence_hash, relevance_score,
                        reliability_score, research_version)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (company_name, source, url, title, text, ev_hash,
                     relevance, reliability, version),
                )
                if conn.total_changes > 0:
                    count += 1
            except Exception:
                continue

        conn.commit()
        conn.close()
    except Exception:
        pass  # 证据持久化失败不阻塞主流程

    return count
