#!/usr/bin/env python3
"""Audit operating metric fields and surface values that need reconciliation."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


OPERATING_FIELDS = {
    "tam", "sam", "som", "market_cagr", "arr", "mrr",
    "registered_users", "active_users", "paying_users",
    "retention_rate", "churn_rate", "cac", "ltv", "ltv_cac_ratio",
    "gross_margin", "burn_rate", "runway_months", "market_size_source_note",
}

NUMBER_RE = re.compile(r"(?:[$￥€£]\s*)?\d+(?:[.,]\d+)*(?:\.\d+)?\s*(?:%|x|万|亿|千|百|M|B|K|m|b|k)?")
SOURCE_RE = re.compile(r"(?:来源|source)[:：]\s*([^）)；;\n]+)", re.I)


def audit_operating_metrics(fields: dict[str, str]) -> list[dict]:
    rows = []
    for key in sorted(OPERATING_FIELDS):
        value = str(fields.get(key) or "").strip()
        if not value or value == "暂缺":
            continue
        rows.append({
            "field_key": key,
            "value": value,
            "numeric_tokens": NUMBER_RE.findall(value),
            "source_hint": (SOURCE_RE.search(value).group(1).strip()
                            if SOURCE_RE.search(value) else ""),
            "needs_reconciliation": len(set(NUMBER_RE.findall(value))) > 1,
        })
    return rows


def load_fields(db_path: str, company: str) -> dict[str, str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """SELECT field_key, final_value FROM final_fields
               WHERE company_name=? AND status != 'hidden'""",
            (company,),
        ).fetchall()
    return {key: value or "" for key, value in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit operating metrics for one company.")
    parser.add_argument("company")
    parser.add_argument("--final-db", default="db/final_db.sqlite")
    parser.add_argument("--output")
    args = parser.parse_args()

    report = audit_operating_metrics(load_fields(args.final_db, args.company))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
