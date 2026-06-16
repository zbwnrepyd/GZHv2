#!/usr/bin/env python3
"""Map Markdown-first card content back to finalized fields and asset tokens."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path


ASSET_RE = re.compile(r"\{\{([a-zA-Z0-9_:-]+)\}\}")
TAG_RE = re.compile(r"<[^>]+>")
MD_RE = re.compile(r"[*_#>`-]+")


def normalize_text(value: str) -> str:
    text = TAG_RE.sub(" ", str(value or ""))
    text = MD_RE.sub(" ", text)
    return " ".join(text.split()).lower()


def map_markdown_to_fields(
    company: str,
    card_id: str,
    markdown: str,
    fields: dict[str, str],
    known_assets: set[str],
) -> dict:
    normalized_markdown = normalize_text(markdown)
    matched = []
    for key, value in sorted(fields.items()):
        normalized_value = normalize_text(value)
        if not normalized_value:
            continue
        if normalized_value in normalized_markdown or any(
            token and token in normalized_markdown
            for token in normalized_value.split()[:8]
        ):
            matched.append(key)
    assets = sorted(set(ASSET_RE.findall(markdown)) & set(known_assets))
    return {
        "company_name": company,
        "card_id": card_id,
        "matched_fields": matched,
        "asset_tokens": assets,
        "unmapped_text_length": max(0, len(normalized_markdown) - sum(len(normalize_text(fields[k])) for k in matched)),
    }


def load_final_fields(db_path: str, company: str) -> dict[str, str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """SELECT field_key, final_value FROM final_fields
               WHERE company_name=? AND status != 'hidden'""",
            (company,),
        ).fetchall()
    return {key: value or "" for key, value in rows}


def load_card_layouts(db_path: str, company: str) -> list[tuple[str, str]]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT card_id, layout_json FROM card_layout_instances WHERE company_name=? ORDER BY card_id",
            (company,),
        ).fetchall()
    layouts = []
    for card_id, raw in rows:
        try:
            layout = json.loads(raw or "{}")
        except json.JSONDecodeError:
            continue
        layouts.append((card_id, str(layout.get("markdown") or "")))
    return layouts


def load_asset_keys(db_path: str, company: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT asset_key FROM company_assets WHERE company_name=?",
            (company,),
        ).fetchall()
    return {row[0] for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Markdown card to finalized field mapping.")
    parser.add_argument("company")
    parser.add_argument("--final-db", default="db/final_db.sqlite")
    parser.add_argument("--template-db", default="db/template_db.sqlite")
    parser.add_argument("--assets-db", default="db/assets_db.sqlite")
    parser.add_argument("--output")
    args = parser.parse_args()

    fields = load_final_fields(args.final_db, args.company)
    assets = load_asset_keys(args.assets_db, args.company)
    report = [
        map_markdown_to_fields(args.company, card_id, markdown, fields, assets)
        for card_id, markdown in load_card_layouts(args.template_db, args.company)
    ]
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
