#!/usr/bin/env python3
"""Extract dominant Markdown-first layout style from saved card layouts."""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path


STYLE_KEYS = ("fontSize", "lineHeight", "paragraphGap", "padding", "imageMaxHeight")
DEFAULT_STYLE = {
    "fontSize": 32,
    "lineHeight": 1.6,
    "paragraphGap": 22,
    "padding": 74,
    "imageMaxHeight": 360,
}


def dominant_style(styles: list[dict]) -> dict:
    result = dict(DEFAULT_STYLE)
    for key in STYLE_KEYS:
        values = [style.get(key) for style in styles if style.get(key) is not None]
        if values:
            result[key] = Counter(values).most_common(1)[0][0]
    return result


def load_layout_styles(db_path: str, company: str) -> list[dict]:
    styles = []
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT layout_json FROM card_layout_instances WHERE company_name=?",
            (company,),
        ).fetchall()
    for (raw,) in rows:
        try:
            layout = json.loads(raw or "{}")
        except json.JSONDecodeError:
            continue
        style = layout.get("style")
        if isinstance(style, dict):
            styles.append(style)
    return styles


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract dominant layout style for one company.")
    parser.add_argument("company")
    parser.add_argument("--template-db", default="db/template_db.sqlite")
    parser.add_argument("--output")
    args = parser.parse_args()

    report = dominant_style(load_layout_styles(args.template_db, args.company))
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
