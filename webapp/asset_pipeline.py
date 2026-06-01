"""七图自动采集管道 — logo / office / product / competitors / other_products"""
from __future__ import annotations
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import shutil

import requests

from config import config
from asset_store import (
    ASSET_KEYS, ASSET_TO_CARD, CARD_ASSET_MAP,
    ensure_assets_rows, upsert_asset, get_asset,
    list_variants, select_variant,
)
from image_query import build_image_queries

# 忽略 SSL 警告（部分图片源证书可能有问题）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def asset_dir(images_root: str, company_name: str) -> str:
    """返回某公司的图片目录，确保存在"""
    d = os.path.join(images_root, company_name)
    os.makedirs(d, exist_ok=True)
    return d


def _safe_path_segment(value) -> str:
    segment = str(value or "company").strip()
    segment = segment.replace("/", "_").replace("\\", "_")
    segment = re.sub(r"\s+", "_", segment)
    segment = re.sub(r"[\x00-\x1f\x7f?%*:|\"<>]", "_", segment)
    while ".." in segment:
        segment = segment.replace("..", "_")
    return segment.strip("._ ") or "company"


def _company_image_dir(images_root: str, company_name: str, *parts: str) -> str:
    base = os.path.abspath(images_root)
    target = os.path.abspath(os.path.join(base, _safe_path_segment(company_name), *parts))
    if os.path.commonpath([base, target]) != base:
        raise ValueError("公司图片目录越界")
    return target


def _image_url_path(company_name: str, *parts: str) -> str:
    url_parts = [_safe_path_segment(company_name), *[str(p) for p in parts]]
    return "/images/" + "/".join(quote(p, safe="") for p in url_parts)


def _variant_url_path(company_name: str, filename: str) -> str:
    return _image_url_path(company_name, "variants", filename)


def _variant_path(images_root: str, company_name: str, asset_key: str, suffix) -> str:
    """生成变体文件路径，确保 variants 子目录存在"""
    d = _company_image_dir(images_root, company_name, "variants")
    os.makedirs(d, exist_ok=True)
    safe_asset_key = _safe_path_segment(asset_key)
    safe_suffix = _safe_path_segment(suffix)
    return os.path.join(d, f"{safe_asset_key}__{safe_suffix}.png")


def _variant_browser_path(company_name: str, file_path: str) -> str:
    return _variant_url_path(company_name, os.path.basename(file_path))


def _collect_candidates(
    db_path: str, images_root: str, company_name: str, asset_key: str,
    sources: list[dict],
    max_candidates: int = 3,
) -> int:
    """
    依次尝试 sources，成功则写 image_variants。
    不 select，不写 company_assets.local_path。
    返回实际写入数量。
    """
    from asset_store import insert_variant
    count = 0
    for src in sources:
        if count >= max_candidates:
            break
        dest = _variant_path(images_root, company_name, asset_key, count)
        ok, source_url = False, ""

        if src["type"] == "scrape":
            img_url = _scrape_page_hero_image(src.get("url", ""))
            if img_url:
                ok = _download(img_url, dest)
                source_url = img_url

        elif src["type"] == "playwright":
            if src.get("url"):
                try:
                    _playwright_screenshot(src["url"], dest)
                    ok = os.path.getsize(dest) > 512
                    source_url = src["url"]
                except Exception:
                    pass

        elif src["type"] == "tavily":
            img_url = _try_tavily_images(src["query"], dest)
            ok = bool(img_url)
            source_url = img_url or ""

        elif src["type"] == "clearbit":
            url = f"https://logo.clearbit.com/{src['domain']}"
            ok = _download(url, dest)
            source_url = url

        if ok:
            insert_variant(db_path, company_name, asset_key,
                           local_path=_variant_browser_path(company_name, dest),
                           source_type=f"screenshot_{src['type']}",
                           source_url=source_url)
            count += 1
    return count


def _download(url: str, dest: str, timeout: int = 15) -> bool:
    """下载 URL 到本地文件，返回是否成功"""
    try:
        resp = requests.get(url, timeout=timeout,
                          headers={"User-Agent": "Mozilla/5.0"},
                          verify=False, stream=True)
        if resp.status_code >= 400:
            return False
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        return os.path.getsize(dest) > 512
    except Exception:
        return False


def _domain_from_url(url: str) -> str:
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    return urlparse(url).netloc or ""


# ═══════════════════════════════════════════════════════════════
# 1. Logo
# ═══════════════════════════════════════════════════════════════

def collect_logo(db_path: str, images_root: str, company_name: str,
                 company_url: str = "", website_url: str = "") -> dict | None:
    domain = _domain_from_url(company_url or website_url)
    if not domain:
        return None

    dest_dir = asset_dir(images_root, company_name)
    dest = os.path.join(dest_dir, "logo.png")

    # 策略1: Clearbit Logo API
    sources = [
        ("clearbit", f"https://logo.clearbit.com/{domain}"),
        # 策略2: Google Favicon (fallback)
        ("favicon", f"https://www.google.com/s2/favicons?domain={domain}&sz=128"),
    ]

    for src_type, url in sources:
        if _download(url, dest):
            upsert_asset(db_path, company_name, "logo",
                        local_path=f"/images/{company_name}/logo.png",
                        source_type=src_type, source_url=url, status="ready")
            return {"local_path": f"/images/{company_name}/logo.png", "source_type": src_type}

    upsert_asset(db_path, company_name, "logo", status="failed")
    return None


# ═══════════════════════════════════════════════════════════════
# 2. Office / 地图
# ═══════════════════════════════════════════════════════════════

def _scrape_page_hero_image(page_url: str, company_name: str = "") -> str | None:
    """
    抓取指定页面，找面积最大且非 logo/icon 的 <img>，返回其 src URL。
    用于 About / Newsroom 页提取公司真实照片。
    """
    from bs4 import BeautifulSoup
    try:
        resp = requests.get(page_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15, verify=False)
        soup = BeautifulSoup(resp.text, "lxml")

        candidates = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if not src or src.startswith("data:"):
                continue
            if any(x in src.lower() for x in ["icon", "logo", "favicon", ".svg"]):
                continue
            if src.startswith("/"):
                base = urlparse(page_url)
                src = f"{base.scheme}://{base.netloc}{src}"
            elif not src.startswith("http"):
                continue
            w = int(img.get("width", 0) or 0)
            h = int(img.get("height", 0) or 0)
            score = w * h if w and h else 50000
            candidates.append((score, src))

        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]
    except Exception:
        return None


def collect_office(db_path: str, images_root: str, company_name: str,
                   location: str = "", query_config: dict = None) -> dict | None:
    """
    图片搜索词 v2：
    1. 优先抓官网 About/Newsroom 页提取 hero image
    2. Tavily 搜新闻/媒体图（含公司名，真实照片）
    3. OSM 静态地图兜底
    不用通用图（Lorem Flickr / Picsum）。
    """
    dest_dir = asset_dir(images_root, company_name)
    dest = os.path.join(dest_dir, "office.png")
    cfg = query_config or {}

    # 1. 抓官网 About / Newsroom 页 hero image
    for url in cfg.get("scrape_urls", []):
        img_url = _scrape_page_hero_image(url, company_name)
        if img_url and _download(img_url, dest):
            upsert_asset(db_path, company_name, "office",
                         local_path=f"/images/{company_name}/office.png",
                         source_type="web_scrape", source_url=img_url, status="ready")
            return {"local_path": f"/images/{company_name}/office.png"}

    # 2. Tavily 搜新闻/媒体图
    for query in cfg.get("tavily_queries", []):
        img_url = _try_tavily_images(query, dest)
        if img_url:
            upsert_asset(db_path, company_name, "office",
                         local_path=f"/images/{company_name}/office.png",
                         source_type="web_search", source_url=img_url, status="ready")
            return {"local_path": f"/images/{company_name}/office.png"}

    # 3. OSM 静态地图兜底
    if location:
        map_dest = os.path.join(dest_dir, "office_map.png")
        if _render_osm_map(location, map_dest):
            upsert_asset(db_path, company_name, "office",
                        local_path=f"/images/{company_name}/office_map.png",
                        source_type="osm_map", source_url="", status="ready",
                        meta={"note": "地图替代（未找到办公楼照片）"})
            return {"local_path": f"/images/{company_name}/office_map.png"}

    upsert_asset(db_path, company_name, "office", status="failed")
    return None


# ═══════════════════════════════════════════════════════════════
# 3. 主产品截图（Playwright）
# ═══════════════════════════════════════════════════════════════

def capture_product(db_path: str, images_root: str, company_name: str,
                    website_url: str = "", query_config: dict = None) -> dict | None:
    """
    图片搜索词 v2：
    1. Playwright 截产品页（优先 main_product_img_src，其次官网）
    2. Tavily 搜产品界面图
    不用通用图。
    """
    dest_dir = asset_dir(images_root, company_name)
    dest = os.path.join(dest_dir, "product_main.png")
    cfg = query_config or {}

    # 1. Playwright 截图
    for url in cfg.get("playwright_urls", []):
        if not url:
            continue
        try:
            _playwright_screenshot(url, dest)
            if os.path.getsize(dest) > 512:
                upsert_asset(db_path, company_name, "product_main",
                            local_path=f"/images/{company_name}/product_main.png",
                            source_type="screenshot", source_url=url, status="ready")
                return {"local_path": f"/images/{company_name}/product_main.png"}
        except Exception:
            pass

    # 2. Tavily 搜产品界面图
    for query in cfg.get("tavily_queries", []):
        img_url = _try_tavily_images(query, dest)
        if img_url:
            upsert_asset(db_path, company_name, "product_main",
                         local_path=f"/images/{company_name}/product_main.png",
                         source_type="web_search", source_url=img_url, status="ready")
            return {"local_path": f"/images/{company_name}/product_main.png"}

    upsert_asset(db_path, company_name, "product_main", status="failed")
    return None


# ═══════════════════════════════════════════════════════════════
# 4. 其他产品图（搜索 + 拼接）
# ═══════════════════════════════════════════════════════════════

def collect_other_products(db_path: str, images_root: str, company_name: str,
                           query_config: dict = None) -> dict | None:
    """
    图片搜索词 v2：
    1. Playwright 截各产品页（有 URL 时优先）
    2. Tavily 搜产品界面图
    3. 搜不到该产品跳过
    4. 水平拼接所有找到的图
    不用通用图。
    """
    cfg = query_config or {}
    per_product = cfg.get("per_product", [])
    if not per_product:
        upsert_asset(db_path, company_name, "products_other", status="failed")
        return None

    dest_dir = asset_dir(images_root, company_name)
    product_images = []

    for i, item in enumerate(per_product):
        name = item.get("name", f"product-{i}")
        tmp_dest = os.path.join(dest_dir, f"_tmp_product_{i}.png")

        # 1. Playwright 截产品页（有 URL 时）
        if item.get("playwright_url"):
            try:
                _playwright_screenshot(item["playwright_url"], tmp_dest)
                if os.path.getsize(tmp_dest) > 512:
                    product_images.append(tmp_dest)
                    continue
            except Exception:
                pass

        # 2. Tavily 搜产品界面图
        found = False
        for query in item.get("tavily_queries", []):
            img_url = _try_tavily_images(query, tmp_dest)
            if img_url and os.path.getsize(tmp_dest) > 512:
                product_images.append(tmp_dest)
                found = True
                break

        if not found:
            # 清理空的临时文件
            try:
                os.remove(tmp_dest)
            except OSError:
                pass

    if not product_images:
        upsert_asset(db_path, company_name, "products_other", status="failed")
        return None

    dest = os.path.join(dest_dir, "products_other.png")
    try:
        _composite_horizontal(product_images, dest)
        upsert_asset(db_path, company_name, "products_other",
                    local_path=f"/images/{company_name}/products_other.png",
                    source_type="composite", source_url="", status="ready")
        for tmp in product_images:
            try:
                os.remove(tmp)
            except OSError:
                pass
        return {"local_path": f"/images/{company_name}/products_other.png"}
    except Exception:
        upsert_asset(db_path, company_name, "products_other", status="failed")
        return None


# ═══════════════════════════════════════════════════════════════
# 5. 竞品 Logo 拼图
# ═══════════════════════════════════════════════════════════════

def compose_competitors(db_path: str, images_root: str, company_name: str,
                        query_config: dict = None) -> dict | None:
    """
    图片搜索词 v2：
    1. Playwright 截竞品官网（有 URL 时优先）
    2. Tavily 搜竞品产品截图
    3. Clearbit logo 兜底（竞品卡专属）
    4. Grid 拼图
    不用通用图。
    """
    cfg = query_config or {}
    per_comp = cfg.get("per_comp", [])
    if not per_comp:
        upsert_asset(db_path, company_name, "competitors", status="failed")
        return None

    dest_dir = asset_dir(images_root, company_name)
    comp_images = []

    for i, item in enumerate(per_comp):
        name = item.get("name", f"competitor-{i}")
        tmp_dest = os.path.join(dest_dir, f"_tmp_comp_{i}.png")

        # 1. Playwright 截竞品官网
        if item.get("playwright_url"):
            try:
                _playwright_screenshot(item["playwright_url"], tmp_dest)
                if os.path.getsize(tmp_dest) > 512:
                    comp_images.append(tmp_dest)
                    continue
            except Exception:
                pass

        # 2. Tavily 搜竞品产品截图
        found = False
        for query in item.get("tavily_queries", []):
            img_url = _try_tavily_images(query, tmp_dest)
            if img_url and os.path.getsize(tmp_dest) > 512:
                comp_images.append(tmp_dest)
                found = True
                break

        if found:
            continue

        # 3. Clearbit logo 兜底
        domain = _guess_domain(name)
        if domain:
            logo_url = f"https://logo.clearbit.com/{domain}"
            if _download(logo_url, tmp_dest):
                comp_images.append(tmp_dest)
                continue
            # Google Favicon 再兜底
            fav_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
            if _download(fav_url, tmp_dest):
                comp_images.append(tmp_dest)
                continue

        # 清理
        try:
            os.remove(tmp_dest)
        except OSError:
            pass

    if not comp_images:
        upsert_asset(db_path, company_name, "competitors", status="failed")
        return None

    dest = os.path.join(dest_dir, "competitors.png")
    try:
        _composite_grid(comp_images, dest)
        upsert_asset(db_path, company_name, "competitors",
                    local_path=f"/images/{company_name}/competitors.png",
                    source_type="composite", source_url="", status="ready")
        for tmp in comp_images:
            try:
                os.remove(tmp)
            except OSError:
                pass
        return {"local_path": f"/images/{company_name}/competitors.png"}
    except Exception:
        upsert_asset(db_path, company_name, "competitors", status="failed")
        return None


# ═══════════════════════════════════════════════════════════════
# 主入口：采集全部
# ═══════════════════════════════════════════════════════════════

def collect_all_assets(db_path: str, images_root: str, company_name: str,
                       company_data: dict) -> dict[str, dict]:
    """
    company_data: 从 research_db 或 final_db 拿到的字段 dict
    包含: company_url/website_url, location, other_products(JSON), competitors(JSON)
    """
    ensure_assets_rows(db_path, company_name)
    results = {}

    company_url = company_data.get("company_url") or company_data.get("website_url") or ""
    website_url = company_data.get("website_url") or company_data.get("company_url") or ""
    location = company_data.get("location") or ""

    # 构建搜索词配置
    query_config = build_image_queries(company_data)

    # 1. Logo
    r = collect_logo(db_path, images_root, company_name, company_url, website_url)
    results["logo"] = r

    # 2. Office
    r = collect_office(db_path, images_root, company_name, location,
                       query_config=query_config.get("office"))
    results["office"] = r

    # 3. 主产品截图
    r = capture_product(db_path, images_root, company_name, website_url,
                        query_config=query_config.get("product_main"))
    results["product_main"] = r

    # 4. 其他产品
    r = collect_other_products(db_path, images_root, company_name,
                               query_config=query_config.get("products_other"))
    results["products_other"] = r

    # 5. 竞品图
    r = compose_competitors(db_path, images_root, company_name,
                            query_config=query_config.get("competitors"))
    results["competitors"] = r

    # 6-7. flywheel / timeline 不在此自动采集，由 infographic.py 处理
    for key in ("flywheel", "timeline"):
        r = get_asset(db_path, company_name, key)
        results[key] = r

    return results


def _collect_assets_as_variants(db_path: str, images_root: str, company_name: str,
                                 company_data: dict):
    """
    变体模式采集：每个槽位生成多个候选写入 image_variants，
    不直接写 company_assets.local_path（等定稿台 select）。
    在文字生成完成后调用。
    """
    from asset_store import insert_variant, upsert_asset
    query_config = build_image_queries(company_data)
    company_url = company_data.get("company_url") or company_data.get("website_url") or ""
    website_url = company_data.get("website_url") or company_data.get("company_url") or ""
    location = company_data.get("location") or ""

    ensure_assets_rows(db_path, company_name)

    # Logo — 保持原有逻辑（单候选，直接写 company_assets）
    collect_logo(db_path, images_root, company_name, company_url, website_url)

    # Office — 多候选采集
    off_cfg = query_config.get("office", {})
    off_sources = []
    for url in off_cfg.get("scrape_urls", []):
        off_sources.append({"type": "scrape", "url": url})
    for q in off_cfg.get("tavily_queries", []):
        off_sources.append({"type": "tavily", "query": q})
    n_off = _collect_candidates(db_path, images_root, company_name, "office", off_sources)
    if n_off == 0 and location:
        # OSM 地图兜底
        dest = _variant_path(images_root, company_name, "office", "osm")
        if _render_osm_map(location, dest):
            insert_variant(db_path, company_name, "office",
                           local_path=_variant_browser_path(company_name, dest),
                           source_type="osm_map")
            n_off = 1
    upsert_asset(db_path, company_name, "office", status="ready" if n_off > 0 else "failed")

    # Product main — 多候选
    prod_cfg = query_config.get("product_main", {})
    prod_sources = []
    for url in prod_cfg.get("playwright_urls", []):
        if url:
            prod_sources.append({"type": "playwright", "url": url})
    for q in prod_cfg.get("tavily_queries", []):
        prod_sources.append({"type": "tavily", "query": q})
    n_prod = _collect_candidates(db_path, images_root, company_name, "product_main", prod_sources)
    upsert_asset(db_path, company_name, "product_main", status="ready" if n_prod > 0 else "failed")

    # Other products — 每产品 2 候选
    other_cfg = query_config.get("products_other", {})
    per_product = other_cfg.get("per_product", [])
    any_other = False
    for i, item in enumerate(per_product[:4]):
        name = item.get("name", f"product-{i}")
        asset_key = f"products_other__{name}"
        upsert_asset(db_path, company_name, asset_key, status="pending")
        sources = []
        if item.get("playwright_url"):
            sources.append({"type": "playwright", "url": item["playwright_url"]})
        for q in item.get("tavily_queries", []):
            sources.append({"type": "tavily", "query": q})
        n = _collect_candidates(db_path, images_root, company_name, asset_key, sources, max_candidates=2)
        if n > 0:
            upsert_asset(db_path, company_name, asset_key, status="ready")
            any_other = True
    if not any_other:
        upsert_asset(db_path, company_name, "products_other", status="failed")

    # Competitors — 每竞品 2 候选 + clearbit 兜底
    comp_cfg = query_config.get("competitors", {})
    per_comp = comp_cfg.get("per_comp", [])
    any_comp = False
    for i, item in enumerate(per_comp[:3]):
        name = item.get("name", f"competitor-{i}")
        asset_key = f"competitors__{name}"
        upsert_asset(db_path, company_name, asset_key, status="pending")
        sources = []
        if item.get("playwright_url"):
            sources.append({"type": "playwright", "url": item["playwright_url"]})
        for q in item.get("tavily_queries", []):
            sources.append({"type": "tavily", "query": q})
        domain = _guess_domain(name)
        if domain:
            sources.append({"type": "clearbit", "domain": domain})
        n = _collect_candidates(db_path, images_root, company_name, asset_key, sources, max_candidates=2)
        if n > 0:
            upsert_asset(db_path, company_name, asset_key, status="ready")
            any_comp = True
    if not any_comp:
        upsert_asset(db_path, company_name, "competitors", status="failed")


# ═══════════════════════════════════════════════════════════════
# 内部工具
# ═══════════════════════════════════════════════════════════════

def _parse_json_field(value) -> list | None:
    """安全解析 JSON 字符串"""
    if not value:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _guess_domain(company_name: str) -> str:
    """从公司名推测域名（简化）"""
    name = company_name.lower().strip()
    # 常见映射
    known = {
        "openai": "openai.com",
        "anthropic": "anthropic.com",
        "google": "google.com",
        "meta": "meta.com",
        "microsoft": "microsoft.com",
        "amazon": "amazon.com",
        "apple": "apple.com",
        "nvidia": "nvidia.com",
        "stability ai": "stability.ai",
        "midjourney": "midjourney.com",
        "deepseek": "deepseek.com",
        "cursor": "cursor.com",
        "notion": "notion.so",
        "linear": "linear.app",
        "vercel": "vercel.com",
        "zuma": "zuma.com",
    }
    if name in known:
        return known[name]
    # 清理 → 假设 .com
    clean = name.replace(" ", "").replace("-", "").replace(".", "")
    if clean and len(clean) >= 3:
        return f"{clean}.com"
    return ""


def _get_tavily_keys() -> list[str]:
    keys = getattr(config, "TAVILY_API_KEYS", None)
    if keys:
        return keys
    return [config.TAVILY_API_KEY] if config.TAVILY_API_KEY else []


def _is_tavily_quota_response(resp) -> bool:
    text = getattr(resp, "text", "") or ""
    return resp.status_code in (429, 432) or "usage limit" in text.lower() or "quota" in text.lower()


def _try_tavily_images(query: str, dest: str) -> str | None:
    """通过 Tavily Search API 搜索图片（include_images=True）"""
    try:
        api_keys = _get_tavily_keys()
        if not api_keys:
            return None

        data = None
        for index, api_key in enumerate(api_keys):
            resp = requests.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "include_images": True,
                    "max_results": 5,
                },
                timeout=15,
            )
            if resp.status_code >= 400:
                if _is_tavily_quota_response(resp) and index < len(api_keys) - 1:
                    continue
                return None
            data = resp.json()
            break

        if not data:
            return None
        images = data.get("images", [])
        for img in images:
            img_url = img.get("url", "") if isinstance(img, dict) else str(img)
            if not img_url:
                continue
            if _download(img_url, dest):
                return img_url
        return None
    except Exception:
        return None


def _render_osm_map(location: str, dest: str) -> bool:
    """用 OSM 静态图 + HTML pin overlay 生成地图，失败再回退 Leaflet 截图。"""
    tmp_map = None
    try:
        # Geocode
        geo_url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1"
        resp = requests.get(geo_url, headers={"User-Agent": "aistartups-cn/1.0"}, timeout=10)
        data = resp.json()
        if not data:
            return False

        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        display_name = data[0].get("display_name", location)

        # Guizang map component: static map raster + HTML pin/legend overlay.
        map_url = (f"https://staticmap.openstreetmap.de/staticmap.php"
                   f"?center={lat},{lon}&zoom=14&size=800x400&maptype=mapnik"
                   f"&markers={lat},{lon},red-pushpin")
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            tmp_map = f.name
        if _render_osm_tile_composite(lat, lon, tmp_map) or _download(map_url, tmp_map):
            if _render_static_map_card(f"file://{tmp_map}", location, display_name, dest):
                return True

        # 回退：Leaflet HTML + Playwright
        return _render_map_via_playwright(lat, lon, display_name, dest)
    except Exception:
        return False
    finally:
        if tmp_map:
            try:
                os.unlink(tmp_map)
            except Exception:
                pass


def _render_osm_tile_composite(lat: float, lon: float, dest: str,
                               width: int = 800, height: int = 400,
                               zoom: int = 14) -> bool:
    """Compose OSM raster tiles locally so the final card has no map UI chrome."""
    try:
        import math
        from io import BytesIO
        from PIL import Image

        tile_size = 256
        scale = tile_size * (2 ** zoom)
        center_x = (lon + 180.0) / 360.0 * scale
        sin_lat = math.sin(math.radians(lat))
        center_y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale

        left = center_x - width / 2
        top = center_y - height / 2
        first_x = int(math.floor(left / tile_size))
        first_y = int(math.floor(top / tile_size))
        last_x = int(math.floor((left + width) / tile_size))
        last_y = int(math.floor((top + height) / tile_size))

        canvas = Image.new("RGB", (width, height), (232, 234, 236))
        max_tile = 2 ** zoom
        headers = {"User-Agent": "aistartups-cn/1.0"}
        loaded = 0
        for x in range(first_x, last_x + 1):
            for y in range(first_y, last_y + 1):
                if y < 0 or y >= max_tile:
                    continue
                tile_x = x % max_tile
                url = f"https://tile.openstreetmap.org/{zoom}/{tile_x}/{y}.png"
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code >= 400:
                    continue
                tile = Image.open(BytesIO(resp.content)).convert("RGB")
                px = int(x * tile_size - left)
                py = int(y * tile_size - top)
                canvas.paste(tile, (px, py))
                loaded += 1

        if loaded == 0:
            return False
        canvas.save(dest, "PNG")
        return os.path.exists(dest) and os.path.getsize(dest) > 512
    except Exception:
        return False


def _render_static_map_card(map_url: str, location: str, label: str, dest: str) -> bool:
    """Render a static OSM raster inside a Guizang-style map block."""
    import tempfile

    safe_location = str(location or "Company location").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_label = str(label or location or "Location").split(",")[0].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=800,initial-scale=1">
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #f2f2f2; font-family: Inter, -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif; }}
  .map-block {{
    position: relative;
    width: 800px;
    height: 400px;
    overflow: hidden;
    background: #e8eaec;
  }}
  .map-block > img {{
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
    filter: saturate(0) contrast(1.06) brightness(1.02);
  }}
  .map-block::after {{
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background:
      linear-gradient(90deg, rgba(242,242,242,.72), rgba(242,242,242,.12) 42%, rgba(242,242,242,.28)),
      radial-gradient(circle at 50% 50%, rgba(41,184,212,.16), transparent 26%);
    mix-blend-mode: multiply;
  }}
  .map-pin {{
    position: absolute;
    left: 50%;
    top: 50%;
    z-index: 3;
    transform: translate(-50%, -50%);
  }}
  .map-pin .dot {{
    width: 16px;
    height: 16px;
    border-radius: 999px;
    background: #29B8D4;
    border: 3px solid #fff;
    box-shadow: 0 6px 18px rgba(0,0,0,.28);
  }}
  .map-pin .line {{
    position: absolute;
    left: 8px;
    top: 8px;
    width: 72px;
    height: 1px;
    background: rgba(11,15,23,.55);
  }}
  .map-pin .card {{
    position: absolute;
    left: 84px;
    top: -22px;
    width: 220px;
    padding: 10px 12px;
    background: rgba(255,255,255,.92);
    border: 1px solid rgba(11,15,23,.18);
    box-shadow: 0 14px 30px rgba(0,0,0,.12);
  }}
  .map-pin .name {{
    font-size: 16px;
    font-weight: 700;
    line-height: 1.18;
    color: #0B0F17;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .map-pin .meta {{
    display: block;
    margin-top: 4px;
    color: #5E6878;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .12em;
    text-transform: uppercase;
  }}
  .map-legend {{
    position: absolute;
    right: 14px;
    bottom: 12px;
    z-index: 3;
    padding: 6px 9px;
    background: rgba(255,255,255,.82);
    border: 1px solid rgba(11,15,23,.16);
    color: #4b5563;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .12em;
  }}
</style>
</head>
<body>
  <div class="map-block" id="map-card">
    <img src="{map_url}" alt="{safe_location}">
    <div class="map-pin">
      <div class="dot"></div><div class="line"></div>
      <div class="card"><div class="name">{safe_label}</div><span class="meta">COMPANY LOCATION</span></div>
    </div>
    <div class="map-legend">OSM STATIC · {safe_location}</div>
  </div>
</body>
</html>"""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(html)
        html_path = f.name

    try:
        with sync_playwright() as p:
            exe = _find_chromium()
            launch_args = {"headless": True}
            if exe:
                launch_args["executable_path"] = exe
            else:
                launch_args["channel"] = "chrome"
            browser = p.chromium.launch(**launch_args)
            page = browser.new_page(viewport={"width": 800, "height": 400})
            page.goto(f"file://{html_path}", wait_until="networkidle", timeout=30000)
            page.wait_for_function(
                "() => { const img = document.querySelector('#map-card img'); return img && img.complete && img.naturalWidth > 0; }",
                timeout=10000,
            )
            page.locator("#map-card").screenshot(path=dest)
            browser.close()
        return os.path.exists(dest) and os.path.getsize(dest) > 512
    except Exception:
        return False
    finally:
        try:
            os.unlink(html_path)
        except Exception:
            pass


def _render_map_via_playwright(lat: float, lon: float, label: str, dest: str) -> bool:
    """用 Leaflet + Playwright 截图生成地图图片"""
    import tempfile

    safe_label = label.replace("'", "\\'")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=800,initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body {{ margin:0; }}
  #map {{ width:800px; height:400px; }}
  .leaflet-control-attribution {{ font-size:10px; }}
</style>
</head>
<body>
<div id="map"></div>
<script>
  const map = L.map('map', {{ zoomControl: true, attributionControl: true }}).setView([{lat}, {lon}], 14);
  L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }}).addTo(map);
  L.marker([{lat}, {lon}]).addTo(map)
    .bindPopup('{safe_label}')
    .openPopup();
  // 等瓦片加载完再截图
  map.on('load', function() {{ document.title = 'ready'; }});
</script>
</body>
</html>"""

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        f.write(html)
        html_path = f.name

    try:
        with sync_playwright() as p:
            # 优先用 _find_chromium() 找本地缓存，否则回退到系统 Chrome
            exe = _find_chromium()
            launch_args = {"headless": True}
            if exe:
                launch_args["executable_path"] = exe
            else:
                launch_args["channel"] = "chrome"
            browser = p.chromium.launch(**launch_args)
            page = browser.new_page(viewport={"width": 800, "height": 400})
            page.goto(f"file://{html_path}", wait_until="networkidle", timeout=30000)
            page.screenshot(path=dest, type="png")
            browser.close()
        return os.path.exists(dest) and os.path.getsize(dest) > 512
    except Exception:
        return False
    finally:
        try:
            os.unlink(html_path)
        except Exception:
            pass


def _find_chromium() -> str:
    """在本地 Playwright 缓存或系统中查找可用的 Chromium 可执行文件"""
    import glob as _glob
    from config import config

    # 1. 优先使用配置/环境变量指定的路径
    if config.PLAYWRIGHT_CHROMIUM_PATH and os.path.exists(config.PLAYWRIGHT_CHROMIUM_PATH):
        return config.PLAYWRIGHT_CHROMIUM_PATH

    # 2. macOS: Playwright 默认缓存路径
    base = os.path.expanduser("~/Library/Caches/ms-playwright")
    for d in sorted(
        _glob.glob(f"{base}/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
        reverse=True,
    ):
        if os.path.exists(d):
            return d

    # 3. Linux: Playwright 默认缓存路径
    linux_base = os.path.expanduser("~/.cache/ms-playwright")
    for d in sorted(
        _glob.glob(f"{linux_base}/chromium-*/chrome-linux/chrome"),
        reverse=True,
    ):
        if os.path.exists(d):
            return d

    # 4. Linux: 尝试系统安装的 chromium
    for system_path in ("chromium", "chromium-browser",
                        "/usr/bin/chromium", "/usr/bin/chromium-browser",
                        "/snap/bin/chromium"):
        found = shutil.which(system_path) if not system_path.startswith("/") else system_path
        if found and os.path.exists(found):
            return found

    return ""


def _playwright_screenshot(url: str, dest: str, width: int = 900, height: int = 600):
    """Playwright 截网页全页或首屏"""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        exe = _find_chromium()
        if not exe:
            raise RuntimeError(
                "找不到 Chromium 可执行文件。请执行 'playwright install chromium' 或设置 "
                "PLAYWRIGHT_CHROMIUM_PATH 环境变量指向 chromium 可执行文件路径。"
            )
        browser = p.chromium.launch(
            headless=True,
            executable_path=exe,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        page = browser.new_page(viewport={"width": width, "height": height})
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        page.screenshot(path=dest, full_page=False)
        browser.close()


def _composite_horizontal(image_paths: list[str], dest: str, max_height: int = 400):
    """多张图水平拼接"""
    from PIL import Image
    images = []
    for p in image_paths:
        img = Image.open(p).convert("RGBA")
        h_ratio = max_height / img.height
        new_w = int(img.width * h_ratio)
        images.append(img.resize((new_w, max_height), Image.LANCZOS))

    total_w = sum(img.width for img in images) + (len(images) - 1) * 8  # 8px gap
    canvas = Image.new("RGBA", (total_w, max_height), (255, 255, 255, 255))
    x = 0
    for img in images:
        canvas.paste(img, (x, 0), img if img.mode == "RGBA" else None)
        x += img.width + 8

    canvas.save(dest, "PNG")


def _composite_grid(image_paths: list[str], dest: str, tile_size: int = 200,
                    max_cols: int = 3):
    """Logo 网格拼图（白色背景，居中排列）"""
    from PIL import Image

    n = len(image_paths)
    cols = min(n, max_cols)
    rows = (n + cols - 1) // cols

    canvas_w = cols * tile_size + (cols - 1) * 12 + 24
    canvas_h = rows * tile_size + (rows - 1) * 12 + 24
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))

    for i, p in enumerate(image_paths):
        img = Image.open(p).convert("RGBA")
        # 缩放到 tile 内
        img.thumbnail((tile_size - 20, tile_size - 20), Image.LANCZOS)
        col = i % cols
        row = i // cols
        x = 12 + col * (tile_size + 12) + (tile_size - img.width) // 2
        y = 12 + row * (tile_size + 12) + (tile_size - img.height) // 2
        canvas.paste(img, (x, y), img if img.mode == "RGBA" else None)

    canvas.save(dest, "PNG")


# ═══════════════════════════════════════════════════════════════
# 图片采集管道 — 多源变体采集器
# ═══════════════════════════════════════════════════════════════

def _geocode_location(location: str) -> tuple | None:
    """Geocode location string via OSM Nominatim. Returns (lat, lon) or None."""
    try:
        geo_url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1"
        resp = requests.get(geo_url, headers={"User-Agent": "aistartups-cn/1.0"}, timeout=10)
        data = resp.json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
        return None


def _fetch_street_view(lat: float, lon: float, api_key: str, dest: str,
                       heading: int = 0, size: str = "800x400", fov: int = 90) -> bool:
    """Download a Google Street View image. Returns True on success."""
    from urllib.parse import urlencode
    params = urlencode({
        "location": f"{lat},{lon}",
        "size": size,
        "heading": heading,
        "fov": fov,
        "key": api_key,
    })
    url = f"https://maps.googleapis.com/maps/api/streetview?{params}"
    return _download(url, dest, timeout=20)


def _collect_office_variants(db_path: str, images_root: str, company_name: str,
                             location: str, query_config: dict) -> int:
    """Card 2: map first, then supplemental street-view/Tavily candidates."""
    from asset_store import insert_variant

    count = 0
    map_variant_id = None

    if location:
        dest = _variant_path(images_root, company_name, "office", "osm_map")
        if _render_osm_map(location, dest):
            map_variant_id = insert_variant(
                db_path, company_name, "office",
                local_path=_variant_browser_path(company_name, dest),
                source_type="osm_map",
            )
            count += 1

    # Supplemental Google Street View variants.
    if config.GOOGLE_MAPS_API_KEY and location:
        latlon = _geocode_location(location)
        if latlon:
            lat, lon = latlon
            for heading in [0, 90]:
                dest = _variant_path(images_root, company_name, "office", f"gsv_{heading}")
                if _fetch_street_view(lat, lon, config.GOOGLE_MAPS_API_KEY, dest, heading=heading):
                    insert_variant(
                        db_path, company_name, "office",
                        local_path=_variant_browser_path(company_name, dest),
                        source_type="street_view",
                        source_url=f"gsv:{lat},{lon},heading={heading}",
                    )
                    count += 1

    # Supplemental Tavily building/office photos.
    for q in (query_config.get("tavily_queries") or [])[:2]:
        dest = _variant_path(images_root, company_name, "office", f"tv_{count}")
        src_url = _try_tavily_images(q, dest)
        if src_url:
            insert_variant(
                db_path, company_name, "office",
                local_path=_variant_browser_path(company_name, dest),
                source_type="web_tavily",
                source_url=src_url,
            )
            count += 1

    if map_variant_id:
        select_variant(db_path, company_name, "office", map_variant_id)

    return count


def _collect_product_main_variants(db_path: str, images_root: str, company_name: str,
                                   query_config: dict) -> int:
    """Card 4: Playwright + Tavily -> variants."""
    from asset_store import insert_variant

    count = 0

    # Playwright screenshots
    for url in (query_config.get("playwright_urls") or [])[:2]:
        if not url or not url.startswith("http"):
            continue
        dest = _variant_path(images_root, company_name, "product_main", f"pw_{count}")
        try:
            _playwright_screenshot(url, dest)
            if os.path.exists(dest) and os.path.getsize(dest) > 512:
                insert_variant(db_path, company_name, "product_main",
                               local_path=_variant_browser_path(company_name, dest), source_type="playwright", source_url=url)
                count += 1
        except Exception:
            pass

    # Tavily
    for q in (query_config.get("tavily_queries") or [])[:4]:
        if count >= 6:
            break
        dest = _variant_path(images_root, company_name, "product_main", f"tv_{count}")
        src_url = _try_tavily_images(q, dest)
        if src_url:
            insert_variant(db_path, company_name, "product_main",
                           local_path=_variant_browser_path(company_name, dest), source_type="web_tavily", source_url=src_url)
            count += 1

    return count


def _collect_products_other_variants(db_path: str, images_root: str, company_name: str,
                                     query_config: dict) -> int:
    """Card 5: Per product Playwright + Tavily -> variants."""
    from asset_store import insert_variant

    count = 0
    for i, item in enumerate((query_config.get("per_product") or [])[:4]):
        if count >= 6:
            break
        name = item.get("name", f"product-{i}")

        # Playwright
        pw_url = item.get("playwright_url", "")
        if pw_url and pw_url.startswith("http"):
            dest = _variant_path(images_root, company_name, "products_other", f"prod{i}_pw")
            try:
                _playwright_screenshot(pw_url, dest)
                if os.path.exists(dest) and os.path.getsize(dest) > 512:
                    insert_variant(db_path, company_name, "products_other",
                                   local_path=_variant_browser_path(company_name, dest), source_type="playwright",
                                   source_url=pw_url, prompt=name)
                    count += 1
            except Exception:
                pass

        # Tavily
        for q in (item.get("tavily_queries") or [])[:2]:
            if count >= 6:
                break
            dest = _variant_path(images_root, company_name, "products_other", f"prod{i}_tv_{count}")
            src_url = _try_tavily_images(q, dest)
            if src_url:
                insert_variant(db_path, company_name, "products_other",
                               local_path=_variant_browser_path(company_name, dest), source_type="web_tavily",
                               source_url=src_url, prompt=name)
                count += 1

    return count


def _collect_competitors_variants(db_path: str, images_root: str, company_name: str,
                                  query_config: dict) -> int:
    """Card 7: Per competitor Playwright + Tavily + Clearbit fallback -> variants."""
    from asset_store import insert_variant

    count = 0
    for i, item in enumerate((query_config.get("per_comp") or [])[:3]):
        if count >= 6:
            break
        name = item.get("name", f"competitor-{i}")

        # Playwright
        pw_url = item.get("playwright_url", "")
        if pw_url and pw_url.startswith("http"):
            dest = _variant_path(images_root, company_name, "competitors", f"comp{i}_pw")
            try:
                _playwright_screenshot(pw_url, dest)
                if os.path.exists(dest) and os.path.getsize(dest) > 512:
                    insert_variant(db_path, company_name, "competitors",
                                   local_path=_variant_browser_path(company_name, dest), source_type="playwright",
                                   source_url=pw_url, prompt=name)
                    count += 1
            except Exception:
                pass

        # Tavily
        for q in (item.get("tavily_queries") or [])[:2]:
            if count >= 6:
                break
            dest = _variant_path(images_root, company_name, "competitors", f"comp{i}_tv_{count}")
            src_url = _try_tavily_images(q, dest)
            if src_url:
                insert_variant(db_path, company_name, "competitors",
                               local_path=_variant_browser_path(company_name, dest), source_type="web_tavily",
                               source_url=src_url, prompt=name)
                count += 1

        # Clearbit logo fallback
        domain = _guess_domain(name)
        if domain:
            dest = _variant_path(images_root, company_name, "competitors", f"comp{i}_cb")
            if _download(f"https://logo.clearbit.com/{domain}", dest):
                insert_variant(db_path, company_name, "competitors",
                               local_path=_variant_browser_path(company_name, dest), source_type="clearbit", prompt=name)
                count += 1

    return count


# 管道入口
def collect_image_variants_pipeline(
    db_path: str, images_root: str, company_name: str,
    company_data: dict,
    progress_callback=None, job_id: str = None,
) -> dict[str, int]:
    """研究流水线图片采集阶段入口。逐一采集 4 个卡片的变体并报告进度。"""
    query_config = build_image_queries(company_data)
    location = company_data.get("location", "")

    ensure_assets_rows(db_path, company_name)

    stages = [
        ("office", "卡片2：公司位置地图", lambda: _collect_office_variants(
            db_path, images_root, company_name, location, query_config.get("office", {}))),
        ("product_main", "卡片4：主产品截图", lambda: _collect_product_main_variants(
            db_path, images_root, company_name, query_config.get("product_main", {}))),
        ("products_other", "卡片5：其他产品截图", lambda: _collect_products_other_variants(
            db_path, images_root, company_name, query_config.get("products_other", {}))),
        ("competitors", "卡片7：竞争格局截图", lambda: _collect_competitors_variants(
            db_path, images_root, company_name, query_config.get("competitors", {}))),
    ]

    results = {}
    for i, (asset_key, label, collector) in enumerate(stages):
        if progress_callback:
            progress_callback("图片采集", {
                "message": label,
                "card": i + 1,
                "total": len(stages),
            })
        try:
            n = collector()
            results[asset_key] = n
            if n > 0:
                variants = list_variants(db_path, company_name, asset_key)
                if variants and not any(v.get("is_selected") for v in variants):
                    select_variant(db_path, company_name, asset_key, variants[0]["id"])
            upsert_asset(db_path, company_name, asset_key,
                        status="ready" if n > 0 else "failed")
            if progress_callback:
                progress_callback("图片采集", {
                    "message": f"{label}完成：{n} 张候选图",
                    "card": i + 1,
                    "total": len(stages),
                    "count": n,
                })
        except Exception as e:
            results[asset_key] = 0
            upsert_asset(db_path, company_name, asset_key, status="failed")
            if progress_callback:
                progress_callback("图片采集", {
                    "message": f"{label}失败：{e}",
                    "card": i + 1,
                    "total": len(stages),
                })

    return results
