"""导出服务 — render-data → HTML → Puppeteer PNG → ZIP"""
from __future__ import annotations
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path


# 全局任务状态（内存）
_export_jobs: dict[str, dict] = {}


def create_job(company: str, card_ids: list[str] | None = None,
               fmt: str = "png", scale: int = 2) -> str:
    """创建导出任务，返回 job_id"""
    job_id = f"exp_{uuid.uuid4().hex[:8]}"
    _export_jobs[job_id] = {
        "job_id": job_id,
        "company_name": company,
        "card_ids": card_ids or [],
        "format": fmt,
        "scale": scale,
        "status": "pending",
        "files": [],
        "download_url": "",
        "error": "",
        "created_at": time.time(),
    }
    return job_id


def get_job(job_id: str) -> dict | None:
    return _export_jobs.get(job_id)


def run_export(job_id: str, project_root: str):
    """后台执行导出任务"""
    job = _export_jobs.get(job_id)
    if not job:
        return

    job["status"] = "running"
    company = job["company_name"]
    card_ids = job["card_ids"]
    fmt = job.get("format", "png")
    scale = job.get("scale", 2)

    try:
        # 加载 render-data
        import sqlite3
        from config import config

        # 获取启用卡片
        from repositories.card_config_repo import get_enabled_cards, get_card_items, get_card
        from repositories.template_repo import get_template
        from repositories.layout_repo import get_layout

        cards = []
        if card_ids:
            for cid in card_ids:
                card = get_card(config.DB_PATH_COMPOSITION, company, cid)
                if card and card.get("enabled"):
                    items = get_card_items(config.DB_PATH_COMPOSITION, company, cid)
                    card["items"] = items
                    cards.append(card)
        else:
            cards = get_enabled_cards(config.DB_PATH_COMPOSITION, company)
            for card in cards:
                card["items"] = get_card_items(config.DB_PATH_COMPOSITION, company, card["card_id"])

        # 加载模板和排版
        for card in cards:
            tid = card.get("template_id")
            if tid:
                tpl = get_template(config.DB_PATH_TEMPLATE, tid)
                card["template_json"] = tpl.get("template_json") if tpl else None
            layout = get_layout(config.DB_PATH_TEMPLATE, company, card["card_id"])
            if layout:
                card["layout_json"] = layout.get("layout_json")
                # 应用 layout overrides 到 template
                if card.get("template_json") and layout.get("layout_json"):
                    overrides = layout["layout_json"].get("overrides", {})
                    regions = card["template_json"].get("regions", [])
                    for r in regions:
                        rid = r.get("id", "")
                        if rid in overrides:
                            _deep_merge_region(r, overrides[rid])

        if not cards:
            job["status"] = "failed"
            job["error"] = "没有可导出的卡片"
            return

        # 解析每个卡片的内容
        from repositories.field_repo import get_final_field_value, get_research_field_value
        from asset_store import ensure_assets_rows, get_asset
        ensure_assets_rows(config.DB_PATH_ASSETS, company)

        output_dir = Path(project_root) / "output" / "cards" / company / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        files = []

        for card in cards:
            # 解析 items
            resolved_items = []
            for item in card.get("items", []):
                resolved = dict(item)
                if item["item_type"] == "field":
                    value = (
                        get_final_field_value(config.DB_PATH_FINAL, company, item["item_key"])
                        or get_research_field_value(config.DB_PATH_RESEARCH, company, item["item_key"])
                        or ""
                    )
                    resolved["value"] = value
                elif item["item_type"] == "media":
                    media = get_asset(config.DB_PATH_ASSETS, company, item["item_key"]) or {}
                    resolved["url"] = media.get("local_path", "")
                resolved_items.append(resolved)

            # 生成 HTML
            html = _build_card_html(card, resolved_items)

            # 保存 HTML 文件
            html_path = output_dir / f"{card['card_id']}.html"
            html_path.write_text(html, encoding="utf-8")

            # Playwright 截图
            png_path = output_dir / f"{card['card_id']}.png"
            tpl = card.get("template_json")
            if isinstance(tpl, str):
                try: tpl = json.loads(tpl)
                except Exception: tpl = _default_template()
            canvas = (tpl or {}).get("canvas", {"width": 900, "height": 1200})
            w, h = canvas.get("width", 900), canvas.get("height", 1200)

            try:
                from infographic import _html_to_png
                _html_to_png(html, str(png_path), width=w, height=h, scale=scale)
                if png_path.exists() and png_path.stat().st_size > 512:
                    files.append(str(png_path))
                else:
                    files.append(str(html_path))  # Fallback: 返回 HTML
            except Exception:
                files.append(str(html_path))  # Fallback

        # ZIP 打包
        if fmt == "zip" and len(files) > 1:
            zip_path = output_dir / f"{company}_cards.zip"
            _create_zip(files, str(zip_path))
            job["download_url"] = f"/api/export/{company}/download/{job_id}"
            job["files"] = [str(zip_path)]
        else:
            job["download_url"] = f"/api/export/{company}/download/{job_id}"
            job["files"] = files

        job["status"] = "done"
    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)


def _build_card_html(card: dict, items: list[dict]) -> str:
    """用 template + items 生成卡片 HTML"""
    template = card.get("template_json")
    # template_json may already be loaded as dict by run_export
    if isinstance(template, str):
        try: template = json.loads(template)
        except Exception: template = None
    if not template:
        template = _default_template()

    canvas = template.get("canvas", {"width": 900, "height": 1200})
    bg = template.get("background", {"type": "color", "value": "#FFFFFF"})
    bg_style = _bg_style(bg)
    regions = template.get("regions", [])
    decorations = template.get("decorations", [])

    # 按 role 分组
    role_map = {}
    for item in items:
        role = item.get("display_role", "body")
        role_map.setdefault(role, []).append(item)

    # 构建 region HTML
    region_html_parts = []
    for r in regions:
        role = r.get("role", "body")
        rtype = r.get("type", "text")
        style = _region_style(r)

        if rtype in ("image", "chart", "logo"):
            candidates = role_map.get(role) or role_map.get("hero_image") or role_map.get("chart") or []
            url = candidates[0].get("url", "") if candidates else ""
            if url:
                fit = (r.get("style") or {}).get("objectFit", "contain")
                region_html_parts.append(
                    f'<img src="{_esc_attr(url)}" style="{style}object-fit:{fit};display:block" alt="">')
            else:
                region_html_parts.append(
                    f'<div style="{style}display:flex;align-items:center;justify-content:center;color:rgba(0,0,0,0.1);font-size:14px">[{role}]</div>')
        elif rtype == "shape":
            region_html_parts.append(f'<div style="{style}"></div>')
        else:
            texts = [item.get("value", "") for item in role_map.get(role, role_map.get("body", []))]
            combined = "\n\n".join(t for t in texts if t)
            ta = (r.get("style") or {}).get("textAlign", "left")
            lh = (r.get("style") or {}).get("lineHeight", 1.55)
            region_html_parts.append(
                f'<div style="{style}text-align:{ta};line-height:{lh};white-space:pre-wrap;word-wrap:break-word">{_esc(combined)}</div>')

    deco_html = ""
    for d in decorations:
        if d.get("type") == "noise":
            deco_html += f'<div style="position:absolute;inset:0;opacity:{d.get("opacity",0.05)};pointer-events:none;z-index:1;background-image:url(\'data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22200%22 height=%22200%22><filter id=%22n%22><feTurbulence type=%22fractalNoise%22 baseFrequency=%220.7%22/></filter><rect width=%22200%22 height=%22200%22 filter=%22url(%23n)%22 opacity=%220.5%22/></svg>\');background-size:200px"></div>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@500;700&family=Noto+Sans+SC:wght@400;700;900&display=swap');
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ width:{canvas.get("width",900)}px; height:{canvas.get("height",1200)}px; overflow:hidden; position:relative; {bg_style} }}
</style></head><body>
  {deco_html}
  {"".join(region_html_parts)}
</body></html>"""


def _default_template() -> dict:
    return {
        "canvas": {"width": 900, "height": 1200},
        "background": {"type": "color", "value": "#FFFFFF"},
        "regions": [
            {"id": "title", "type": "text", "role": "title", "x": 68, "y": 80, "w": 764, "h": 90,
             "style": {"fontFamily": "Noto Sans SC", "fontSize": 48, "fontWeight": 700, "color": "#111", "textAlign": "left"}},
            {"id": "body", "type": "text", "role": "body", "x": 68, "y": 200, "w": 764, "h": 920,
             "style": {"fontFamily": "Noto Sans SC", "fontSize": 24, "fontWeight": 400, "color": "#333", "lineHeight": 1.55}},
        ],
        "decorations": [],
    }


def _bg_style(bg: dict) -> str:
    if not bg:
        return "background:#FFFFFF;"
    t = bg.get("type", "color")
    v = bg.get("value", "#FFFFFF")
    if t == "gradient":
        return f"background:{v};"
    if t == "image":
        return f"background:url({v}) center/cover;"
    return f"background:{v};"


def _region_style(r: dict) -> str:
    s = r.get("style") or {}
    css = [
        f"position:absolute",
        f"left:{r.get('x',0)}px",
        f"top:{r.get('y',0)}px",
        f"width:{r.get('w',100)}px",
        f"height:{r.get('h',100)}px",
    ]
    if s.get("fontFamily"): css.append(f"font-family:'{s['fontFamily']}','Noto Sans SC',sans-serif")
    if s.get("fontSize"): css.append(f"font-size:{s['fontSize']}px")
    if s.get("fontWeight"): css.append(f"font-weight:{s['fontWeight']}")
    if s.get("color"): css.append(f"color:{s['color']}")
    if s.get("letterSpacing"): css.append(f"letter-spacing:{s['letterSpacing']}")
    if s.get("opacity") is not None: css.append(f"opacity:{s['opacity']}")
    if s.get("borderRadius"): css.append(f"border-radius:{s['borderRadius']}px")
    if s.get("borderWidth") and s.get("borderColor"):
        css.append(f"border:{s['borderWidth']}px solid {s['borderColor']}")
    if s.get("shadow"): css.append(f"box-shadow:{s['shadow']}")
    if s.get("backgroundColor"): css.append(f"background:{s['backgroundColor']}")
    css.append("overflow:hidden")
    return ";".join(css) + ";"


def _deep_merge_region(base: dict, override: dict):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge_region(base[k], v)
        else:
            base[k] = v


def _create_zip(file_paths: list[str], dest: str):
    import zipfile
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in file_paths:
            zf.write(fp, os.path.basename(fp))


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _esc_attr(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace('"', "&quot;")
