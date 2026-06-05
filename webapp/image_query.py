"""图片搜索词生成 — 为 asset_pipeline 提供结构化搜索配置"""
from __future__ import annotations
import json


def _json_array(value) -> list:
    """安全解析 JSON 字符串为列表"""
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def build_image_queries(record: dict) -> dict:
    """
    从研究数据中生成结构化的图片采集策略。
    所有 allow_generic=False —— 搜不到就 failed，不用通用图。
    """
    company_name = record.get("company_name", "")
    website_url = record.get("website_url", "")
    product_name = record.get("main_product_name", "")

    other_products = _json_array(record.get("other_products"))
    competitors = _json_array(record.get("competitors"))
    office_hints = record.get("office_photo_hints") or {}
    if isinstance(office_hints, str):
        try:
            office_hints = json.loads(office_hints)
        except (json.JSONDecodeError, TypeError):
            office_hints = {}

    newsroom_url = office_hints.get("newsroom_url", "")
    about_url = office_hints.get("about_url", "")

    return {
        # ── office：公司真实照片 ──────────────────────────────
        "office": {
            "scrape_urls": [u for u in [about_url, newsroom_url] if u],
            "tavily_queries": [
                f'"{company_name}" office team photo',
                f'"{company_name}" headquarters building',
                f'"{company_name}" founders team',
            ],
            "allow_generic": False,
        },

        # ── 卡片4：主产品截图 ────────────────────────────────
        "product_main": {
            "playwright_urls": [
                u for u in [
                    record.get("main_product_img_src", ""),
                    website_url,
                ] if u and u.startswith("http")
            ],
            "tavily_queries": [
                f'"{product_name}" "{company_name}" interface screenshot',
                f'"{product_name}" app dashboard',
                f'"{company_name}" mobile app store screenshot',
                f'"{product_name}" product review screenshot',
            ],
            "allow_generic": False,
        },

        # ── 卡片5：其他产品截图 ──────────────────────────────
        "products_other": {
            "per_product": [
                {
                    "name": p.get("name", ""),
                    "playwright_url": p.get("url", ""),
                    "tavily_queries": [
                        f'"{p.get("name")}" "{company_name}" interface',
                        f'"{company_name}" "{p.get("name")}" screenshot',
                    ],
                }
                for p in other_products[:4]
            ],
            "allow_generic": False,
        },

        # ── 卡片7：竞品产品截图 ──────────────────────────────
        "competitors": {
            "per_comp": [
                {
                    "name": c.get("name", ""),
                    "playwright_url": c.get("url", ""),
                    "tavily_queries": [
                        f'"{c.get("name")}" product interface screenshot',
                        f'"{c.get("name")}" app UI',
                        f'"{c.get("name")}" product advertisement screenshot',
                    ],
                }
                for c in competitors[:3]
            ],
            "fallback": "clearbit_logo",
            "allow_generic": False,
        },
    }
