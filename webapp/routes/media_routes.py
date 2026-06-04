"""图片素材 API — /api/media/...

This is the decoupled media-facing contract. It wraps the existing
company_assets/image_variants storage so older image-studio routes can remain
available while new layout/card-config code speaks in media terms.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from urllib.parse import quote

from flask import Blueprint, jsonify, redirect, request

from config import config
import db as database
from asset_store import (
    ASSET_KEYS,
    ensure_assets_rows,
    get_asset,
    get_assets,
    insert_variant,
    list_variants,
    select_variant,
)


COLLECTED_MEDIA_KEYS = {
    "logo", "office", "website_screenshot", "product_main",
    "products_other", "competitors", "competitors_logo_strip",
}
GENERATED_MEDIA_KEYS = {
    "flywheel", "timeline", "chart_competitive", "chart_ecosystem",
}
UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
UPLOAD_MIMES = {"image/png", "image/jpeg", "image/webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _safe_part(value: str) -> str:
    part = re.sub(r"[^A-Za-z0-9._-]+", "_", value or "").strip("._")
    return part or "company"


def _image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return None, None


def _company_data(company: str) -> dict | None:
    research = database.get_research(config.DB_PATH_RESEARCH, company, "standard")
    if not research:
        return None
    return {
        "company_url": research.get("website_url", ""),
        "website_url": research.get("website_url", ""),
        "location": research.get("location", ""),
        "other_products": research.get("other_products", ""),
        "competitors": research.get("competitors", ""),
    }


def _collect_media(company: str, media_key: str):
    company_data = _company_data(company)
    if not company_data:
        return None, (jsonify({"error": f"未找到公司 {company} 的研究数据"}), 404)

    from asset_pipeline import collect_image_variants_pipeline
    results = collect_image_variants_pipeline(
        config.DB_PATH_ASSETS,
        config.IMAGES_DIR,
        company,
        company_data,
        asset_key=media_key,
    )
    return results, None


def _media_summary(company: str, media_key: str, asset: dict | None = None) -> dict:
    asset = asset or {}
    variants = list_variants(config.DB_PATH_ASSETS, company, media_key)
    selected = next((v for v in variants if v.get("is_selected")), None)
    return {
        "company_name": company,
        "media_key": media_key,
        "media_label": media_key,
        "status": asset.get("status", "missing"),
        "local_path": asset.get("local_path", ""),
        "source_type": asset.get("source_type", ""),
        "selected_variant_id": asset.get("selected_variant_id"),
        "selected_variant": selected,
        "variant_count": len(variants),
        "variants": variants,
    }


def register(bp: Blueprint):
    @bp.route("/media/<company>")
    def list_company_media(company: str):
        try:
            ensure_assets_rows(config.DB_PATH_ASSETS, company)
            assets = get_assets(config.DB_PATH_ASSETS, company)
            media = [_media_summary(company, key, assets.get(key)) for key in ASSET_KEYS]
            return jsonify({"company_name": company, "media": media})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/media/<company>/<media_key>")
    def get_company_media(company: str, media_key: str):
        if media_key not in ASSET_KEYS:
            return jsonify({"error": "未知 media_key"}), 404
        try:
            ensure_assets_rows(config.DB_PATH_ASSETS, company)
            asset = get_asset(config.DB_PATH_ASSETS, company, media_key)
            return jsonify(_media_summary(company, media_key, asset))
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/media/<company>/<media_key>/select", methods=["PATCH"])
    def select_company_media(company: str, media_key: str):
        if media_key not in ASSET_KEYS:
            return jsonify({"error": "未知 media_key"}), 404
        data = request.get_json() or {}
        variant_id = data.get("variant_id")
        if not variant_id:
            return jsonify({"error": "缺少 variant_id"}), 400
        try:
            ok = select_variant(config.DB_PATH_ASSETS, company, media_key, int(variant_id))
            if not ok:
                return jsonify({"error": "变体不存在"}), 404
            asset = get_asset(config.DB_PATH_ASSETS, company, media_key)
            return jsonify({
                "status": "ok",
                "media_key": media_key,
                "variant_id": int(variant_id),
                "media": _media_summary(company, media_key, asset),
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/media/<company>/<media_key>/recollect", methods=["POST"])
    def recollect_company_media(company: str, media_key: str):
        if media_key not in ASSET_KEYS:
            return jsonify({"error": "未知 media_key"}), 404
        if media_key not in COLLECTED_MEDIA_KEYS:
            return jsonify({"error": f"{media_key} 不是采集图片类型，请使用 generate"}), 400
        try:
            results, error = _collect_media(company, media_key)
            if error:
                return error
            asset = get_asset(config.DB_PATH_ASSETS, company, media_key)
            return jsonify({
                "status": "ok",
                "company_name": company,
                "media_key": media_key,
                "results": results,
                "media": _media_summary(company, media_key, asset),
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @bp.route("/media/<company>/<media_key>/generate", methods=["POST"])
    def generate_company_media(company: str, media_key: str):
        if media_key not in ASSET_KEYS:
            return jsonify({"error": "未知 media_key"}), 404
        if media_key == "competitors_logo_strip":
            try:
                results, error = _collect_media(company, media_key)
                if error:
                    return error
                asset = get_asset(config.DB_PATH_ASSETS, company, media_key)
                return jsonify({
                    "status": "ok",
                    "company_name": company,
                    "media_key": media_key,
                    "results": results,
                    "media": _media_summary(company, media_key, asset),
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        if media_key in GENERATED_MEDIA_KEYS:
            return redirect(f"/api/assets/generate/{quote(company)}/{media_key}", code=307)
        return jsonify({"error": f"{media_key} 不是生成图片类型，请使用 recollect 或 upload"}), 400

    @bp.route("/media/<company>/<media_key>/upload", methods=["POST"])
    def upload_company_media(company: str, media_key: str):
        if media_key not in ASSET_KEYS:
            return jsonify({"error": "未知 media_key"}), 404
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"error": "缺少上传文件 file"}), 400

        ext = Path(file.filename).suffix.lower()
        if ext not in UPLOAD_EXTENSIONS:
            return jsonify({"error": "仅允许上传 png / jpg / jpeg / webp，普通图片不接受 svg"}), 400
        if file.mimetype and file.mimetype not in UPLOAD_MIMES:
            return jsonify({"error": "文件类型与允许图片类型不匹配"}), 400

        try:
            file.stream.seek(0, os.SEEK_END)
            size = file.stream.tell()
            file.stream.seek(0)
        except Exception:
            size = 0
        if size > MAX_UPLOAD_BYTES:
            return jsonify({"error": "文件超过 10MB 限制"}), 413

        try:
            company_dir_name = _safe_part(company)
            variant_dir = Path(config.IMAGES_DIR) / company_dir_name / "variants"
            variant_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{media_key}_upload_{int(time.time() * 1000)}{ext}"
            local_file = variant_dir / filename
            file.save(local_file)

            width, height = _image_dimensions(local_file)
            if not width or not height:
                local_file.unlink(missing_ok=True)
                return jsonify({"error": "无法识别图片内容"}), 400
            aspect_ratio = (width / height) if width and height else None
            local_path = f"/images/{company_dir_name}/variants/{filename}"

            ensure_assets_rows(config.DB_PATH_ASSETS, company)
            variant_id = insert_variant(
                config.DB_PATH_ASSETS,
                company,
                media_key,
                local_path=local_path,
                source_type="upload",
                width=width,
                height=height,
                file_size=local_file.stat().st_size,
                aspect_ratio=aspect_ratio,
                final_score=100,
                meta={"upload_filename": file.filename},
            )
            select_variant(config.DB_PATH_ASSETS, company, media_key, variant_id)
            asset = get_asset(config.DB_PATH_ASSETS, company, media_key)
            return jsonify({
                "status": "ok",
                "company_name": company,
                "media_key": media_key,
                "variant_id": variant_id,
                "media": _media_summary(company, media_key, asset),
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
