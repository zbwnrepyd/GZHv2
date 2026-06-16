#!/usr/bin/env python3
"""Check that card/field changes do not reduce existing finalized content."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def normalize_text(value: str) -> str:
    return " ".join(str(value or "").split())


def compare_field_snapshots(before: dict[str, str], after: dict[str, str]) -> dict:
    missing_fields = []
    shortened_fields = []
    for key, old_value in sorted(before.items()):
        old = normalize_text(old_value)
        if not old:
            continue
        new = normalize_text(after.get(key, ""))
        if not new:
            missing_fields.append(key)
        elif len(new) < len(old):
            shortened_fields.append({
                "field_key": key,
                "before_len": len(old),
                "after_len": len(new),
            })
    return {
        "ok": not missing_fields and not shortened_fields,
        "missing_fields": missing_fields,
        "shortened_fields": shortened_fields,
    }


def load_final_fields(db_path: str, company: str) -> dict[str, str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """SELECT field_key, final_value FROM final_fields
               WHERE company_name=? AND status != 'hidden'""",
            (company,),
        ).fetchall()
    return {key: value or "" for key, value in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare finalized field coverage before/after changes.")
    parser.add_argument("--before-json", help="JSON file containing {field_key: value}")
    parser.add_argument("--after-json", help="JSON file containing {field_key: value}")
    parser.add_argument("--final-db", default="db/final_db.sqlite")
    parser.add_argument("--company")
    parser.add_argument("--output")
    args = parser.parse_args()

    if args.before_json and args.after_json:
        before = json.loads(Path(args.before_json).read_text(encoding="utf-8"))
        after = json.loads(Path(args.after_json).read_text(encoding="utf-8"))
    elif args.company:
        before = load_final_fields(args.final_db, args.company)
        after = dict(before)
    else:
        parser.error("Provide --before-json/--after-json or --company")

    report = compare_field_snapshots(before, after)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
