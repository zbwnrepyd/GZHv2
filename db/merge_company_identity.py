#!/usr/bin/env python3
"""合并历史大小写重复公司数据 — Limitless/limitless → 单一 company_key。

用法:
  python3 db/merge_company_identity.py --dry-run
  python3 db/merge_company_identity.py --apply
"""
from __future__ import annotations
import argparse, sqlite3, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "webapp"))
from config import config
from company_identity import build_company_identity


def _conn(path: str) -> sqlite3.Connection:
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    return c


def _get_all_companies(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT DISTINCT company_name, "
        "COALESCE(NULLIF(website_url,''),'') as website_url "
        "FROM research ORDER BY company_name"
    ).fetchall()
    return [dict(r) for r in rows]


def _build_key_map(companies: list[dict]) -> dict[str, str]:
    key_map: dict[str, str] = {}
    for c in companies:
        name = c["company_name"]
        url = c.get("website_url", "")
        identity = build_company_identity(name, url)
        key_map[name] = identity.company_key
    return key_map


def _merge_table(conn, table: str, key_map: dict[str, str],
                 dry_run: bool) -> int:
    count = 0
    for name, key in key_map.items():
        if dry_run:
            rows = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE company_name=? "
                f"AND (company_key IS NULL OR company_key!=?)",
                (name, key)).fetchone()
            count += rows[0]
        else:
            cur = conn.execute(
                f"UPDATE {table} SET company_key=? "
                f"WHERE company_name=? AND (company_key IS NULL OR company_key!=?)",
                (key, name, key))
            count += cur.rowcount
    if not dry_run:
        conn.commit()
    return count


def _merge_final_fields(conn, key_map, dry_run: bool) -> int:
    count = 0
    for name, key in key_map.items():
        if dry_run:
            rows = conn.execute(
                "SELECT COUNT(*) FROM final_fields WHERE company_name=? "
                "AND (company_key IS NULL OR company_key!=?)",
                (name, key)).fetchone()
            count += rows[0]
        else:
            cur = conn.execute(
                "UPDATE final_fields SET company_key=? "
                "WHERE company_name=? AND (company_key IS NULL OR company_key!=?)",
                (key, name, key))
            count += cur.rowcount
    if not dry_run:
        conn.commit()
    return count


def _conflicting_keys(key_map: dict[str, str]) -> list[tuple[str, str, str]]:
    """Find cases where different company_names map to the same key."""
    by_key: dict[str, list[str]] = {}
    for name, key in key_map.items():
        by_key.setdefault(key, []).append(name)
    return [(key, names[0], n) for key, names in by_key.items()
            if len(names) > 1 for n in names[1:]]


def main():
    parser = argparse.ArgumentParser(
        description="合并历史大小写重复公司数据")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览变更，不实际修改")
    parser.add_argument("--apply", action="store_true",
                        help="执行合并")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        print("用法: python3 db/merge_company_identity.py --dry-run | --apply")
        sys.exit(1)

    dry_run = args.dry_run

    research_conn = _conn(config.DB_PATH_RESEARCH)
    final_conn = _conn(config.DB_PATH_FINAL)
    assets_conn = _conn(config.DB_PATH_ASSETS)

    companies = _get_all_companies(research_conn)
    key_map = _build_key_map(companies)
    unique_keys = len(set(key_map.values()))

    print(f"公司名变体: {len(key_map)} → 唯一 company_key: {unique_keys}")
    conflicts = _conflicting_keys(key_map)
    if conflicts:
        print(f"\n将合并 {len(conflicts)} 个重复:")
        for key, primary, dup in conflicts:
            print(f"  {dup} → {primary} (key={key})")

    print(f"\n{'[DRY RUN]' if dry_run else '[APPLY]'} 修改统计:")

    # research
    n = _merge_table(research_conn, "research", key_map, dry_run)
    print(f"  research: {n} 行")

    # research_jobs
    n = _merge_table(research_conn, "research_jobs", key_map, dry_run)
    print(f"  research_jobs: {n} 行")

    # final_fields
    n = _merge_final_fields(final_conn, key_map, dry_run)
    print(f"  final_fields: {n} 行")

    # company_assets
    n = _merge_table(assets_conn, "company_assets", key_map, dry_run)
    print(f"  company_assets: {n} 行")

    # image_variants
    n = _merge_table(assets_conn, "image_variants", key_map, dry_run)
    print(f"  image_variants: {n} 行")

    research_conn.close()
    final_conn.close()
    assets_conn.close()

    if dry_run:
        print("\nDRY RUN — 未实际修改。加 --apply 执行。")
    else:
        print("\n合并完成。")


if __name__ == "__main__":
    main()
