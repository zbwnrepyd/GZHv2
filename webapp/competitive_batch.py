from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from pathlib import Path

from config import config
from deepseek_client import call_deepseek
from competitive_scoring import (
    AI_MODEL_MAP,
    CUSTOMER_MAP,
    DATA_ASSET_MAP,
    FLYWHEEL_MAP,
    INCUMBENT_MAP,
    INFERENCE_MAP,
    PRICING_MAP,
    STACK_LAYER_MAP,
    WORKFLOW_MAP,
    compute_scores,
    normalize_fields,
)
import db as database


SYSTEM_PROMPT = """你是AI创业公司分析师。根据输入的公司信息，提取竞争格局和生态位评分所需字段。
只输出JSON，不输出任何解释。字段值必须严格使用枚举值。
信息不足时，根据已有线索推断最接近值，并将该字段加入uncertain数组。"""

USER_TEMPLATE = """公司信息：
{company_name} | {description} | {website} | {funding_stage}

补充上下文：
客户群体：{customer_segment}
商业模式：{revenue_model}
竞争壁垒：{moat}
竞品：{competitors}

提取以下字段并返回JSON：
{{
  "ai_model_dependency": "proprietary_model | fine_tuned | multi_model | openai_only | no_ai_core",
  "workflow_integration_level": "system_of_record | workflow_embedded | plugin_addon | standalone_tool",
  "data_flywheel": "yes | partial | no",
  "proprietary_data_asset": "yes_core | yes_supplementary | no",
  "incumbent_direct_competitor": "openai | google | multiple | microsoft | other | none",
  "customer_segment_type": "b2b_enterprise | developer_api | b2b2c | b2b_smb | b2c",
  "pricing_model": "outcome_based | enterprise_contract | subscription | usage_based | freemium | free",
  "inference_cost_exposure": "none | low | medium | high",
  "stack_layer": "infrastructure | foundation_model | middleware | vertical_app | distribution",
  "uncertain": []
}}"""

ENUM_FIELDS = {
    "ai_model_dependency": AI_MODEL_MAP,
    "workflow_integration_level": WORKFLOW_MAP,
    "data_flywheel": FLYWHEEL_MAP,
    "proprietary_data_asset": DATA_ASSET_MAP,
    "incumbent_direct_competitor": INCUMBENT_MAP,
    "customer_segment_type": CUSTOMER_MAP,
    "pricing_model": PRICING_MAP,
    "inference_cost_exposure": INFERENCE_MAP,
    "stack_layer": STACK_LAYER_MAP,
}

BOUNDARY_REVIEW_FIELDS = {
    "ai_model_dependency": {"fine_tuned", "multi_model"},
    "incumbent_direct_competitor": {"multiple"},
}


def _get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def latest_standard_rows(db_path: str, company_names: list[str] | None = None,
                         limit: int | None = None) -> list[sqlite3.Row]:
    with _get_db(db_path) as conn:
        database._ensure_research_schema(conn)
        conn.commit()
        where = "WHERE r.version='standard'"
        params: list[str] = []
        if company_names:
            marks = ",".join("?" for _ in company_names)
            where += f" AND r.company_name IN ({marks})"
            params.extend(company_names)
        sql = f"""
            SELECT r.*
            FROM research r
            JOIN (
              SELECT company_name, MAX(created_at) AS created_at
              FROM research
              WHERE version='standard'
              GROUP BY company_name
            ) latest
              ON latest.company_name = r.company_name
             AND latest.created_at = r.created_at
            {where}
            ORDER BY r.created_at DESC, r.company_name
        """
        if limit:
            sql += " LIMIT ?"
            params.append(str(limit))
        return conn.execute(sql, params).fetchall()


def _extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, flags=re.IGNORECASE)
    if match:
        text = match.group(1)
    clean = text.strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", clean)
        if not match:
            raise
        return json.loads(match.group(0))


def build_user_prompt(row: sqlite3.Row | dict) -> str:
    data = dict(row)
    normalized = normalize_fields(data)
    return USER_TEMPLATE.format(
        company_name=data.get("company_name", ""),
        description=" | ".join(
            str(data.get(k) or "")
            for k in ["company_type", "company_def", "main_product_def"]
            if data.get(k)
        ),
        website=data.get("website_url", ""),
        funding_stage=normalized["funding_stage"],
        customer_segment=data.get("customer_segment", ""),
        revenue_model=data.get("revenue_model", ""),
        moat=data.get("moat", ""),
        competitors=data.get("competitors", ""),
    )


def default_call(system_prompt: str, user_prompt: str) -> str:
    if not config.DEEPSEEK_API_KEY:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY")
    return call_deepseek(
        config.DEEPSEEK_API_KEY,
        system_prompt,
        user_prompt,
        model=config.DEEPSEEK_MODEL,
        temperature=0,
        max_tokens=2000,
        timeout=120,
    )


def normalize_extracted_fields(raw: dict, row: sqlite3.Row | dict) -> dict:
    data = dict(row)
    for field, mapping in ENUM_FIELDS.items():
        value = str(raw.get(field) or "").strip()
        if value in mapping:
            data[field] = value
    data = normalize_fields(data)
    data.update(compute_scores(data))
    uncertain = raw.get("uncertain", [])
    if not isinstance(uncertain, list):
        uncertain = []
    data["uncertain"] = [str(item) for item in uncertain]
    data["needs_review"] = needs_review(data)
    return data


def compact_result(fields: dict) -> dict:
    keys = [
        "id",
        "company_name",
        "ai_model_dependency",
        "workflow_integration_level",
        "data_flywheel",
        "proprietary_data_asset",
        "incumbent_direct_competitor",
        "customer_segment_type",
        "funding_stage",
        "funding_stage_score",
        "pricing_model",
        "inference_cost_exposure",
        "stack_layer",
        "score_defensibility",
        "score_incumbent_attention",
        "score_value_capture",
        "uncertain",
        "needs_review",
        "error",
    ]
    return {key: fields[key] for key in keys if key in fields}


def needs_review(row: dict) -> bool:
    uncertain = row.get("uncertain") or []
    if len(uncertain) > 3:
        return True
    for field, boundary_values in BOUNDARY_REVIEW_FIELDS.items():
        if row.get(field) in boundary_values:
            return True
    return False


def _update_research_row(conn: sqlite3.Connection, row_id: int, fields: dict):
    writable = [
        "ai_model_dependency",
        "workflow_integration_level",
        "data_flywheel",
        "proprietary_data_asset",
        "incumbent_direct_competitor",
        "customer_segment_type",
        "funding_stage",
        "funding_stage_score",
        "pricing_model",
        "inference_cost_exposure",
        "stack_layer",
        "score_defensibility",
        "score_incumbent_attention",
        "score_value_capture",
    ]
    sets = ", ".join(f"{field}=?" for field in writable)
    conn.execute(
        f"UPDATE research SET {sets} WHERE id=?",
        [fields[field] for field in writable] + [row_id],
    )


def batch_extract(db_path: str, call_fn=None, company_names: list[str] | None = None,
                  limit: int | None = None, dry_run: bool = False) -> list[dict]:
    call = call_fn or default_call
    rows = latest_standard_rows(db_path, company_names=company_names, limit=limit)
    results = []
    with _get_db(db_path) as conn:
        database._ensure_research_schema(conn)
        for row in rows:
            try:
                raw = _call_and_parse_with_retry(call, row)
                fields = normalize_extracted_fields(raw, row)
                fields["company_name"] = row["company_name"]
                fields["id"] = row["id"]
                results.append(compact_result(fields))
                if not dry_run:
                    _update_research_row(conn, row["id"], fields)
            except Exception as exc:
                results.append({
                    "company_name": row["company_name"],
                    "id": row["id"],
                    "error": str(exc),
                    "needs_review": True,
                })
        if not dry_run:
            conn.commit()
    return results


def _call_and_parse_with_retry(call, row: sqlite3.Row) -> dict:
    user_prompt = build_user_prompt(row)
    last_error = None
    for attempt in range(2):
        prompt = user_prompt
        if attempt:
            prompt += "\n\n上一次输出不是合法 JSON。请重新输出一个完整 JSON 对象，不要解释，不要 Markdown，不要省略字段。"
        try:
            return _extract_json(call(SYSTEM_PROMPT, prompt))
        except Exception as exc:
            last_error = exc
    raise last_error


def recompute_scores(db_path: str, company_names: list[str] | None = None) -> dict:
    rows = latest_standard_rows(db_path, company_names=company_names)
    with _get_db(db_path) as conn:
        database._ensure_research_schema(conn)
        for row in rows:
            data = normalize_fields(dict(row))
            data.update(compute_scores(data))
            _update_research_row(conn, row["id"], data)
        conn.commit()
    return {"updated": len(rows), "distribution": score_distribution(db_path)}


def score_distribution(db_path: str) -> dict:
    with _get_db(db_path) as conn:
        database._ensure_research_schema(conn)
        rows = conn.execute(
            "SELECT score_defensibility, score_incumbent_attention, score_value_capture "
            "FROM research WHERE version='standard'"
        ).fetchall()
    return {
        field: _distribution([row[field] for row in rows if row[field] is not None])
        for field in ["score_defensibility", "score_incumbent_attention", "score_value_capture"]
    }


def _distribution(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "min": None, "max": None, "avg": None, "buckets": [0] * 5}
    buckets = [0] * 5
    for value in values:
        index = min(4, max(0, int(float(value) // 2)))
        buckets[index] += 1
    return {
        "count": len(values),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "avg": round(sum(values) / len(values), 2),
        "buckets": buckets,
    }


def review_rows(results: list[dict]) -> list[dict]:
    return [
        {
            "company_name": row["company_name"],
            "uncertain": row.get("uncertain", []),
            "ai_model_dependency": row.get("ai_model_dependency"),
            "incumbent_direct_competitor": row.get("incumbent_direct_competitor"),
            "error": row.get("error", ""),
        }
        for row in results
        if row.get("needs_review") or row.get("error")
    ]


def write_json(path: str, data):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="竞争/生态位字段批处理工具")
    parser.add_argument("command", choices=["extract", "score", "distribution"])
    parser.add_argument("--db", default=config.DB_PATH_RESEARCH)
    parser.add_argument("--company", action="append", dest="companies")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="")
    args = parser.parse_args(argv)

    if args.command == "extract":
        results = batch_extract(
            args.db,
            company_names=args.companies,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        payload = {"results": results, "review": review_rows(results)}
    elif args.command == "score":
        payload = recompute_scores(args.db, company_names=args.companies)
    else:
        payload = score_distribution(args.db)

    if args.out:
        write_json(args.out, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
