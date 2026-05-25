from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager


@contextmanager
def get_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── research_db 查询 ──────────────────────────────────────────


def get_companies(db_path: str) -> list[dict]:
    """列出所有已研究公司"""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT company_name, MAX(created_at) as created_at "
            "FROM research GROUP BY company_name ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


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


def save_research_records(db_path: str, records: list[dict]) -> list[int]:
    """保存多条研究记录到 research_db，返回插入的 ID 列表"""
    ids = []
    with get_db(db_path) as conn:
        for rec in records:
            for f in REQUIRED_RESEARCH_FIELDS:
                val = rec.get(f)
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    rec[f] = "暂缺"
                elif isinstance(val, (list, dict)):
                    rec[f] = json.dumps(val, ensure_ascii=False)

            values = [rec.get("company_name", "未知"), rec.get("version", "unknown")]
            values += [rec.get(f, "暂缺") for f in REQUIRED_RESEARCH_FIELDS]
            placeholders = ",".join(["?"] * (len(REQUIRED_RESEARCH_FIELDS) + 2))
            cur = conn.execute(
                f"INSERT INTO research (company_name, version, {','.join(REQUIRED_RESEARCH_FIELDS)}) VALUES ({placeholders})",
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
        result[ci]["fields"][c["field_name"]] = c["field_value"] or ""
        if c["img_local_path"]:
            result[ci]["img_paths"][c["field_name"]] = c["img_local_path"]

    return {"company_name": company_name, "cards": result}


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
        "产品线（主产品）", "其他产品", "商业模式", "总结",
    ]

    for idx in range(1, 8):
        fields = card_groups.get(idx, [])
        if not fields:
            continue
        lines.append(f"## 卡片{idx}：{card_titles[idx]}")
        lines.append("")
        for f in fields:
            label = f["field_name"]
            value = f["field_value"] or ""
            if f["img_local_path"]:
                lines.append(f"- **{label}**：{value}")
                lines.append(f"  ![图片]({f['img_local_path']})")
            else:
                lines.append(f"- **{label}**：{value}")
        lines.append("")

    return "\n".join(lines)
