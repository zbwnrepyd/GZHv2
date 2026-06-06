from __future__ import annotations
from flask import Flask, request, jsonify, render_template, send_from_directory
from config import config
import db as database
from deepseek_client import call_deepseek, load_prompt
from image_client import generate_image
from firecrawl_local import scrape_url
from pipeline import PipelineCancelledError, run_pipeline
from asset_store import (
    init_assets_db, ensure_assets_rows, get_assets, upsert_asset,
    list_variants, insert_variant, select_variant, delete_variant,
    update_variant_scores,
)
from asset_resolver import resolve_company_assets
from asset_pipeline import (
    collect_all_assets, _download, _variant_path, _render_osm_map,
    _company_image_dir, _image_url_path, _variant_url_path,
    _resolve_office_location, _geocode_search_text,
)
from infographic import (
    generate_flywheel_from_markdown, generate_timeline_from_markdown,
    render_with_template, extract_flywheel_json, extract_timeline_json,
    build_competitive_landscape_svg, build_stack_positioning_svg,
    render_competitive_landscape, render_stack_positioning, _html_to_png,
    _echarts_inline_js,
)
from infographic_templates import get_all as get_all_templates, get as get_template, upload as upload_template, delete as delete_template
from image_search import search_images
from image_candidate import ImageCandidate
from image_scorer import score_candidate
from image_quality import inspect_local_image, validate_candidate
import markdown_builder
import json
import os
import re
import time
import uuid
import threading
from pathlib import Path

app = Flask(__name__)
app.config.from_object(config)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 确保图片目录存在
Path(config.IMAGES_DIR).mkdir(parents=True, exist_ok=True)

# 初始化资产数据库
init_assets_db(config.DB_PATH_ASSETS)


def _init_new_composition_dbs():
    """幂等初始化编排数据库和模板数据库（Step 1 新增）"""
    import importlib.util as _importlib_util
    import sqlite3 as _sqlite3
    from pathlib import Path as _P

    project_db_dir = _P(__file__).resolve().parent.parent / "db"

    def _exec_sql_file(db_path: str, sql_filename: str):
        sql_file = project_db_dir / sql_filename
        if not sql_file.exists():
            return
        conn = _sqlite3.connect(db_path)
        conn.executescript(sql_file.read_text())
        conn.commit()
        conn.close()

    def _run_migrations(db_path: str, names: list[str]):
        migrate_file = project_db_dir / "migrate.py"
        if not migrate_file.exists():
            return
        spec = _importlib_util.spec_from_file_location("gzh_db_migrate", migrate_file)
        module = _importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.run_migrations(db_path, project_db_dir / "migrations", names=names)

    # composition_db — 卡片编排
    _exec_sql_file(config.DB_PATH_COMPOSITION, "init_composition_db.sql")

    # template_db — 模板系统
    _exec_sql_file(config.DB_PATH_TEMPLATE, "init_template_db.sql")

    # 迁移：research_fields 写入 research_db
    _run_migrations(config.DB_PATH_RESEARCH, ["001_research_fields.sql"])

    # 迁移：final_fields 写入 final_db
    _run_migrations(config.DB_PATH_FINAL, ["002_final_fields.sql"])


# 初始化新数据库（幂等，失败不阻塞 import）
try:
    _init_new_composition_dbs()
    database.ensure_research_schema_once(config.DB_PATH_RESEARCH)
except Exception as e:
    import logging
    logging.warning("composition/template DB init skipped: %s", e)


def _quality_kwargs_for_variant(company: str, asset_key: str, local_file: str,
                                source_type: str, source_url: str = "",
                                source_page: str = "", prompt: str = "",
                                author: str = "", license_text: str = "") -> dict:
    candidate = ImageCandidate(
        company_name=company,
        asset_key=asset_key,
        image_url=source_url or local_file,
        source_page=source_page,
        source_type=source_type,
        title=prompt,
        alt_text=author,
        author=author,
        license=license_text,
        local_path=local_file,
    )
    inspect_local_image(candidate)
    passed, reason = validate_candidate(candidate)
    if passed:
        score_candidate(candidate, product_names=[company])
    else:
        candidate.reject_reason = reason
    return {
        "width": candidate.width,
        "height": candidate.height,
        "file_size": candidate.file_size,
        "aspect_ratio": candidate.aspect_ratio,
        "quality_score": candidate.quality_score,
        "relevance_score": candidate.relevance_score,
        "source_score": candidate.source_score,
        "final_score": candidate.final_score,
        "reject_reason": candidate.reject_reason,
        "meta": candidate.meta,
    }


def _local_file_from_browser_path(path: str) -> str:
    """将浏览器 /images/... 路径映射到本地文件系统路径，防止路径遍历攻击。"""
    if not path or not path.startswith("/images/"):
        return path or ""
    rel = path[len("/images/"):]
    base = Path(config.IMAGES_DIR).resolve()
    target = (base / rel).resolve()
    if target != base and base not in target.parents:
        return ""
    return str(target)

# 后台任务状态
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


# ── API：公司列表 ─────────────────────────────────────────────

@app.route("/api/companies")
def list_companies():
    try:
        companies = database.get_companies(config.DB_PATH_RESEARCH, config.DB_PATH_FINAL)
        return jsonify(companies)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API：读取研究数据 ─────────────────────────────────────────

@app.route("/api/research/<company>/<version>")
def get_research(company: str, version: str):
    if version not in ("standard", "business", "spread"):
        return jsonify({"error": f"无效的版本: {version}"}), 400
    try:
        data = database.get_research(config.DB_PATH_RESEARCH, company, version)
        if not data:
            return jsonify({"error": "公司或版本不存在"}), 404
        # 移除 SQLite 内部字段
        data.pop("id", None)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/research/<company>")
def get_all_versions(company: str):
    try:
        versions = database.get_all_versions(config.DB_PATH_RESEARCH, company)
        # 清理内部字段
        for v in versions.values():
            v.pop("id", None)
        return jsonify(versions)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/research/<company>/card/<int:card_index>")
def get_research_card_markdown(company: str, card_index: int):
    if card_index < 1 or card_index > 8:
        return jsonify({"error": "card_index 必须在 1-8 之间"}), 400
    version = request.args.get("version", "standard")
    if version not in ("standard", "business", "spread"):
        return jsonify({"error": f"无效的版本: {version}"}), 400
    try:
        markdown = markdown_builder.build_card_markdown(
            config.DB_PATH_RESEARCH, company, card_index, version
        )
        if not markdown:
            return jsonify({"error": "公司或版本不存在"}), 404
        return jsonify({"company_name": company, "card_index": card_index, "version": version, "markdown": markdown})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API：保存研究数据（legacy 兼容） ──────────────────────────


@app.route("/api/research/save", methods=["POST"])
def save_research():
    try:
        data = request.get_json()
        if not data or not isinstance(data, list):
            return jsonify({"error": "请求体应为记录数组"}), 400
        for i, rec in enumerate(data):
            if not isinstance(rec, dict):
                return jsonify({"error": f"记录 {i} 应为对象"}), 400
            if not rec.get("company_name", "").strip():
                return jsonify({"error": f"记录 {i} 缺少 company_name"}), 400
            if not rec.get("version", "").strip():
                return jsonify({"error": f"记录 {i} 缺少 version"}), 400
        ids = database.save_research_records(config.DB_PATH_RESEARCH, data)
        return jsonify({"status": "ok", "record_ids": ids, "count": len(ids)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API：启动研究流水线 ──────────────────────────────────────


def _run_pipeline_job(job_id: str, company_name: str, company_url: str):
    database.create_job(config.DB_PATH_RESEARCH, job_id, company_name, company_url)

    def on_progress(stage: str, detail: str):
        message = detail.get("message", "") if isinstance(detail, dict) else detail
        sources = detail.get("sources") if isinstance(detail, dict) else None
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["stage"] = stage
                _jobs[job_id]["detail"] = message
                if sources is not None:
                    _jobs[job_id]["sources"] = sources
                # 累积阶段历史
                stages = _jobs[job_id].setdefault("stages", [])
                if not stages or stages[-1]["stage"] != stage:
                    stages.append({"stage": stage, "detail": message, "ts": time.time()})
                else:
                    stages[-1]["detail"] = message
                    stages[-1]["ts"] = time.time()

    def cancel_token():
        with _jobs_lock:
            return bool(_jobs.get(job_id, {}).get("cancelled", False))

    try:
        ids = run_pipeline(
            company_name, company_url,
            progress_callback=on_progress,
            job_id=job_id,
            cancel_token=cancel_token,
        )
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["record_ids"] = ids
                _jobs[job_id]["stage"] = "完成"
                _jobs[job_id]["detail"] = f"共 {len(ids)} 条记录"
        database.update_job(config.DB_PATH_RESEARCH, job_id,
                            status="done", record_ids=json.dumps(ids),
                            stage="完成", detail=f"共 {len(ids)} 条记录")

        threading.Thread(target=_collect_assets_silently, args=(company_name,), daemon=True).start()
    except PipelineCancelledError:
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "cancelled"
                _jobs[job_id]["stage"] = "已停止"
                _jobs[job_id]["detail"] = "用户已停止研究"
        database.update_job(config.DB_PATH_RESEARCH, job_id,
                            status="cancelled", stage="已停止", detail="用户已停止研究")
    except Exception as e:
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = str(e)
        database.update_job(config.DB_PATH_RESEARCH, job_id,
                            status="failed", error=str(e),
                            stage="失败", detail=str(e)[:200])


def _collect_assets_silently(company_name: str):
    """研究完成后仅自动采集 Logo（其余图片已由流水线图片采集阶段处理）。"""
    try:
        research = database.get_research(config.DB_PATH_RESEARCH, company_name, "standard")
        if not research:
            return
        company_url = research.get("website_url", "")
        website_url = research.get("website_url", "")
        from asset_pipeline import collect_logo, ensure_assets_rows
        ensure_assets_rows(config.DB_PATH_ASSETS, company_name)
        collect_logo(config.DB_PATH_ASSETS, config.IMAGES_DIR, company_name,
                     company_url, website_url)
    except Exception:
        pass


def _pre_extract_svg_data(company_name: str, card_index: int):
    """从定稿卡片 Markdown 预提取飞轮/时间线结构化 JSON，缓存到资产 meta 中。"""
    try:
        asset_key = "timeline" if card_index == 3 else "flywheel"
        markdown = database.get_final_card_markdown(config.DB_PATH_FINAL, company_name, card_index)
        if not markdown:
            return

        def ds_call(sys_prompt, usr_msg, **kw):
            return call_deepseek(
                config.DEEPSEEK_API_KEY, sys_prompt, usr_msg,
                model=config.DEEPSEEK_MODEL, **kw
            )

        data = None
        if asset_key == "flywheel":
            data = extract_flywheel_json(markdown, ds_call)
        else:
            data = extract_timeline_json(markdown, ds_call)

        if data:
            upsert_asset(config.DB_PATH_ASSETS, company_name, asset_key,
                        meta={"svg_data": data, "cached_at": time.time()})
    except Exception:
        pass  # 静默失败，不影响定稿保存


def _fallback_svg_data(asset_key: str, markdown: str) -> dict | None:
    """Best-effort parser used when LLM extraction fails."""
    lines = [line.strip() for line in (markdown or "").splitlines() if line.strip()]
    if asset_key == "timeline":
        events = []
        for line in lines:
            match = re.match(
                r"^[-*]\s*(?:\*\*)?([12]\d{3}(?:[-./年]\d{1,2})?)(?:\*\*)?\s*[:：\-—]?\s*(.+)$",
                line,
            )
            if not match:
                continue
            year = match.group(1).replace("年", "")
            text = re.sub(r"\*+", "", match.group(2)).strip(" -—:：")
            parts = re.split(r"\s+[—-]\s+|[。；;]", text, maxsplit=1)
            title = (parts[0].strip() or year)[:18]
            desc = (parts[1].strip() if len(parts) > 1 else text)[:80]
            events.append({"year": year, "title": title, "desc": desc})
            if len(events) >= 6:
                break
        return {"events": events} if events else None

    if asset_key == "flywheel":
        stages = []
        for line in lines:
            match = re.match(r"^(?:[-*]\s*)?\*\*([^*：:]{2,14})\*\*[：:]\s*(.+)$", line)
            if not match:
                match = re.match(r"^(?:[-*]\s*)?([^：:]{2,14})[：:]\s*(.+)$", line)
            if not match:
                continue
            label = re.sub(r"\*+", "", match.group(1)).strip()
            desc = re.sub(r"\*+", "", match.group(2)).strip()
            if label in {"卡片6", "商业模式", "增长飞轮"}:
                continue
            stages.append({"label": label[:8], "desc": desc[:60]})
            if len(stages) >= 5:
                break
        return {"center": "增长飞轮", "stages": stages} if len(stages) >= 2 else None

    return None


def _generate_card7_charts(company_name: str):
    """卡片7确认后自动生成竞争格局图 + 产业链生态位图（后台线程）"""
    try:
        init_assets_db(config.DB_PATH_ASSETS)
        ensure_assets_rows(config.DB_PATH_ASSETS, company_name)
        companies = _load_all_scored_companies(config.DB_PATH_RESEARCH)
        dest_dir = _company_image_dir(config.IMAGES_DIR, company_name)
        os.makedirs(dest_dir, exist_ok=True)

        chart_tasks = [
            ("chart_competitive", "competitive_landscape"),
            ("chart_ecosystem", "stack_positioning"),
        ]
        for asset_key, _chart_type in chart_tasks:
            try:
                dest = os.path.join(dest_dir, f"{asset_key}.png")
                if asset_key == "chart_competitive":
                    ok = render_competitive_landscape(companies, company_name, dest)
                else:
                    ok = render_stack_positioning(companies, company_name, dest)
                if ok:
                    upsert_asset(config.DB_PATH_ASSETS, company_name, asset_key,
                                local_path=_image_url_path(company_name, f"{asset_key}.png"),
                                source_type="svg_render", status="ready")
            except Exception:
                pass  # 单张图失败不影响另一张
    except Exception:
        pass  # 静默失败，用户可在图片定稿台手动生成


def _load_all_scored_companies(research_db_path: str) -> list[dict]:
    """加载所有有评分的公司数据（用于散点图）"""
    import sqlite3
    conn = sqlite3.connect(research_db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT DISTINCT company_name, score_defensibility, score_incumbent_attention, "
        "score_value_capture, funding_stage_score, stack_layer "
        "FROM research WHERE version='standard' "
        "AND score_defensibility IS NOT NULL AND score_value_capture IS NOT NULL"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _default_chart_params(asset_key: str) -> dict:
    """Default editable params for generated chart demands."""
    base = {
        "theme": "dark",
        "accent_color": "#29B8D4",
        "title_size": 16,
        "axis_size": 12,
        "label_size": 10,
        "point_size": 10,
        "show_label": True,
        "subtitle": "",
        "note": "",
        "width": 800,
        "height": 600,
    }
    if asset_key == "chart_competitive":
        base.update({
            "title": "AI 创业公司竞争格局图",
            "x_label": "Defensibility",
            "y_label": "Incumbent Attention",
            "x_split": 5,
            "y_split": 5,
            "quadrant_tl": "Sweet Spot",
            "quadrant_tr": "Kill Zone",
            "quadrant_bl": "Waiting Room",
            "quadrant_br": "Battlefield",
            "bubble_min": 8,
            "bubble_max": 42,
        })
    elif asset_key == "chart_ecosystem":
        base.update({
            "title": "AI 产业链生态位图",
            "x_label": "Stack Layer",
            "y_label": "Value Capture",
            "value_threshold": 7,
            "stack_labels": ["基础设施", "基础模型", "中间件", "垂直应用", "分发渠道"],
            "stack_colors": ["#4FC3F7", "#BA68C8", "#FFB74D", "#81C784", "#E57373"],
            "jitter": 0.16,
        })
    elif asset_key == "flywheel":
        base.update({
            "title": "飞轮图",
            "template_id": "flywheel_circular",
            "radius": 200,
            "node_radius": 48,
            "arrow_curve": 40,
            "label_size": 16,
            "desc_size": 12,
            "show_desc": True,
        })
    elif asset_key == "timeline":
        base.update({
            "title": "时间线图",
            "template_id": "timeline_left_axis",
            "row_h": 90,
            "axis_x": 160,
            "node_size": 6,
            "title_size": 18,
            "desc_size": 13,
            "wrap_text": True,
        })
    return base


def _chart_type_for_asset(asset_key: str) -> str:
    return {
        "chart_competitive": "competitive_landscape",
        "chart_ecosystem": "stack_positioning",
        "flywheel": "flywheel",
        "timeline": "timeline",
    }.get(asset_key, "")


def _load_svg_data(company: str, asset_key: str, markdown: str) -> tuple[dict | None, bool]:
    existing = get_assets(config.DB_PATH_ASSETS, company).get(asset_key)
    cached = (existing or {}).get("meta", {}).get("svg_data")
    if cached:
        return cached, True

    def ds_call(sys, usr, **kw):
        return call_deepseek(
            config.DEEPSEEK_API_KEY, sys, usr,
            model=config.DEEPSEEK_MODEL, **kw
        )

    data = None
    try:
        if asset_key == "flywheel":
            data = extract_flywheel_json(markdown, ds_call)
        else:
            data = extract_timeline_json(markdown, ds_call)
    except Exception:
        data = None

    if not data:
        data = _fallback_svg_data(asset_key, markdown)

    if data:
        upsert_asset(config.DB_PATH_ASSETS, company, asset_key,
                    meta={"svg_data": data, "cached_at": time.time()})
    return data, False


@app.route("/api/research/start", methods=["POST"])
def start_research():
    try:
        data = request.get_json(silent=True) or {}
        company_name = data.get("company_name", "").strip()
        company_url = data.get("company_url", "").strip()
        if not company_name or not company_url:
            return jsonify({"error": "缺少 company_name 或 company_url"}), 400

        job_id = str(uuid.uuid4())[:8]
        with _jobs_lock:
            _jobs[job_id] = {
                "job_id": job_id,
                "company_name": company_name,
                "status": "running",
                "stage": "启动",
                "detail": "准备开始...",
                "record_ids": None,
                "sources": {},
                "started_at": time.time(),
            }

        t = threading.Thread(target=_run_pipeline_job,
                             args=(job_id, company_name, company_url), daemon=True)
        t.start()

        return jsonify({"job_id": job_id, "status": "running"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/research/status/<job_id>")
def get_research_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        db_job = database.get_job(config.DB_PATH_RESEARCH, job_id)
        if db_job:
            return jsonify(db_job)
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(job)


@app.route("/api/research/running")
def get_running_research():
    """返回当前正在运行的研究任务（用于页面刷新后恢复轮询）。"""
    with _jobs_lock:
        running = [
            j for j in _jobs.values()
            if j.get("status") in ("running", "cancelling")
        ]
    if running:
        return jsonify(sorted(
            running,
            key=lambda x: x.get("started_at", 0),
            reverse=True,
        )[0])
    while True:
        db_job = database.get_latest_running_job(config.DB_PATH_RESEARCH)
        if not db_job:
            break
        database.update_job(
            config.DB_PATH_RESEARCH,
            db_job["job_id"],
            status="cancelled",
            stage="已停止",
            detail="服务重启后任务已失效",
        )
    return jsonify({"status": "none"})


@app.route("/api/research/stop/<job_id>", methods=["POST"])
def stop_research(job_id: str):
    """标记取消，pipeline 在下一个 checkpoint 检测到后优雅退出。"""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            db_job = database.get_job(config.DB_PATH_RESEARCH, job_id)
            if not db_job:
                return jsonify({"error": "任务不存在或已完成"}), 404
            if db_job.get("status") not in ("running", "cancelling"):
                return jsonify({"error": f"任务状态为 {db_job.get('status')}，无法停止"}), 409
            database.update_job(
                config.DB_PATH_RESEARCH, job_id,
                status="cancelled", stage="已停止", detail="用户已停止研究"
            )
            return jsonify({"status": "ok"})
        if job.get("status") != "running":
            return jsonify({"error": f"任务状态为 {job.get('status')}，无法停止"}), 409
        job["cancelled"] = True
        job["status"] = "cancelling"
        job["stage"] = "正在停止"
        job["detail"] = "等待当前步骤完成..."
    database.update_job(
        config.DB_PATH_RESEARCH, job_id,
        status="cancelling", stage="正在停止", detail="等待当前步骤完成..."
    )
    return jsonify({"status": "ok"})


# ── API：保存定稿 ─────────────────────────────────────────────

@app.route("/api/final/save", methods=["POST"])
def save_final_card():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "请求体为空"}), 400

        company_name = data.get("company_name")
        card_index = data.get("card_index")
        markdown_content = data.get("markdown_content")
        fields = data.get("fields", {})
        img_paths = data.get("img_paths", {})

        if not company_name or not card_index:
            return jsonify({"error": "缺少 company_name 或 card_index"}), 400
        if card_index < 1 or card_index > 8:
            return jsonify({"error": "card_index 必须在 1-8 之间"}), 400

        if markdown_content is not None:
            database.save_final_markdown(
                config.DB_PATH_FINAL, company_name, card_index, markdown_content
            )
        else:
            database.save_final_card(
                config.DB_PATH_FINAL, company_name, card_index, fields, img_paths
            )

        # 预提取 SVG 数据（卡片3=timeline, 卡片6=flywheel）
        if card_index in (3, 6):
            _pre_extract_svg_data(company_name, card_index)

        # 卡片7确认时自动生成竞争格局图 + 产业链生态位图
        if card_index == 7:
            threading.Thread(target=_generate_card7_charts,
                           args=(company_name,), daemon=True).start()

        return jsonify({"status": "ok", "card_index": card_index})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/final/status/<company>")
def get_final_status(company: str):
    try:
        return jsonify(database.get_final_status(config.DB_PATH_FINAL, company))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/final/card/<company>/<int:card_index>")
def get_final_card(company: str, card_index: int):
    try:
        markdown = database.get_final_card_markdown(config.DB_PATH_FINAL, company, card_index)
        if markdown is None:
            return jsonify({"company_name": company, "card_index": card_index, "markdown_content": ""})
        return jsonify({"company_name": company, "card_index": card_index, "markdown_content": markdown})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API：导出 Markdown ────────────────────────────────────────

@app.route("/api/final/export/<company>")
def export_company(company: str):
    try:
        fmt = request.args.get("format", "markdown")
        if fmt == "json":
            data = database.export_json(config.DB_PATH_FINAL, company)
            if not data:
                return jsonify({"error": "该公司没有已确认的卡片"}), 404
            return jsonify(data)

        markdown = database.export_markdown(config.DB_PATH_FINAL, company)
        if not markdown:
            return jsonify({"error": "该公司没有已确认的卡片"}), 404
        return jsonify({"company_name": company, "markdown": markdown})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API：AI 图片生成 ──────────────────────────────────────────

@app.route("/api/generate-image", methods=["POST"])
def generate_image_route():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        company_name = data.get("company_name", "unknown")
        field_name = data.get("field_name", "image")
        asset_key = data.get("asset_key", "")  # 可选：写入 company_assets
        image_api_url = (data.get("image_api_url") or "").strip() or None
        image_api_key = (data.get("image_api_key") or "").strip() or None

        if not prompt:
            return jsonify({"error": "缺少 prompt"}), 400

        safe_name = company_name.replace("/", "_").replace(" ", "_")
        filename = f"{safe_name}_{field_name}_{int(time.time())}.png"
        path = generate_image(
            prompt,
            config.IMAGES_DIR,
            filename,
            api_url=image_api_url,
            api_key=image_api_key,
        )
        img_path = f"/images/{Path(path).name}"

        # 如果指定了 asset_key，写入资产表
        if asset_key:
            init_assets_db(config.DB_PATH_ASSETS)
            ensure_assets_rows(config.DB_PATH_ASSETS, company_name)
            variant_id = insert_variant(
                config.DB_PATH_ASSETS,
                company_name,
                asset_key,
                local_path=img_path,
                source_type="api_generate",
                source_url="",
                author="AI Generated",
                license="AI",
                prompt=prompt,
                **_quality_kwargs_for_variant(
                    company_name, asset_key, path, "api_generate",
                    prompt=prompt, author="AI Generated", license_text="AI",
                ),
            )
            select_variant(config.DB_PATH_ASSETS, company_name, asset_key, variant_id)

        return jsonify({"status": "ok", "img_path": img_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/images/<path:filename>")
def image_assets(filename):
    return send_from_directory(config.IMAGES_DIR, filename)


# ── API：资产系统 ──────────────────────────────────────────────

@app.route("/api/assets/resolved")
def get_resolved_assets():
    """Return layout-ready card assets through the stable resolver contract."""
    company = (request.args.get("company") or request.args.get("company_name") or "").strip()
    if not company:
        return jsonify({"error": "缺少 company 参数"}), 400
    try:
        init_assets_db(config.DB_PATH_ASSETS)
        ensure_assets_rows(config.DB_PATH_ASSETS, company)
        return jsonify(resolve_company_assets(config.DB_PATH_ASSETS, company))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/assets/<company>")
def get_company_assets(company: str):
    """获取某公司全部资产"""
    try:
        assets = get_assets(config.DB_PATH_ASSETS, company)
        return jsonify({"company_name": company, "assets": assets})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/assets/collect/<company>", methods=["POST"])
def collect_assets(company: str):
    """触发自动采集。可选 ?asset_key=office 只采集单个槽位。"""
    try:
        # 从 research DB 获取公司数据
        research = database.get_research(config.DB_PATH_RESEARCH, company, "standard")
        if not research:
            return jsonify({"error": f"未找到公司 {company} 的研究数据"}), 404

        asset_key = request.args.get("asset_key", "").strip()

        company_data = {
            "company_url": research.get("website_url", ""),
            "website_url": research.get("website_url", ""),
            "location": research.get("location", ""),
            "other_products": research.get("other_products", ""),
            "competitors": research.get("competitors", ""),
        }

        images_root = config.IMAGES_DIR
        from asset_pipeline import collect_image_variants_pipeline
        results = collect_image_variants_pipeline(
            config.DB_PATH_ASSETS, images_root, company, company_data,
            asset_key=asset_key or "",
        )
        return jsonify({"status": "ok", "company_name": company, "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/assets/generate/<company>/<asset_key>", methods=["POST"])
def generate_asset(company: str, asset_key: str):
    """生成信息图（flywheel / timeline / chart_competitive / chart_ecosystem）"""
    if asset_key not in ("flywheel", "timeline", "chart_competitive", "chart_ecosystem"):
        return jsonify({"error": f"不支持的 asset_key: {asset_key}，仅支持 flywheel/timeline/chart_competitive/chart_ecosystem"}), 400

    try:
        ensure_assets_rows(config.DB_PATH_ASSETS, company)

        # 输出路径
        dest_dir = _company_image_dir(config.IMAGES_DIR, company)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"{asset_key}.png")

        # ── chart_competitive / chart_ecosystem：直接查库画散点图，无需 LLM ──
        if asset_key in ("chart_competitive", "chart_ecosystem"):
            companies = _load_all_scored_companies(config.DB_PATH_RESEARCH)
            if asset_key == "chart_competitive":
                ok = render_competitive_landscape(companies, company, dest)
            else:
                ok = render_stack_positioning(companies, company, dest)
            if not ok:
                upsert_asset(config.DB_PATH_ASSETS, company, asset_key, status="failed",
                            meta={"error": "散点图渲染失败"})
                return jsonify({"error": "生成失败"}), 500
            upsert_asset(config.DB_PATH_ASSETS, company, asset_key,
                        local_path=_image_url_path(company, f"{asset_key}.png"),
                        source_type="svg_render", status="ready")
            return jsonify({
                "status": "ok",
                "company_name": company,
                "asset_key": asset_key,
                "local_path": _image_url_path(company, f"{asset_key}.png"),
            })

        # ── flywheel / timeline：需要 markdown + LLM 提取 ──
        card_index = 6 if asset_key == "flywheel" else 3
        markdown = database.get_final_card_markdown(config.DB_PATH_FINAL, company, card_index)
        if not markdown:
            return jsonify({"error": f"未找到公司 {company} 卡片 {card_index} 的定稿内容"}), 404

        # 包装 deepseek 调用
        def ds_call(system_prompt, user_message, temperature=0.1, max_tokens=2048):
            return call_deepseek(
                config.DEEPSEEK_API_KEY,
                system_prompt,
                user_message,
                model=config.DEEPSEEK_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        if asset_key == "flywheel":
            ok = generate_flywheel_from_markdown(markdown, dest, ds_call)
        else:
            ok = generate_timeline_from_markdown(markdown, dest, ds_call)

        if not ok:
            upsert_asset(config.DB_PATH_ASSETS, company, asset_key, status="failed",
                        meta={"error": "SVG 渲染失败或 LLM 提取失败"})
            return jsonify({"error": "生成失败"}), 500

        upsert_asset(config.DB_PATH_ASSETS, company, asset_key,
                    local_path=_image_url_path(company, f"{asset_key}.png"),
                    source_type="svg_render", status="ready")

        return jsonify({
            "status": "ok",
            "company_name": company,
            "asset_key": asset_key,
            "local_path": _image_url_path(company, f"{asset_key}.png"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API：网页抓取（本地 trafilatura） ─────────────────────────

@app.route("/api/scrape-website", methods=["POST"])
def scrape_website():
    try:
        data = request.get_json()
        url = data.get("url", "")
        if not url:
            return jsonify({"error": "缺少 url"}), 400
        result = scrape_url(url)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API：文本分段 ─────────────────────────────────────────────

@app.route("/api/split-text", methods=["POST"])
def split_text():
    try:
        data = request.get_json()
        text = data.get("text", "")
        segment_count = data.get("segment_count", 2)

        if not text:
            return jsonify({"error": "缺少文本"}), 400

        # 如果当前就是目标段数，直接返回
        current_paras = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(current_paras) == segment_count:
            return jsonify(
                {"status": "ok", "segments": current_paras, "already_split": True}
            )

        system_prompt = load_prompt("split-text").replace(
            "{{segment_count}}", str(segment_count)
        )
        result = call_deepseek(
            config.DEEPSEEK_API_KEY,
            system_prompt,
            text,
            model=config.DEEPSEEK_FLASH_MODEL,
            temperature=0.1,
            max_tokens=4096,
            timeout=60,
        )

        # 解析分段结果
        segments = []
        for line in result.split("\n"):
            stripped = line.strip()
            if stripped.startswith("## 第") or not stripped:
                continue
            segments.append(stripped)

        if not segments:
            segments = current_paras

        return jsonify({"status": "ok", "segments": segments})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/check/<company>")
def check_company_status(company: str):
    """检查公司卡片确认状态"""
    try:
        cards = database.get_final_cards(config.DB_PATH_FINAL, company)
        confirmed_cards = set()
        for c in cards:
            confirmed_cards.add(c["card_index"])
        return jsonify(
            {
                "company_name": company,
                "confirmed_cards": sorted(confirmed_cards),
                "total_confirmed": len(confirmed_cards),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API：SVG 模板管理 ───────────────────────────────────────────

@app.route("/api/svg-templates")
def list_svg_templates():
    """返回全部 SVG 模板的 META 列表"""
    try:
        templates = get_all_templates()
        return jsonify({"templates": templates})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/svg-templates/upload", methods=["POST"])
def upload_svg_template():
    """上传用户自定义模板 .py 文件"""
    try:
        if not _is_local_request():
            return jsonify({"error": "Python 模板上传仅允许本机请求"}), 403
        if request.headers.get("X-Template-Upload-Intent") != "local-dev":
            return jsonify({"error": "缺少 Python 模板上传意图 header"}), 403
        if "file" not in request.files:
            return jsonify({"error": "缺少 file"}), 400
        f = request.files["file"]
        if not f.filename:
            return jsonify({"error": "文件名为空"}), 400
        content = f.read()
        meta = upload_template(f.filename, content)
        return jsonify({"meta": meta})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _is_local_request() -> bool:
    remote_addr = request.remote_addr or ""
    return remote_addr == "::1" or remote_addr == "localhost" or remote_addr.startswith("127.")


@app.route("/api/svg-templates/<template_id>", methods=["DELETE"])
def delete_svg_template(template_id: str):
    """删除用户上传的模板（内置模板不可删）"""
    try:
        ok = delete_template(template_id)
        if not ok:
            return jsonify({"error": "模板不存在或为内置模板不可删除"}), 400
        return jsonify({"deleted": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/preview", methods=["POST"])
def preview_chart_html(company: str, asset_key: str):
    """返回图表 HTML 字符串供前端 iframe srcdoc 实时预览（不经过 Playwright）"""
    if asset_key not in ("chart_competitive", "chart_ecosystem"):
        return jsonify({"error": "仅支持 chart_competitive / chart_ecosystem"}), 400

    try:
        body = request.get_json() or {}
        params = _default_chart_params(asset_key)
        params.update(body.get("params", {}) or {})
        companies = _load_all_scored_companies(config.DB_PATH_RESEARCH)
        if asset_key == "chart_competitive":
            html = build_competitive_landscape_svg(companies, company, params)
        else:
            html = build_stack_positioning_svg(companies, company, params)
        return app.response_class(html, mimetype="text/html")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/chart-data", methods=["POST"])
def get_generated_chart_data(company: str, asset_key: str):
    """返回生成图的可编辑数据结构，供参数检查器使用。"""
    if asset_key not in ("chart_competitive", "chart_ecosystem", "flywheel", "timeline"):
        return jsonify({"error": "仅支持生成图 asset_key"}), 400

    try:
        params = _default_chart_params(asset_key)
        payload = {
            "company_name": company,
            "asset_key": asset_key,
            "chart_type": _chart_type_for_asset(asset_key),
            "params": params,
            "companies": [],
            "data": {},
            "templates": [],
        }

        if asset_key in ("chart_competitive", "chart_ecosystem"):
            companies = _load_all_scored_companies(config.DB_PATH_RESEARCH)
            payload["companies"] = companies
            payload["data"] = {
                "highlight": company,
                "has_highlight": any(c.get("company_name") == company for c in companies),
            }
            return jsonify(payload)

        card_index = 6 if asset_key == "flywheel" else 3
        markdown = database.get_final_card_markdown(config.DB_PATH_FINAL, company, card_index)
        data = {}
        cached = False
        if markdown:
            data, cached = _load_svg_data(company, asset_key, markdown)
        payload["data"] = data or {}
        payload["cached"] = cached
        payload["templates"] = [t for t in get_all_templates() if t.get("asset_key") == asset_key]
        return jsonify(payload)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/svg-templates/preview", methods=["POST"])
def preview_svg_template():
    """用指定模板+参数+数据渲染纯 SVG（不截图），返回 SVG 字符串供前端实时预览"""
    try:
        body = request.get_json()
        template_id = body.get("template_id", "")
        params = body.get("params", {})
        data = body.get("data", {})

        if not template_id:
            return jsonify({"error": "缺少 template_id"}), 400

        m = get_template(template_id)
        if not m:
            return jsonify({"error": f"模板 {template_id!r} 不存在"}), 404

        svg = m.build(data, params)
        return app.response_class(svg, mimetype="image/svg+xml")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 编辑器页面 ─────────────────────────────────────────────────

@app.route("/editor")
@app.route("/editor/")
@app.route("/editor/<company>")
def editor_page(company: str = None):
    return render_template("editor.html")


@app.route("/api/research/<company>", methods=["DELETE"])
def delete_company(company: str):
    """真删除某公司全部研究数据"""
    try:
        counts = database.delete_company(
            config.DB_PATH_RESEARCH,
            config.DB_PATH_FINAL,
            config.DB_PATH_ASSETS,
            config.IMAGES_DIR,
            company,
        )
        return jsonify({"company_name": company, "deleted": counts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/canvas/")
def canvas_page():
    return send_from_directory("../canvas", "card-renderer.html")


@app.route("/canvas/card/<company>/<card_id>")
def canvas_card_page(company: str, card_id: str):
    if not card_id:
        return jsonify({"error": "缺少 card_id"}), 400
    return send_from_directory("../canvas", "card.html")


@app.route("/canvas/<path:filename>")
def canvas_assets(filename):
    # Validate each path segment against traversal (Flask send_from_directory also does safe_join internally)
    for part in filename.split("/"):
        if part in ("..", ".") or part.startswith(".."):
            return jsonify({"error": "非法路径"}), 400
    return send_from_directory("../canvas", filename)


# ── 图片定稿台 (image-studio v2) ─────────────────────────────────

@app.route("/image-studio/")
def image_studio_page():
    return send_from_directory("../image-studio", "index.html")


@app.route("/image-studio/<path:filename>")
def image_studio_assets(filename):
    for part in filename.split("/"):
        if part in ("..", ".") or part.startswith(".."):
            return jsonify({"error": "非法路径"}), 400
    return send_from_directory("../image-studio", filename)


# ── API：图片定稿台 ─────────────────────────────────────────────

@app.route("/api/image-studio/<company>")
def get_image_studio_overview(company: str):
    """返回全部槽位概览"""
    try:
        init_assets_db(config.DB_PATH_ASSETS)
        ensure_assets_rows(config.DB_PATH_ASSETS, company)
        assets = get_assets(config.DB_PATH_ASSETS, company)

        slots = []
        for asset_key in ["logo", "website_screenshot", "office", "product_main",
                          "products_other", "competitors", "competitors_logo_strip",
                          "chart_competitive", "chart_ecosystem",
                          "flywheel", "timeline"]:
            asset = assets.get(asset_key, {})
            variants = list_variants(config.DB_PATH_ASSETS, company, asset_key)
            selected = next((v for v in variants if v.get("is_selected")), None)
            slots.append({
                "asset_key": asset_key,
                "card_index": asset.get("card_index", 0),
                "status": asset.get("status", "missing"),
                "local_path": asset.get("local_path", ""),
                "source_type": asset.get("source_type", ""),
                "variant_count": len(variants),
                "selected_variant": selected,
            })
        return jsonify({"company_name": company, "slots": slots})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>")
def get_slot_variants(company: str, asset_key: str):
    """返回单个槽位的变体库"""
    try:
        init_assets_db(config.DB_PATH_ASSETS)
        variants = list_variants(config.DB_PATH_ASSETS, company, asset_key)
        return jsonify({
            "company_name": company,
            "asset_key": asset_key,
            "variants": variants,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/variants")
def get_slot_variants_alias(company: str, asset_key: str):
    return get_slot_variants(company, asset_key)


@app.route("/api/image-studio/<company>/<asset_key>/rescore", methods=["POST"])
def rescore_slot_variants(company: str, asset_key: str):
    """Recalculate rule-based scores and auto-select the highest scored variant."""
    try:
        init_assets_db(config.DB_PATH_ASSETS)
        variants = list_variants(config.DB_PATH_ASSETS, company, asset_key)
        if not variants:
            upsert_asset(
                config.DB_PATH_ASSETS, company, asset_key,
                status="failed", fail_reason="没有候选图可重新评分",
            )
            return jsonify({"asset_key": asset_key, "variants": [], "selected_variant_id": None})

        for v in variants:
            candidate = ImageCandidate(
                company_name=company,
                asset_key=asset_key,
                image_url=v.get("source_url") or v.get("local_path") or "",
                source_page=v.get("source_page") or "",
                source_type=v.get("source_type") or "",
                title=v.get("prompt") or "",
                alt_text=v.get("author") or "",
                author=v.get("author") or "",
                license=v.get("license") or "",
                local_path=_local_file_from_browser_path(v.get("local_path") or ""),
                width=v.get("width"),
                height=v.get("height"),
                file_size=v.get("file_size"),
                aspect_ratio=v.get("aspect_ratio"),
                meta=v.get("meta") or {},
            )
            if not candidate.width or not candidate.height or not candidate.file_size:
                inspect_local_image(candidate)
            score_candidate(candidate, product_names=[company])
            update_variant_scores(
                config.DB_PATH_ASSETS,
                v["id"],
                width=candidate.width,
                height=candidate.height,
                file_size=candidate.file_size,
                aspect_ratio=candidate.aspect_ratio,
                quality_score=candidate.quality_score,
                relevance_score=candidate.relevance_score,
                source_score=candidate.source_score,
                final_score=candidate.final_score,
                meta=candidate.meta,
            )

        rescored = list_variants(config.DB_PATH_ASSETS, company, asset_key)
        best = max(rescored, key=lambda row: row.get("final_score") or 0)
        select_variant(config.DB_PATH_ASSETS, company, asset_key, best["id"], auto_selected=True)
        rescored = list_variants(config.DB_PATH_ASSETS, company, asset_key)
        return jsonify({
            "asset_key": asset_key,
            "selected_variant_id": best["id"],
            "variants": rescored,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/search", methods=["POST"])
def search_slot_images(company: str, asset_key: str):
    """图库搜索"""
    try:
        data = request.get_json()
        query = data.get("query", "")
        source = data.get("source", "pexels")
        lang = data.get("lang", "en")
        page = data.get("page", 1)
        per_page = data.get("per_page", 9)

        if not query:
            return jsonify({"error": "缺少 query"}), 400

        result = search_images(query, source=source, lang=lang,
                               page=page, per_page=per_page)
        result["query_used"] = query
        result["page"] = page
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/fetch", methods=["POST"])
def fetch_slot_image(company: str, asset_key: str):
    """下载候选图片到本地，写入变体库"""
    try:
        data = request.get_json()
        full_url = data.get("full_url", "")
        thumbnail_url = data.get("thumbnail_url", "")
        source = data.get("source", "web_pexels")
        source_page = data.get("source_page", "")
        author = data.get("author", "")
        license_text = data.get("license", "")
        attribution = data.get("attribution", False)

        if not full_url:
            return jsonify({"error": "缺少 full_url"}), 400

        # 确定 source_type 前缀
        source_type_map = {
            "pexels": "web_pexels",
            "unsplash": "web_unsplash",
            "tavily": "web_tavily",
        }
        source_type = source_type_map.get(source, source)

        # 下载到本地
        ext = ".jpg"
        if full_url.lower().endswith(".png"):
            ext = ".png"
        elif full_url.lower().endswith(".webp"):
            ext = ".webp"

        variant_dir = _company_image_dir(config.IMAGES_DIR, company, "variants")
        os.makedirs(variant_dir, exist_ok=True)

        # 用 source id 做文件名
        img_id = data.get("id", str(int(time.time())))
        filename = f"{img_id}{ext}"
        dest = os.path.join(variant_dir, filename)

        if not _download(full_url, dest, timeout=30):
            return jsonify({"error": "下载图片失败"}), 500

        local_path = _variant_url_path(company, filename)

        # 写入变体库
        init_assets_db(config.DB_PATH_ASSETS)
        variant_id = insert_variant(
            config.DB_PATH_ASSETS, company, asset_key,
            local_path=local_path,
            source_type=source_type,
            source_url=full_url,
            source_page=source_page,
            author=author,
            license=license_text,
            attribution_req=1 if attribution else 0,
            **_quality_kwargs_for_variant(
                company, asset_key, dest, source_type,
                source_url=full_url, source_page=source_page,
                author=author, license_text=license_text,
            ),
        )

        # 自动设为选中
        select_variant(config.DB_PATH_ASSETS, company, asset_key, variant_id)

        return jsonify({
            "id": variant_id,
            "local_path": local_path,
            "source_type": source_type,
            "source_page": source_page,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/query", methods=["POST"])
def generate_search_queries(company: str, asset_key: str):
    """调用 DeepSeek Flash 生成智能搜索词"""
    try:
        data = request.get_json()
        card_markdown = data.get("card_markdown", "")

        if not card_markdown:
            return jsonify({"error": "缺少 card_markdown"}), 400

        # 截取 markdown 摘要（前 1500 字符足够）
        summary = card_markdown[:1500]

        card_topics = {
            "website_screenshot": "官网截图/首页截图",
            "office": "公司办公室/办公场景",
            "product_main": "主产品界面/使用场景",
            "products_other": "其他产品/功能截图",
            "chart_competitive": "竞争格局矩阵图",
            "chart_ecosystem": "产业链生态位图",
            "competitors": "竞品分析/行业格局",
            "competitors_logo_strip": "三个竞品 Logo 横向拼图",
        }
        topic = card_topics.get(asset_key, "产品配图")

        prompt = f"""根据以下知识卡片的 Markdown 内容，为该卡片的配图生成搜索词。

卡片主题：{topic}
公司名：{company}
Markdown 摘要：{summary}

要求：
1. 生成 3 组搜索词，每组包含：英文关键词（适合 Unsplash）、中文关键词（适合 Pexels）
2. 聚焦图片视觉内容，不要包含公司名（通用场景图效果更好）
3. 不要生成涉及人脸识别的词，不要生成版权敏感词
4. 返回 JSON 格式：[{{"en": "...", "zh": "..."}}, ...]"""

        result = call_deepseek(
            config.DEEPSEEK_API_KEY,
            prompt,
            "",
            model=config.DEEPSEEK_FLASH_MODEL,
            temperature=0.3,
            max_tokens=1024,
            timeout=30,
        )

        # 解析 JSON
        import re as _re
        match = _re.search(r'\[[\s\S]*\]', result)
        if match:
            queries = json.loads(match.group(0))
        else:
            queries = json.loads(result)

        return jsonify({"queries": queries})
    except Exception as e:
        # fallback: 返回默认查询词
        fallbacks = {
            "website_screenshot": [
                {"en": "technology company website homepage screenshot", "zh": "科技 公司 官网 首页 截图"},
                {"en": "startup website product homepage", "zh": "创业公司 官网 产品 首页"},
                {"en": "software company landing page interface", "zh": "软件 公司 官网 界面"},
            ],
            "office": [
                {"en": "modern office workspace technology", "zh": "科技公司 办公室 团队"},
                {"en": "startup office interior", "zh": "创业公司 办公环境"},
                {"en": "tech company headquarters building", "zh": "科技 总部 大楼"},
            ],
            "product_main": [
                {"en": "software application interface", "zh": "软件 产品 界面"},
                {"en": "technology product screenshot", "zh": "科技 产品 手机"},
                {"en": "app dashboard technology", "zh": "应用 仪表盘 科技"},
            ],
            "products_other": [
                {"en": "software product feature", "zh": "软件 功能 科技"},
                {"en": "technology tool dashboard", "zh": "科技 工具 界面"},
                {"en": "digital product showcase", "zh": "数字 产品 展示"},
            ],
            "chart_competitive": [
                {"en": "competitive landscape matrix chart", "zh": "竞争格局 矩阵 图"},
                {"en": "market positioning bubble chart", "zh": "市场定位 气泡图"},
                {"en": "startup competition analysis", "zh": "创业公司 竞争 分析"},
            ],
            "chart_ecosystem": [
                {"en": "value chain ecosystem map", "zh": "产业链 生态位 图"},
                {"en": "AI stack layer diagram", "zh": "AI 技术栈 层级 图"},
                {"en": "industry value chain analysis", "zh": "产业 价值链 分析"},
            ],
            "competitors": [
                {"en": "technology startup competition", "zh": "科技 创业公司 行业"},
                {"en": "market landscape comparison", "zh": "市场 格局 对比"},
                {"en": "business competition analysis", "zh": "商业 竞争 分析"},
            ],
            "competitors_logo_strip": [
                {"en": "competitor company logos", "zh": "竞品 公司 Logo"},
                {"en": "startup brand logo comparison", "zh": "创业公司 品牌 Logo 对比"},
                {"en": "technology company logo strip", "zh": "科技公司 Logo 横排"},
            ],
        }
        return jsonify({"queries": fallbacks.get(asset_key, [
            {"en": f"{company} product", "zh": f"科技 产品"},
        ])})


@app.route("/api/image-studio/<company>/<asset_key>/import", methods=["POST"])
def import_slot_image(company: str, asset_key: str):
    """手动导入图片（URL 或本地上传）"""
    try:
        if request.content_type and "multipart" in request.content_type:
            return _import_upload(company, asset_key)
        else:
            return _import_url(company, asset_key)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _import_url(company: str, asset_key: str):
    data = request.get_json()
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "缺少 url"}), 400

    variant_dir = _company_image_dir(config.IMAGES_DIR, company, "variants")
    os.makedirs(variant_dir, exist_ok=True)

    ext = ".jpg"
    if url.lower().endswith(".png"):
        ext = ".png"
    filename = f"import_{int(time.time())}{ext}"
    dest = os.path.join(variant_dir, filename)

    if not _download(url, dest, timeout=30):
        return jsonify({"error": "下载图片失败"}), 500

    local_path = _variant_url_path(company, filename)
    init_assets_db(config.DB_PATH_ASSETS)
    variant_id = insert_variant(
        config.DB_PATH_ASSETS, company, asset_key,
        local_path=local_path,
        source_type="import_url",
        source_url=url,
        **_quality_kwargs_for_variant(
            company, asset_key, dest, "import_url", source_url=url,
        ),
    )
    select_variant(config.DB_PATH_ASSETS, company, asset_key, variant_id)

    return jsonify({"id": variant_id, "local_path": local_path})


def _import_upload(company: str, asset_key: str):
    if "file" not in request.files:
        return jsonify({"error": "缺少 file"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "文件名为空"}), 400

    variant_dir = _company_image_dir(config.IMAGES_DIR, company, "variants")
    os.makedirs(variant_dir, exist_ok=True)

    ext = os.path.splitext(f.filename)[1] or ".jpg"
    filename = f"upload_{int(time.time())}{ext}"
    dest = os.path.join(variant_dir, filename)
    f.save(dest)

    local_path = _variant_url_path(company, filename)
    init_assets_db(config.DB_PATH_ASSETS)
    variant_id = insert_variant(
        config.DB_PATH_ASSETS, company, asset_key,
        local_path=local_path,
        source_type="import_upload",
        **_quality_kwargs_for_variant(
            company, asset_key, dest, "import_upload",
        ),
    )
    select_variant(config.DB_PATH_ASSETS, company, asset_key, variant_id)

    return jsonify({"id": variant_id, "local_path": local_path})


@app.route("/api/image-studio/<company>/<asset_key>/generate-map", methods=["POST"])
def generate_slot_map(company: str, asset_key: str):
    """为槽位生成 OSM 地图变体（先尝试 staticmap，失败则用 Playwright 截图）"""
    if asset_key != "office":
        return jsonify({"error": "地图仅用于公司位置地图素材"}), 400
    try:
        research = database.get_research(config.DB_PATH_RESEARCH, company, "standard")
        location = ""
        company_url = ""
        if research:
            location = (research.get("location") or "").strip()
            company_url = (research.get("website_url") or research.get("company_url") or "").strip()

        if not location:
            return jsonify({"error": "未找到公司位置信息，请先完成研究"}), 400

        resolved = _resolve_office_location(company, location, company_url)
        map_location = resolved.get("location") or location

        # 先验证 geocode 可达性
        import requests as _requests
        geo_url = f"https://nominatim.openstreetmap.org/search?q={_geocode_search_text(map_location)}&format=json&limit=1"
        try:
            geo_resp = _requests.get(geo_url, headers={"User-Agent": "aistartups-cn/1.0"}, timeout=10)
            geo_data = geo_resp.json()
        except Exception as geo_err:
            return jsonify({"error": f"地理编码失败（OSM 服务不可达，请检查 HTTPS_PROXY）: {geo_err}"}), 500

        if not geo_data:
            return jsonify({"error": f"无法定位「{map_location}」，请检查位置名称是否准确"}), 400

        suffix = f"osm_{int(time.time())}"
        dest = _variant_path(config.IMAGES_DIR, company, asset_key, suffix)
        filename = os.path.basename(dest)
        url_path = _variant_url_path(company, filename)

        if not _render_osm_map(map_location, dest, label=company, legend=map_location):
            return jsonify({"error": "地图渲染失败（staticmap 和 Playwright 均不可用）"}), 500

        init_assets_db(config.DB_PATH_ASSETS)
        quality = _quality_kwargs_for_variant(
            company, asset_key, dest, "osm_map", prompt=map_location,
        )
        quality["meta"] = {
            **(quality.get("meta") or {}),
            "location_source": resolved.get("source"),
            "map_location": map_location,
        }
        variant_id = insert_variant(
            config.DB_PATH_ASSETS, company, asset_key,
            local_path=url_path,
            source_type="osm_map",
            source_url=resolved.get("source_url") or "",
            prompt=map_location,
            **quality,
        )
        select_variant(config.DB_PATH_ASSETS, company, asset_key, variant_id)

        return jsonify({"variant_id": variant_id, "local_path": url_path, "location": map_location, "location_source": resolved.get("source")})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/extract-data", methods=["POST"])
def extract_svg_data(company: str, asset_key: str):
    """从定稿 Markdown 提取飞轮/时间线结构化 JSON，供前端预览用"""
    if asset_key not in ("flywheel", "timeline"):
        return jsonify({"error": "仅支持 flywheel / timeline"}), 400

    try:
        card_index = 6 if asset_key == "flywheel" else 3
        markdown = database.get_final_card_markdown(config.DB_PATH_FINAL, company, card_index)
        if not markdown:
            return jsonify({"error": f"未找到卡片 {card_index} 的定稿内容"}), 404

        data, cached = _load_svg_data(company, asset_key, markdown)
        if not data:
            return jsonify({"error": "结构化数据提取失败"}), 500

        return jsonify({"data": data, "cached": cached})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/render-svg", methods=["POST"])
def render_svg_variant(company: str, asset_key: str):
    """使用指定模板渲染 SVG → PNG 变体"""
    if asset_key not in ("flywheel", "timeline", "chart_competitive", "chart_ecosystem"):
        return jsonify({"error": "仅支持 flywheel / timeline / chart_competitive / chart_ecosystem"}), 400

    try:
        body = request.get_json()
        template_id = body.get("template_id")
        params = body.get("params", {})

        if not template_id:
            return jsonify({"error": "缺少 template_id"}), 400

        suffix = f"{template_id}_{int(time.time())}"
        variant_dir = _company_image_dir(config.IMAGES_DIR, company, "variants")
        os.makedirs(variant_dir, exist_ok=True)
        dest = os.path.join(variant_dir, f"{asset_key}__{suffix}.png")

        # ── chart_competitive / chart_ecosystem：无需 LLM，直接查库画散点图 ──
        if asset_key in ("chart_competitive", "chart_ecosystem"):
            companies = _load_all_scored_companies(config.DB_PATH_RESEARCH)
            chart_type = "competitive_landscape" if asset_key == "chart_competitive" else "stack_positioning"
            if chart_type == "competitive_landscape":
                ok = render_competitive_landscape(companies, company, dest, params)
            else:
                ok = render_stack_positioning(companies, company, dest, params)
            if not ok:
                return jsonify({"error": "散点图渲染失败"}), 500
            init_assets_db(config.DB_PATH_ASSETS)
            vid = insert_variant(
                config.DB_PATH_ASSETS, company, asset_key,
                local_path=_variant_url_path(company, f"{asset_key}__{suffix}.png"),
                source_type="svg_render",
                prompt=f"chart={chart_type}",
                **_quality_kwargs_for_variant(
                    company, asset_key, dest, "svg_render",
                    prompt=f"chart={chart_type}",
                ),
            )
            select_variant(config.DB_PATH_ASSETS, company, asset_key, vid)
            return jsonify({
                "variant_id": vid,
                "local_path": _variant_url_path(company, f"{asset_key}__{suffix}.png"),
            })

        # ── flywheel / timeline：LLM 提取结构化数据 ──
        card_index = 6 if asset_key == "flywheel" else 3
        markdown = database.get_final_card_markdown(config.DB_PATH_FINAL, company, card_index)
        if not markdown:
            return jsonify({"error": f"未找到卡片 {card_index} 的定稿内容"}), 404

        data, _cached = _load_svg_data(company, asset_key, markdown)
        if not data:
            return jsonify({"error": "结构化数据提取失败"}), 500

        try:
            ok = render_with_template(data, params, template_id, dest)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

        if not ok:
            return jsonify({"error": "SVG 渲染失败"}), 500

        init_assets_db(config.DB_PATH_ASSETS)
        vid = insert_variant(
            config.DB_PATH_ASSETS, company, asset_key,
            local_path=_variant_url_path(company, f"{asset_key}__{suffix}.png"),
            source_type="svg_render",
            prompt=f"template={template_id} params={json.dumps(params)}",
            **_quality_kwargs_for_variant(
                company, asset_key, dest, "svg_render",
                prompt=f"template={template_id} params={json.dumps(params)}",
            ),
        )
        select_variant(config.DB_PATH_ASSETS, company, asset_key, vid)

        return jsonify({
            "variant_id": vid,
            "local_path": _variant_url_path(company, f"{asset_key}__{suffix}.png"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/render-html", methods=["POST"])
def render_echarts_html_variant(company: str, asset_key: str):
    """Render hand-edited ECharts HTML into a PNG variant."""
    if asset_key not in ("chart_competitive", "chart_ecosystem"):
        return jsonify({"error": "仅支持 chart_competitive / chart_ecosystem"}), 400

    try:
        body = request.get_json() or {}
        html = (body.get("html") or "").strip()
        params = body.get("params") or {}
        if not html:
            return jsonify({"error": "缺少 html"}), 400
        if "echarts" not in html.lower():
            return jsonify({"error": "HTML 中未检测到 ECharts 代码"}), 400
        html = re.sub(
            r'<script\s+src=["\'][^"\']*echarts[^"\']*["\']\s*></script>',
            lambda _: f"<script>{_echarts_inline_js()}</script>",
            html,
            flags=re.IGNORECASE,
        )

        width = int(params.get("width") or body.get("width") or 800)
        height = int(params.get("height") or body.get("height") or 600)
        width = max(480, min(width, 1600))
        height = max(360, min(height, 1400))

        suffix = f"manual_echarts_{int(time.time())}"
        variant_dir = _company_image_dir(config.IMAGES_DIR, company, "variants")
        os.makedirs(variant_dir, exist_ok=True)
        dest = os.path.join(variant_dir, f"{asset_key}__{suffix}.png")
        _html_to_png(html, dest, width=width, height=height, scale=2)

        init_assets_db(config.DB_PATH_ASSETS)
        vid = insert_variant(
            config.DB_PATH_ASSETS, company, asset_key,
            local_path=_variant_url_path(company, f"{asset_key}__{suffix}.png"),
            source_type="echarts_html",
            prompt="manual_echarts_html",
            **_quality_kwargs_for_variant(
                company, asset_key, dest, "echarts_html",
                prompt="manual_echarts_html",
            ),
        )
        select_variant(config.DB_PATH_ASSETS, company, asset_key, vid)
        return jsonify({
            "variant_id": vid,
            "local_path": _variant_url_path(company, f"{asset_key}__{suffix}.png"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/select", methods=["PATCH"])
def select_slot_variant(company: str, asset_key: str):
    """选定变体"""
    try:
        data = request.get_json()
        variant_id = data.get("variant_id")
        if not variant_id:
            return jsonify({"error": "缺少 variant_id"}), 400

        ok = select_variant(config.DB_PATH_ASSETS, company, asset_key, variant_id)
        if not ok:
            return jsonify({"error": "变体不存在"}), 404

        return jsonify({"status": "ok", "variant_id": variant_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/image-studio/<company>/<asset_key>/variants/<int:variant_id>",
           methods=["DELETE"])
def delete_slot_variant(company: str, asset_key: str, variant_id: int):
    """删除变体"""
    try:
        ok = delete_variant(config.DB_PATH_ASSETS, company, asset_key, variant_id)
        if not ok:
            return jsonify({"error": "变体不存在"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return render_template("index.html")


# ── API：全量 Markdown 摘要 ──────────────────────────────────

@app.route("/api/final/abstract/<company>", methods=["POST"])
def generate_abstract(company: str):
    """生成三版本全量 Markdown 摘要"""
    try:
        abstracts = {}
        for version in ("standard", "business", "spread"):
            parts = []
            for card_index in range(1, 9):
                markdown = database.get_final_card_markdown(config.DB_PATH_FINAL, company, card_index)
                if markdown and markdown.strip():
                    parts.append(markdown.strip())
            full_text = "\n\n".join(parts)
            if not full_text.strip():
                abstracts[version] = "暂无内容"
                continue

            if len(full_text) < 300:
                abstracts[version] = full_text[:200]
                continue

            prompt = f"""你是专业编辑。以下是一家AI创业公司的8张知识卡片全部内容（{version}版）。
请用2-3句话概括核心内容（中文，150字以内），聚焦：公司做什么、核心产品、商业模式、竞争地位。
只输出摘要文本，不要标题、不要markdown格式。

全文：
{full_text[:3000]}"""

            try:
                result = call_deepseek(
                    config.DEEPSEEK_API_KEY,
                    prompt,
                    "",
                    model=config.DEEPSEEK_FLASH_MODEL,
                    temperature=0.2,
                    max_tokens=512,
                    timeout=30,
                )
                abstracts[version] = result.strip()
            except Exception:
                abstracts[version] = full_text[:200] + "..."

        return jsonify({"company_name": company, "abstracts": abstracts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 注册新路由（GZHv2） ──────────────────────────────────────────

from routes import register_routes
register_routes(app)


# ── GZHv2 页面 ──────────────────────────────────────────────────

@app.route("/layout")
@app.route("/layout/")
@app.route("/layout/<company>")
def layout_page(company: str = None):
    return render_template("layout.html")


@app.route("/template-maker")
@app.route("/template-maker/")
def template_maker_page():
    return render_template("template_maker.html")


# ── GZHv2 模板 API ──────────────────────────────────────────────

@app.route("/api/templates")
def list_card_templates():
    try:
        from repositories.template_repo import get_all_templates
        templates = get_all_templates(config.DB_PATH_TEMPLATE)
        summaries = [{
            "template_id": t["template_id"],
            "template_name": t["template_name"],
            "canvas_width": t["canvas_width"],
            "canvas_height": t["canvas_height"],
            "is_builtin": bool(t.get("is_builtin")),
        } for t in templates]
        return jsonify({"templates": summaries})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/templates/<template_id>")
def get_card_template(template_id: str):
    try:
        from repositories.template_repo import get_template
        t = get_template(config.DB_PATH_TEMPLATE, template_id)
        if not t:
            return jsonify({"error": "模板不存在"}), 404
        return jsonify(t)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/templates", methods=["POST"])
def create_card_template():
    try:
        from services.template_service import save_template
        data = request.get_json() or {}
        template_id = data.get("template_id", "")
        template_name = data.get("template_name", "")
        template_json = data.get("template_json", {})
        if not template_id or not template_name:
            return jsonify({"error": "缺少 template_id 或 template_name"}), 400
        ok, errors = save_template(config.DB_PATH_TEMPLATE, template_id, template_name, template_json)
        if not ok:
            return jsonify({"error": "校验失败", "errors": errors}), 400
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/templates/<template_id>", methods=["PATCH"])
def update_card_template(template_id: str):
    try:
        from services.template_service import validate_template_json
        from repositories.template_repo import update_template
        data = request.get_json() or {}
        updates = {}
        if "template_name" in data:
            updates["template_name"] = data.get("template_name")
        if "template_json" in data:
            template_json = data.get("template_json") or {}
            errors = validate_template_json(template_json)
            if errors:
                return jsonify({"error": "校验失败", "errors": errors}), 400
            updates["template_json"] = template_json
            canvas = template_json.get("canvas", {})
            bg = template_json.get("background", {})
            updates["canvas_width"] = canvas.get("width")
            updates["canvas_height"] = canvas.get("height")
            updates["background_type"] = bg.get("type")
            updates["background_value"] = bg.get("value")
        ok = update_template(config.DB_PATH_TEMPLATE, template_id, **updates)
        if not ok:
            return jsonify({"error": "模板不存在、为内置模板或没有可更新字段"}), 404
        return jsonify({"status": "ok", "template_id": template_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/templates/<template_id>", methods=["DELETE"])
def delete_card_template(template_id: str):
    try:
        from repositories.template_repo import delete_template
        ok = delete_template(config.DB_PATH_TEMPLATE, template_id)
        if not ok:
            return jsonify({"error": "模板不存在或为内置模板"}), 404
        return jsonify({"status": "ok", "template_id": template_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/templates/<template_id>/duplicate", methods=["POST"])
def duplicate_card_template(template_id: str):
    try:
        from repositories.template_repo import duplicate_template
        data = request.get_json() or {}
        new_id = data.get("template_id") or f"{template_id}_copy_{int(time.time())}"
        new_name = data.get("template_name") or f"{template_id} 副本"
        row_id = duplicate_template(config.DB_PATH_TEMPLATE, template_id, new_id, new_name)
        if row_id is None:
            return jsonify({"error": "模板不存在"}), 404
        return jsonify({"status": "ok", "template_id": new_id, "id": row_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── GZHv2 排版 API ──────────────────────────────────────────────

@app.route("/api/layout/<company>/<card_id>")
def get_card_layout(company: str, card_id: str):
    try:
        from repositories.layout_repo import get_layout
        layout = get_layout(config.DB_PATH_TEMPLATE, company, card_id)
        return jsonify({"company_name": company, "card_id": card_id, "layout": layout})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/layout/<company>/<card_id>", methods=["PATCH"])
def update_card_layout(company: str, card_id: str):
    try:
        from services.layout_service import update_layout_override
        data = request.get_json() or {}
        overrides = data.get("overrides", {})
        template_id = data.get("template_id", "")
        for region_id, override in overrides.items():
            update_layout_override(config.DB_PATH_TEMPLATE, company, card_id,
                                   region_id, override, template_id=template_id)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/layout/<company>/<card_id>/reset", methods=["POST"])
def reset_card_layout(company: str, card_id: str):
    try:
        from repositories.layout_repo import reset_layout
        ok = reset_layout(config.DB_PATH_TEMPLATE, company, card_id)
        return jsonify({"status": "ok", "reset": ok})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── GZHv2 导出 API ──────────────────────────────────────────────

@app.route("/api/export/<company>", methods=["POST"])
def start_export(company: str):
    """启动导出任务"""
    try:
        from services.export_service import create_job, run_export
        data = request.get_json() or {}
        card_ids = data.get("card_ids")  # None = 全部启用卡片
        fmt = data.get("format", "png")
        scale = data.get("scale", 2)

        job_id = create_job(company, card_ids=card_ids, fmt=fmt, scale=scale)
        project_root = str(Path(__file__).resolve().parent.parent)

        t = threading.Thread(target=run_export, args=(job_id, project_root), daemon=True)
        t.start()

        return jsonify({"job_id": job_id, "status": "pending"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export/<company>/jobs/<job_id>")
def get_export_status(company: str, job_id: str):
    """查询导出任务状态"""
    try:
        from services.export_service import get_job
        job = get_job(job_id)
        if not job:
            return jsonify({"error": "任务不存在"}), 404
        return jsonify(job)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export/<company>/download/<job_id>")
def download_export(company: str, job_id: str):
    """下载导出文件"""
    try:
        from services.export_service import get_job
        job = get_job(job_id)
        if not job:
            return jsonify({"error": "任务不存在"}), 404
        if job["status"] != "done":
            return jsonify({"error": "任务未完成"}), 400

        files = job.get("files", [])
        if not files:
            return jsonify({"error": "无文件"}), 404

        # 单文件 PNG 直接返回
        if len(files) == 1 and files[0].endswith(".png"):
            return send_from_directory(os.path.dirname(files[0]),
                                      os.path.basename(files[0]),
                                      mimetype="image/png")

        # ZIP 或第一个文件
        first = files[0]
        return send_from_directory(os.path.dirname(first),
                                  os.path.basename(first),
                                  as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── 启动 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=config.FLASK_PORT,
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
