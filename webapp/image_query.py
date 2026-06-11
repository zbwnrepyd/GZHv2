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


# 占位符常量 — L3 无法提取时填入的值，不应出现在搜索查询中
_ZUNQUE = "暂缺"


def _valid(v) -> bool:
    """值非空且不是占位符"""
    if v is None:
        return False
    s = str(v).strip()
    return bool(s) and s != _ZUNQUE


def build_image_queries(record: dict) -> dict:
    """
    从研究数据中生成结构化的图片采集策略。
    所有 allow_generic=False —— 搜不到就 failed，不用通用图。
    自动过滤「暂缺」占位符，避免无意义搜索查询。
    """
    company_name = record.get("company_name", "")
    website_url = record.get("website_url", "")
    raw_product_name = record.get("main_product_name", "")
    product_name = raw_product_name if _valid(raw_product_name) else ""

    other_products_all = _json_array(record.get("other_products"))
    competitors_all = _json_array(record.get("competitors"))
    # 过滤名为「暂缺」或空的条目
    other_products = [p for p in other_products_all if _valid(p.get("name"))]
    competitors = [c for c in competitors_all if _valid(c.get("name"))]

    office_hints = record.get("office_photo_hints") or {}
    if isinstance(office_hints, str):
        try:
            office_hints = json.loads(office_hints)
        except (json.JSONDecodeError, TypeError):
            office_hints = {}

    newsroom_url = office_hints.get("newsroom_url", "")
    about_url = office_hints.get("about_url", "")

    # 产品 Tavily 查询：有有效产品名时用它，否则只用公司名
    if product_name:
        product_tavily_queries = [
            f'"{product_name}" "{company_name}" interface screenshot',
            f'"{product_name}" app dashboard',
            f'"{company_name}" mobile app store screenshot',
            f'"{product_name}" product review screenshot',
        ]
    else:
        product_tavily_queries = [
            f'"{company_name}" product interface screenshot',
            f'"{company_name}" app dashboard',
            f'"{company_name}" mobile app store screenshot',
        ]

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
            "tavily_queries": product_tavily_queries,
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
