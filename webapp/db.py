from __future__ import annotations
import json
import os
import re
import shutil
import sqlite3
from contextlib import contextmanager

from competitive_scoring import compute_scores, normalize_fields
from path_safety import safe_path_segment

# Track whether research schema has been ensured (one-time migration, not per-query)
_schema_ensured: set[str] = set()


def ensure_research_schema_once(db_path: str):
    """幂等确保 research DB schema 包含评分字段（仅首次调用时执行 ALTER TABLE）。"""
    if db_path in _schema_ensured:
        return
    with get_db(db_path) as conn:
        _ensure_research_schema(conn)
        conn.commit()
    _schema_ensured.add(db_path)


@contextmanager
def get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── research_db 查询 ──────────────────────────────────────────


def get_companies(db_path: str, final_db_path: str = "") -> list[dict]:
    """列出所有已研究公司，附带定稿进度"""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT company_name, MAX(created_at) as created_at "
            "FROM research GROUP BY company_name ORDER BY created_at DESC"
        ).fetchall()
        companies = []
        for row in rows:
            latest = conn.execute(
                "SELECT * FROM research WHERE company_name=? ORDER BY created_at DESC, CASE version WHEN 'standard' THEN 0 ELSE 1 END LIMIT 1",
                (row["company_name"],),
            ).fetchone()
            filled = 0
            if latest:
                for field in REQUIRED_RESEARCH_FIELDS:
                    value = latest[field]
                    if value is not None and str(value).strip() not in ("", "暂缺"):
                        filled += 1
            completeness = round(filled / len(REQUIRED_RESEARCH_FIELDS) * 100) if latest else 0
            confirmed = 0
            total = 8
            if final_db_path:
                confirmed, total = _count_final_fields_progress(final_db_path, row["company_name"])
            website_url = latest["website_url"] if latest else ""
            if not website_url or str(website_url).strip() in ("", "暂缺"):
                website_url = _latest_job_company_url(conn, row["company_name"])
            scoring = _company_scoring_payload(latest)
            companies.append(
                {
                    "company_name": row["company_name"],
                    "category": latest["company_type"] if latest else "",
                    "company_url": website_url,
                    "website_url": website_url,
                    "created_at": row["created_at"],
                    "researched_at": row["created_at"],
                    "completeness": completeness,
                    "confirmed": confirmed,
                    "total": total,
                    **scoring,
                }
            )
        return companies


def _company_scoring_payload(row: sqlite3.Row | None) -> dict:
    if not row:
        return {
            "ai_model_dependency": "",
            "workflow_integration_level": "",
            "data_flywheel": "",
            "proprietary_data_asset": "",
            "incumbent_direct_competitor": "",
            "customer_segment_type": "",
            "funding_stage": "",
            "funding_stage_score": None,
            "pricing_model": "",
            "inference_cost_exposure": "",
            "stack_layer": "",
            "score_defensibility": None,
            "score_incumbent_attention": None,
            "score_value_capture": None,
        }

    data = dict(row)
    normalized = normalize_fields(data)
    scores = compute_scores(normalized)
    payload = {}
    for field in [
        "ai_model_dependency",
        "workflow_integration_level",
        "data_flywheel",
        "proprietary_data_asset",
        "incumbent_direct_competitor",
        "customer_segment_type",
        "funding_stage",
        "pricing_model",
        "inference_cost_exposure",
        "stack_layer",
    ]:
        payload[field] = data.get(field) or normalized[field]
    for field in [
        "funding_stage_score",
        "score_defensibility",
        "score_incumbent_attention",
        "score_value_capture",
    ]:
        payload[field] = data.get(field) if data.get(field) is not None else scores[field]
    return payload


def _latest_job_company_url(conn: sqlite3.Connection, company_name: str) -> str:
    try:
        row = conn.execute(
            "SELECT company_url FROM research_jobs WHERE company_name=? ORDER BY created_at DESC LIMIT 1",
            (company_name,),
        ).fetchone()
        return row["company_url"] if row else ""
    except sqlite3.Error:
        return ""


def _count_confirmed_cards(final_db_path: str, company_name: str) -> int:
    try:
        with get_db(final_db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT card_index) as cnt FROM final_content WHERE company_name=? AND field_name='markdown_full'",
                (company_name,),
            ).fetchone()
            return row["cnt"] if row else 0
    except Exception:
        return 0


def _count_final_fields_progress(final_db_path: str, company_name: str) -> tuple[int, int]:
    try:
        with get_db(final_db_path) as conn:
            row = conn.execute(
                """SELECT
                     COUNT(CASE WHEN status='confirmed' THEN 1 END) as confirmed,
                     COUNT(*) as total
                   FROM final_fields
                   WHERE company_name=?""",
                (company_name,),
            ).fetchone()
            total = row["total"] if row else 0
            if total:
                return row["confirmed"], total
    except Exception:
        pass
    return _count_confirmed_cards(final_db_path, company_name), 8


def get_research(db_path: str, company_name: str, version: str) -> dict | None:
    """读取指定版本的全部字段"""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM research WHERE company_name=? AND version=? "
            "ORDER BY created_at DESC LIMIT 1",
            (company_name, version),
        ).fetchone()
        return dict(row) if row else None


def get_all_versions(db_path: str, company_name: str) -> dict[str, dict]:
    """读取某公司的所有版本"""
    versions = {}
    for v in ("standard", "business", "spread"):
        data = get_research(db_path, company_name, v)
        if data:
            versions[v] = data
    return versions


# ── research_db 写入 ──────────────────────────────────────────

REQUIRED_RESEARCH_FIELDS = [
    "company_type", "location", "company_def", "founder_name", "founder_edu",
    "founder_bg", "founder_achievement", "team_size", "team_highlight",
    "funding_info", "website_url", "timeline_events", "main_product_name",
    "main_product_def", "main_product_highlight", "main_product_achievement",
    "main_product_img_src", "other_products", "revenue_model", "gtm_strategy",
    "cold_start", "customer_segment", "growth_flywheel", "moat", "competitors",
    "market_opportunity", "hook_paragraph_1", "hook_paragraph_2", "hook_paragraph_3",
    "data_confidence",
]

COMPETITIVE_RESEARCH_FIELDS = [
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

RESEARCH_SAVE_FIELDS = REQUIRED_RESEARCH_FIELDS + COMPETITIVE_RESEARCH_FIELDS


def _ensure_research_schema(conn: sqlite3.Connection):
    """Migrate existing local research DB files to the current scoring schema."""
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(research)").fetchall()}
    columns = {
        "ai_model_dependency": "TEXT",
        "workflow_integration_level": "TEXT",
        "data_flywheel": "TEXT",
        "proprietary_data_asset": "TEXT",
        "incumbent_direct_competitor": "TEXT",
        "customer_segment_type": "TEXT",
        "funding_stage": "TEXT",
        "funding_stage_score": "REAL",
        "pricing_model": "TEXT",
        "inference_cost_exposure": "TEXT",
        "stack_layer": "TEXT",
        "score_defensibility": "REAL",
        "score_incumbent_attention": "REAL",
        "score_value_capture": "REAL",
    }
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE research ADD COLUMN {name} {definition}")


def save_research_records(db_path: str, records: list[dict]) -> list[int]:
    """保存多条研究记录到 research_db，返回插入的 ID 列表"""
    ids = []
    with get_db(db_path) as conn:
        _ensure_research_schema(conn)
        for rec in records:
            rec = dict(rec)
            for f in REQUIRED_RESEARCH_FIELDS:
                val = rec.get(f)
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    rec[f] = "暂缺"
                elif isinstance(val, (list, dict)):
                    rec[f] = json.dumps(val, ensure_ascii=False)

            normalized = normalize_fields(rec)
            rec.update(normalized)
            rec.update(compute_scores(rec))

            values = [rec.get("company_name", "未知"), rec.get("version", "unknown")]
            values += [rec.get(f, "暂缺") for f in RESEARCH_SAVE_FIELDS]
            placeholders = ",".join(["?"] * (len(RESEARCH_SAVE_FIELDS) + 2))
            cur = conn.execute(
                f"INSERT INTO research (company_name, version, {','.join(RESEARCH_SAVE_FIELDS)}) VALUES ({placeholders})",
                values,
            )
            ids.append(cur.lastrowid)
        conn.commit()
    return ids


# ── research_jobs 追踪 ──────────────────────────────────────────


def create_job(db_path: str, job_id: str, company_name: str, company_url: str):
    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO research_jobs (job_id, company_name, company_url, status, stage, detail)
               VALUES (?, ?, ?, 'running', '启动', '准备开始...')""",
            (job_id, company_name, company_url),
        )
        conn.commit()


def update_job(db_path: str, job_id: str, **kwargs):
    if not kwargs:
        return
    sets = [f"{k}=?" for k in kwargs]
    values = list(kwargs.values()) + [job_id]
    with get_db(db_path) as conn:
        conn.execute(
            f"UPDATE research_jobs SET {','.join(sets)}, updated_at=CURRENT_TIMESTAMP WHERE job_id=?",
            values,
        )
        conn.commit()


def get_job(db_path: str, job_id: str) -> dict | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM research_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        return dict(row) if row else None


def get_latest_running_job(db_path: str) -> dict | None:
    """返回最近一条 running/cancelling 状态的 job，用于页面刷新恢复。"""
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM research_jobs
               WHERE status IN ('running', 'cancelling')
               ORDER BY created_at DESC LIMIT 1"""
        ).fetchone()
        return dict(row) if row else None


# ── final_db 读写 ─────────────────────────────────────────────


def _ensure_final_unique_index(conn: sqlite3.Connection):
    """清理历史重复字段，并确保定稿字段可按公司+卡片+字段更新。"""
    duplicates = conn.execute(
        """SELECT company_name, card_index, field_name, MAX(id) AS keep_id, COUNT(*) AS count
           FROM final_content
           GROUP BY company_name, card_index, field_name
           HAVING count > 1"""
    ).fetchall()
    for row in duplicates:
        conn.execute(
            """DELETE FROM final_content
               WHERE company_name=? AND card_index=? AND field_name=? AND id<>?""",
            (row["company_name"], row["card_index"], row["field_name"], row["keep_id"]),
        )

    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_final_unique_field
           ON final_content(company_name, card_index, field_name)"""
    )


def save_final_card(
    db_path: str,
    company_name: str,
    card_index: int,
    fields: dict[str, str],
    img_paths: dict[str, str] = None,
):
    """保存单张卡片字段到 final_db（UPSERT）"""
    img_paths = img_paths or {}
    with get_db(db_path) as conn:
        _ensure_final_unique_index(conn)
        for field_name, field_value in fields.items():
            img_local_path = img_paths.get(field_name)
            conn.execute(
                """INSERT INTO final_content (company_name, card_index, field_name, field_value, img_local_path)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(company_name, card_index, field_name) DO UPDATE SET
                     field_value=excluded.field_value,
                     img_local_path=COALESCE(excluded.img_local_path, final_content.img_local_path),
                     confirmed_at=CURRENT_TIMESTAMP""",
                (company_name, card_index, field_name, field_value, img_local_path),
            )
        conn.commit()


def save_final_markdown(db_path: str, company_name: str, card_index: int, markdown_content: str):
    """保存单张卡片的整块 Markdown。"""
    save_final_card(db_path, company_name, card_index, {"markdown_full": markdown_content})


def get_final_card_markdown(db_path: str, company_name: str, card_index: int) -> str | None:
    """读取单张卡片已定稿的 markdown_full"""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT field_value FROM final_content WHERE company_name=? AND card_index=? AND field_name='markdown_full'",
            (company_name, card_index),
        ).fetchone()
        return row["field_value"] if row else None


def get_final_status(db_path: str, company_name: str) -> dict:
    cards = get_final_cards(db_path, company_name)
    confirmed = sorted({c["card_index"] for c in cards if c["field_name"] == "markdown_full"} or
                       {c["card_index"] for c in cards})
    return {"company_name": company_name, "confirmed": confirmed, "total": 8}


def get_final_cards(db_path: str, company_name: str) -> list[dict]:
    """读取某公司所有已确认卡片，按 card_index 排序"""
    with get_db(db_path) as conn:
        _ensure_final_unique_index(conn)
        conn.commit()
        rows = conn.execute(
            "SELECT * FROM final_content WHERE company_name=? ORDER BY card_index, id",
            (company_name,),
        ).fetchall()
        return [dict(row) for row in rows]


def export_json(db_path: str, company_name: str) -> dict | None:
    """导出结构化 JSON，供 canvas 直接消费"""
    cards = get_final_cards(db_path, company_name)
    if not cards:
        return None

    result: dict[str, dict] = {}
    for c in cards:
        ci = str(c["card_index"])
        if ci not in result:
            result[ci] = {"fields": {}, "img_paths": {}}
        if c["field_name"] == "markdown_full":
            result[ci]["markdown_content"] = c["field_value"] or ""
        else:
            result[ci]["fields"][c["field_name"]] = c["field_value"] or ""
        if c["img_local_path"]:
            result[ci]["img_paths"][c["field_name"]] = c["img_local_path"]

    return {
        "company_name": company_name,
        "cards": result,
        "confirmed_count": len(result),
    }


def _safe_image_dir_name(company_name: str) -> str:
    return safe_path_segment(company_name)


def delete_company(research_db_path: str, final_db_path: str, assets_db_path: str,
                  images_dir: str, company_name: str) -> dict:
    """真删除某公司全部数据：3个DB的5张表 + images目录。返回删除计数。"""
    counts = {}

    # research_db: research + research_jobs
    with get_db(research_db_path) as conn:
        cur = conn.execute("DELETE FROM research WHERE company_name=?", (company_name,))
        counts["research"] = cur.rowcount
        cur = conn.execute("DELETE FROM research_jobs WHERE company_name=?", (company_name,))
        counts["research_jobs"] = cur.rowcount
        conn.commit()

    # final_db: final_content
    with get_db(final_db_path) as conn:
        cur = conn.execute("DELETE FROM final_content WHERE company_name=?", (company_name,))
        counts["final_content"] = cur.rowcount
        conn.commit()

    # assets_db: image_variants + company_assets
    with get_db(assets_db_path) as conn:
        cur = conn.execute("DELETE FROM image_variants WHERE company_name=?", (company_name,))
        counts["image_variants"] = cur.rowcount
        cur = conn.execute("DELETE FROM company_assets WHERE company_name=?", (company_name,))
        counts["company_assets"] = cur.rowcount
        conn.commit()

    # images 目录
    base_dir = os.path.abspath(images_dir)
    img_dir = os.path.abspath(os.path.join(base_dir, _safe_image_dir_name(company_name)))
    if os.path.commonpath([base_dir, img_dir]) != base_dir:
        counts["images_dir"] = "路径越界，已跳过"
        return counts
    if os.path.exists(img_dir):
        shutil.rmtree(img_dir)
        counts["images_dir"] = "已删除"
    else:
        counts["images_dir"] = "不存在"

    return counts


def export_markdown(db_path: str, company_name: str) -> str:
    """从 final_db 导出完整 Markdown"""
    cards = get_final_cards(db_path, company_name)
    if not cards:
        return ""

    # 按卡片分组
    card_groups: dict[int, list[dict]] = {}
    for c in cards:
        card_groups.setdefault(c["card_index"], []).append(c)

    lines: list[str] = []
    card_titles = [
        "", "首页", "公司介绍", "发展沿袭",
        "产品线（主产品）", "其他产品", "商业模式", "竞争格局", "总结",
    ]

    for idx in range(1, 9):
        fields = card_groups.get(idx, [])
        if not fields:
            continue
        lines.append(f"## 卡片{idx}：{card_titles[idx]}")
        lines.append("")
        for f in fields:
            if f["field_name"] == "markdown_full":
                lines.append(f["field_value"] or "")
                continue
            label = f["field_name"]
            value = f["field_value"] or ""
            if f["img_local_path"]:
                lines.append(f"- **{label}**：{value}")
                lines.append(f"  ![图片]({f['img_local_path']})")
            else:
                lines.append(f"- **{label}**：{value}")
        lines.append("")

    return "\n".join(lines)
