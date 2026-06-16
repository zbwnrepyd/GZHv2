"""Write normalized field candidates to research storage."""
from __future__ import annotations

import json
import sqlite3

from repositories.field_repo import insert_research_fields_batch


def select_best_candidate(field_key: str, candidates: list[dict]) -> dict | None:
    if not candidates:
        return None
    return sorted(candidates, key=lambda c: c.get("confidence", ""), reverse=True)[0]


def upsert_research_fields(
    db_path: str,
    company_name: str,
    rows: list[dict],
    version: str = "standard",
) -> int:
    prepared = []
    for row in rows:
        field_key = row.get("field_key")
        if not field_key:
            continue
        prepared.append({
            "company_name": company_name,
            "version": version,
            "field_key": field_key,
            "field_label": row.get("field_label", field_key),
            "field_value": row.get("field_value", row.get("raw_value", "")),
            "source_type": row.get("source_type", "rule_extract"),
            "source_url": row.get("source_url", ""),
            "confidence": row.get("confidence", "medium"),
            "raw_payload": json.dumps(row, ensure_ascii=False),
            "value_type": row.get("value_type", ""),
            "norm_value": row.get("norm_value", ""),
            "currency_code": row.get("currency_code", ""),
            "unit": row.get("unit", ""),
            "as_of_date": row.get("as_of_date", ""),
            "evidence_ids": row.get("evidence_ids", ""),
            "source_urls": row.get("source_urls", ""),
            "page_no": row.get("page_no"),
            "sort_order": row.get("sort_order", 0),
        })
    return insert_research_fields_batch(db_path, prepared) if prepared else 0


def append_audit_logs(db_path: str, company_name: str, logs: list[dict]) -> int:
    count = 0
    with sqlite3.connect(db_path) as conn:
        for log in logs:
            conn.execute(
                """INSERT INTO field_resolution_logs
                   (company_name, version, field_key, resolution_status,
                    resolution_method, evidence_count, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    company_name,
                    log.get("version", "standard"),
                    log.get("field_key", ""),
                    log.get("resolution_status", ""),
                    log.get("resolution_method", ""),
                    int(log.get("evidence_count", 0) or 0),
                    json.dumps(log.get("detail", {}), ensure_ascii=False),
                ),
            )
            count += 1
        conn.commit()
    return count
