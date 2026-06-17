"""证据追溯 API — /api/evidence/...

提供字段级证据链查询，支持前端证据追溯入口。
"""
from __future__ import annotations
from flask import Blueprint, request, jsonify
from config import config


def register(bp: Blueprint):
    """将路由注册到 Blueprint"""

    @bp.route("/evidence/<company_key>/<field_key>")
    def get_field_evidence(company_key: str, field_key: str):
        """获取单个字段的证据链。

        Returns:
            {
                "field_key": "...",
                "company_key": "...",
                "evidence_chain": [
                    {
                        "span_id": int,
                        "quote_text": str,
                        "normalized_fact": str,
                        "confidence": float,
                        "created_by_agent": str,
                        "doc_title": str,
                        "source_url": str,
                        "trust_tier": str,
                    }
                ],
                "total_evidence": int,
                "status": "confirmed"|"llm_extracted"|...,
            }
        """
        try:
            from research.evidence_extractor import get_evidence_for_field, count_evidence_for_field

            evidence = get_evidence_for_field(
                config.DB_PATH_RESEARCH, field_key, company_key)
            count = count_evidence_for_field(
                config.DB_PATH_RESEARCH, field_key, company_key)

            # 尝试获取字段当前状态
            status = "draft"
            try:
                from repositories.field_repo import get_research_fields
                rows = get_research_fields(
                    config.DB_PATH_RESEARCH, company_key, "standard")
                for r in rows:
                    if r.get("field_key") == field_key:
                        status = r.get("resolution_status", "draft")
                        break
            except Exception:
                pass

            return jsonify({
                "field_key": field_key,
                "company_key": company_key,
                "evidence_chain": evidence,
                "total_evidence": count,
                "status": status,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/evidence/<company_key>")
    def get_company_evidence_summary(company_key: str):
        """获取公司的证据摘要（按字段分组）。

        Returns:
            {
                "company_key": "...",
                "total_documents": int,
                "total_evidence_spans": int,
                "by_source_type": {...},
                "by_trust_tier": {...},
                "top_evidenced_fields": [
                    {"field_key": "...", "count": int, "confidence_avg": float}
                ],
            }
        """
        try:
            import sqlite3
            conn = sqlite3.connect(config.DB_PATH_RESEARCH)
            conn.row_factory = sqlite3.Row

            # 文档数
            doc_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM source_documents WHERE company_key=?",
                (company_key,),
            ).fetchone()
            total_docs = doc_row["cnt"] if doc_row else 0

            # 证据片段数
            span_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM evidence_spans WHERE company_key=?",
                (company_key,),
            ).fetchone()
            total_spans = span_row["cnt"] if span_row else 0

            # 按来源类型分组
            by_source = {}
            for r in conn.execute(
                """SELECT sd.source_type, COUNT(*) as cnt
                   FROM evidence_spans es
                   JOIN source_documents sd ON es.document_id = sd.id
                   WHERE es.company_key=?
                   GROUP BY sd.source_type""",
                (company_key,),
            ).fetchall():
                by_source[r["source_type"]] = r["cnt"]

            # 按信任层级分组
            by_tier = {}
            for r in conn.execute(
                """SELECT sd.trust_tier, COUNT(*) as cnt
                   FROM evidence_spans es
                   JOIN source_documents sd ON es.document_id = sd.id
                   WHERE es.company_key=?
                   GROUP BY sd.trust_tier""",
                (company_key,),
            ).fetchall():
                by_tier[r["trust_tier"]] = r["cnt"]

            # 证据最多的字段
            top_fields = []
            for r in conn.execute(
                """SELECT field_key, COUNT(*) as cnt,
                   ROUND(AVG(confidence), 2) as confidence_avg
                   FROM evidence_spans
                   WHERE company_key=? AND field_key IS NOT NULL AND field_key != ''
                   GROUP BY field_key
                   ORDER BY cnt DESC LIMIT 10""",
                (company_key,),
            ).fetchall():
                top_fields.append({
                    "field_key": r["field_key"],
                    "count": r["cnt"],
                    "confidence_avg": r["confidence_avg"],
                })

            conn.close()

            return jsonify({
                "company_key": company_key,
                "total_documents": total_docs,
                "total_evidence_spans": total_spans,
                "by_source_type": by_source,
                "by_trust_tier": by_tier,
                "top_evidenced_fields": top_fields,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/evidence/<company_key>/<field_key>/sources")
    def get_field_sources(company_key: str, field_key: str):
        """获取某字段的所有来源文档。

        Returns:
            {
                "field_key": "...",
                "sources": [
                    {
                        "doc_id": int,
                        "source_type": str,
                        "source_url": str,
                        "title": str,
                        "trust_tier": str,
                        "quote_count": int,
                    }
                ]
            }
        """
        try:
            import sqlite3
            conn = sqlite3.connect(config.DB_PATH_RESEARCH)
            conn.row_factory = sqlite3.Row

            rows = conn.execute(
                """SELECT sd.id as doc_id, sd.source_type, sd.source_url,
                          sd.title, sd.trust_tier, COUNT(es.id) as quote_count
                   FROM evidence_spans es
                   JOIN source_documents sd ON es.document_id = sd.id
                   WHERE es.company_key=? AND es.field_key=?
                   GROUP BY sd.id
                   ORDER BY quote_count DESC, sd.trust_tier""",
                (company_key, field_key),
            ).fetchall()

            conn.close()
            return jsonify({
                "field_key": field_key,
                "company_key": company_key,
                "sources": [dict(r) for r in rows],
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
