"""七图自动采集管道 — logo / office / product / competitors / other_products"""
from __future__ import annotations
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import shutil

import requests

from config import config
from asset_store import (
    ASSET_KEYS, ASSET_TO_CARD, CARD_ASSET_MAP,
    ensure_assets_rows, upsert_asset, get_asset,
)

# 忽略 SSL 警告（部分图片源证书可能有问题）
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def asset_dir(images_root: str, company_name: str) -> str:
    """返回某公司的图片目录，确保存在"""
    d = os.path.join(images_root, company_name)
    os.makedirs(d, exist_ok=True)
    return d


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

def collect_office(db_path: str, images_root: str, company_name: str,
                   location: str = "", search_keywords: str = "") -> dict | None:
    """
    通过 Playwright 搜索公司办公楼图片。
    搜索策略：公司名 + "office building" 或 公司名 + "总部大楼"
    """
    dest_dir = asset_dir(images_root, company_name)
    dest = os.path.join(dest_dir, "office.png")

    # 搜索关键词
    if search_keywords:
        queries = [f"{search_keywords} office building", f"{search_keywords} headquarters"]
    else:
        queries = [f"{company_name} office building", f"{company_name} headquarters", f"{company_name} 办公室"]

    img_url = _search_and_download_image(queries, dest)
    if img_url:
        upsert_asset(db_path, company_name, "office",
                    local_path=f"/images/{company_name}/office.png",
                    source_type="web_search", source_url=img_url, status="ready")
        return {"local_path": f"/images/{company_name}/office.png"}

    # Fallback: OSM 静态地图
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
                    website_url: str = "", product_page_url: str = "") -> dict | None:
    url = product_page_url or website_url
    if not url:
        upsert_asset(db_path, company_name, "product_main", status="failed")
        return None

    dest_dir = asset_dir(images_root, company_name)
    dest = os.path.join(dest_dir, "product_main.png")

    try:
        _playwright_screenshot(url, dest)
        upsert_asset(db_path, company_name, "product_main",
                    local_path=f"/images/{company_name}/product_main.png",
                    source_type="screenshot", source_url=url, status="ready")
        return {"local_path": f"/images/{company_name}/product_main.png"}
    except Exception as e:
        upsert_asset(db_path, company_name, "product_main", status="failed",
                    meta={"error": str(e)})
        return None


# ═══════════════════════════════════════════════════════════════
# 4. 其他产品图（搜索 + 拼接）
# ═══════════════════════════════════════════════════════════════

def collect_other_products(db_path: str, images_root: str, company_name: str,
                           other_products: list[dict] = None) -> dict | None:
    """
    other_products: [{"name": "产品A", "def": "...", "highlight": "..."}, ...]
    每个产品搜一张图 → PIL 水平拼接
    """
    if not other_products:
        upsert_asset(db_path, company_name, "products_other", status="failed")
        return None

    dest_dir = asset_dir(images_root, company_name)
    product_images = []

    for i, product in enumerate(other_products[:5]):  # 最多 5 个产品
        name = product.get("name", f"product-{i}")
        tmp_dest = os.path.join(dest_dir, f"_tmp_product_{i}.png")
        queries = [f"{company_name} {name}", f"{name} product screenshot"]
        img_url = _search_and_download_image(queries, tmp_dest)
        if img_url and os.path.getsize(tmp_dest) > 512:
            product_images.append(tmp_dest)

    if not product_images:
        upsert_asset(db_path, company_name, "products_other", status="failed")
        return None

    dest = os.path.join(dest_dir, "products_other.png")
    try:
        _composite_horizontal(product_images, dest)
        upsert_asset(db_path, company_name, "products_other",
                    local_path=f"/images/{company_name}/products_other.png",
                    source_type="web_search", source_url="", status="ready")
        for tmp in product_images:
            try: os.remove(tmp)
            except OSError: pass
        return {"local_path": f"/images/{company_name}/products_other.png"}
    except Exception:
        upsert_asset(db_path, company_name, "products_other", status="failed")
        return None


# ═══════════════════════════════════════════════════════════════
# 5. 竞品 Logo 拼图
# ═══════════════════════════════════════════════════════════════

def compose_competitors(db_path: str, images_root: str, company_name: str,
                        competitors: list[dict] = None) -> dict | None:
    """
    competitors: [{"name": "OpenAI", "product": "...", "data": "..."}, ...]
    逐一抓 favicon → PIL Grid 拼图
    """
    if not competitors:
        upsert_asset(db_path, company_name, "competitors", status="failed")
        return None

    dest_dir = asset_dir(images_root, company_name)
    logo_paths = []
    source_urls = []

    for i, comp in enumerate(competitors[:6]):  # 最多 6 个竞品
        name = comp.get("name", f"competitor-{i}")
        # 尝试从公司名推断域名（简化版）
        domain = _guess_domain(name)
        if not domain:
            continue

        tmp_dest = os.path.join(dest_dir, f"_tmp_comp_{i}.png")
        logo_url = f"https://logo.clearbit.com/{domain}"
        if _download(logo_url, tmp_dest):
            logo_paths.append(tmp_dest)
            source_urls.append(logo_url)
        else:
            # Fallback: Google Favicon
            fav_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
            if _download(fav_url, tmp_dest):
                logo_paths.append(tmp_dest)
                source_urls.append(fav_url)

    if not logo_paths:
        upsert_asset(db_path, company_name, "competitors", status="failed")
        return None

    dest = os.path.join(dest_dir, "competitors.png")
    try:
        _composite_grid(logo_paths, dest)
        upsert_asset(db_path, company_name, "competitors",
                    local_path=f"/images/{company_name}/competitors.png",
                    source_type="composite", source_url=", ".join(source_urls),
                    status="ready")
        for tmp in logo_paths:
            try: os.remove(tmp)
            except OSError: pass
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

    # 解析 JSON 字段
    other_products = _parse_json_field(company_data.get("other_products"))
    competitors = _parse_json_field(company_data.get("competitors"))

    # 1. Logo
    r = collect_logo(db_path, images_root, company_name, company_url, website_url)
    results["logo"] = r

    # 2. Office
    r = collect_office(db_path, images_root, company_name, location,
                       search_keywords=company_name)
    results["office"] = r

    # 3. 主产品截图
    r = capture_product(db_path, images_root, company_name, website_url)
    results["product_main"] = r

    # 4. 其他产品
    r = collect_other_products(db_path, images_root, company_name, other_products)
    results["products_other"] = r

    # 5. 竞品 Logo
    r = compose_competitors(db_path, images_root, company_name, competitors)
    results["competitors"] = r

    # 6-7. flywheel / timeline 不在此自动采集，由 infographic.py 处理
    for key in ("flywheel", "timeline"):
        r = get_asset(db_path, company_name, key)
        results[key] = r

    return results


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


def _search_and_download_image(queries: list[str], dest: str) -> str | None:
    """
    多源图片搜索：Tavily 图片搜索 → Lorem Flickr → Picsum。
    遍历所有 queries，返回第一个成功的结果 URL。
    """
    for query in queries:
        # 源1: Tavily 图片搜索（精准、真实来源）
        img_url = _try_tavily_images(query, dest)
        if img_url:
            return img_url

        # 源2: Lorem Flickr（Flickr 关键词随机图）
        img_url = _try_lorem_flickr(query, dest)
        if img_url:
            return img_url

        # 源3: Picsum（随机图兜底）
        img_url = _try_picsum(dest)
        if img_url:
            return img_url

    return None


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


def _try_lorem_flickr(query: str, dest: str) -> str | None:
    """从 Lorem Flickr 获取基于关键词的随机图片"""
    try:
        keywords = query.replace(" ", ",")
        url = f"https://loremflickr.com/800/400/{keywords}"
        if _download(url, dest):
            return url
        return None
    except Exception:
        return None


def _try_picsum(dest: str) -> str | None:
    """从 Picsum 获取随机图片（兜底）"""
    try:
        url = "https://picsum.photos/800/400"
        if _download(url, dest):
            return url
        return None
    except Exception:
        return None


def _render_osm_map(location: str, dest: str) -> bool:
    """用 OpenStreetMap Nominatim + Static Map 生成地图截图"""
    try:
        # Geocode
        geo_url = f"https://nominatim.openstreetmap.org/search?q={location}&format=json&limit=1"
        resp = requests.get(geo_url, headers={"User-Agent": "aistartups-cn/1.0"}, timeout=10)
        data = resp.json()
        if not data:
            return False

        lat = data[0]["lat"]
        lon = data[0]["lon"]

        # Static map
        map_url = (f"https://staticmap.openstreetmap.de/staticmap.php"
                   f"?center={lat},{lon}&zoom=14&size=800x400&maptype=mapnik"
                   f"&markers={lat},{lon},red-pushpin")
        return _download(map_url, dest)
    except Exception:
        return False


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
