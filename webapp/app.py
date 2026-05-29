from __future__ import annotations
from flask import Flask, request, jsonify, render_template, send_from_directory
from config import config
import db as database
from deepseek_client import call_deepseek, load_prompt
from image_client import generate_image
from firecrawl_local import scrape_url
from pipeline import run_pipeline
from asset_store import init_assets_db, ensure_assets_rows, get_assets, upsert_asset
from asset_pipeline import collect_all_assets
from infographic import generate_flywheel_from_markdown, generate_timeline_from_markdown
import markdown_builder
import json
import time
import uuid
import threading
from pathlib import Path

app = Flask(__name__)
app.config.from_object(config)

# 确保图片目录存在
Path(config.IMAGES_DIR).mkdir(parents=True, exist_ok=True)

# 初始化资产数据库
init_assets_db(config.DB_PATH_ASSETS)

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

    try:
        ids = run_pipeline(company_name, company_url, progress_callback=on_progress, job_id=job_id)
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
    except Exception as e:
        with _jobs_lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = "failed"
                _jobs[job_id]["error"] = str(e)
        database.update_job(config.DB_PATH_RESEARCH, job_id,
                            status="failed", error=str(e),
                            stage="失败", detail=str(e)[:200])


def _collect_assets_silently(company_name: str):
    """研究完成后的图片资产采集不再占用研究任务状态。"""
    try:
        research = database.get_research(config.DB_PATH_RESEARCH, company_name, "standard")
        if not research:
            return
        company_data = {
            "company_url": research.get("website_url", ""),
            "website_url": research.get("website_url", ""),
            "location": research.get("location", ""),
            "other_products": research.get("other_products", ""),
            "competitors": research.get("competitors", ""),
        }
        collect_all_assets(config.DB_PATH_ASSETS, config.IMAGES_DIR, company_name, company_data)
    except Exception:
        pass


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
            upsert_asset(config.DB_PATH_ASSETS, company_name, asset_key,
                        local_path=img_path, source_type="api_generate",
                        source_url="", prompt=prompt, status="ready")

        return jsonify({"status": "ok", "img_path": img_path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/images/<path:filename>")
def image_assets(filename):
    return send_from_directory(config.IMAGES_DIR, filename)


# ── API：资产系统 ──────────────────────────────────────────────

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
    """触发七图自动采集"""
    try:
        # 从 research DB 获取公司数据
        research = database.get_research(config.DB_PATH_RESEARCH, company, "standard")
        if not research:
            return jsonify({"error": f"未找到公司 {company} 的研究数据"}), 404

        company_data = {
            "company_url": research.get("website_url", ""),
            "website_url": research.get("website_url", ""),
            "location": research.get("location", ""),
            "other_products": research.get("other_products", ""),
            "competitors": research.get("competitors", ""),
        }

        images_root = config.IMAGES_DIR
        results = collect_all_assets(config.DB_PATH_ASSETS, images_root, company, company_data)
        return jsonify({"status": "ok", "company_name": company, "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/assets/generate/<company>/<asset_key>", methods=["POST"])
def generate_asset(company: str, asset_key: str):
    """生成信息图（flywheel 或 timeline）"""
    if asset_key not in ("flywheel", "timeline"):
        return jsonify({"error": f"不支持的 asset_key: {asset_key}，仅支持 flywheel/timeline"}), 400

    try:
        # 获取对应卡片的 markdown
        card_index = 6 if asset_key == "flywheel" else 3
        markdown = database.get_final_card_markdown(config.DB_PATH_FINAL, company, card_index)
        if not markdown:
            return jsonify({"error": f"未找到公司 {company} 卡片 {card_index} 的定稿内容"}), 404

        # 确保资产行存在
        ensure_assets_rows(config.DB_PATH_ASSETS, company)

        # 输出路径
        dest_dir = os.path.join(config.IMAGES_DIR, company)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"{asset_key}.png")

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
                    local_path=f"/images/{company}/{asset_key}.png",
                    source_type="svg_render", status="ready")

        return jsonify({
            "status": "ok",
            "company_name": company,
            "asset_key": asset_key,
            "local_path": f"/images/{company}/{asset_key}.png",
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


# ── 编辑器页面 ─────────────────────────────────────────────────

@app.route("/editor")
@app.route("/editor/")
@app.route("/editor/<company>")
def editor_page(company: str = None):
    return render_template("editor.html")


@app.route("/canvas/")
def canvas_page():
    return send_from_directory("../canvas", "card-renderer.html")


@app.route("/canvas/card/<company>/<int:card_index>")
def canvas_card_page(company: str, card_index: int):
    if card_index < 1 or card_index > 8:
        return jsonify({"error": "card_index 必须在 1-8 之间"}), 400
    return send_from_directory("../canvas", "card.html")


@app.route("/canvas/<path:filename>")
def canvas_assets(filename):
    return send_from_directory("../canvas", filename)


@app.route("/")
def index():
    return render_template("index.html")


# ── 启动 ──────────────────────────────────────────────────────

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.FLASK_PORT, debug=True)
