"""图片搜索：Pexels / Unsplash / Tavily 三源统一入口"""
from __future__ import annotations
import requests
from config import config


def search_pexels(query: str, lang: str = "en", page: int = 1,
                  per_page: int = 9) -> dict:
    api_key = config.PEXELS_API_KEY
    if not api_key:
        return {"results": [], "error": "PEXELS_API_KEY not configured"}

    url = "https://api.pexels.com/v1/search"
    headers = {"Authorization": api_key}
    params = {"query": query, "page": page, "per_page": per_page,
              "locale": "zh-CN" if lang == "zh" else "en-US"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return {"results": [], "error": str(e)}

    data = resp.json()
    return {
        "results": [
            {
                "id": f"pexels_{p['id']}",
                "thumbnail_url": p["src"]["medium"],
                "full_url": p["src"]["large2x"],
                "source": "pexels",
                "source_page": p["url"],
                "author": p["photographer"],
                "license": "Pexels License",
            }
            for p in data.get("photos", [])
        ],
        "total": data.get("total_results", 0),
    }


def search_unsplash(query: str, page: int = 1, per_page: int = 9) -> dict:
    access_key = config.UNSPLASH_ACCESS_KEY
    if not access_key:
        return {"results": [], "error": "UNSPLASH_ACCESS_KEY not configured"}

    url = "https://api.unsplash.com/search/photos"
    params = {"query": query, "page": page, "per_page": per_page,
              "orientation": "landscape"}
    headers = {"Authorization": f"Client-ID {access_key}"}
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return {"results": [], "error": str(e)}

    data = resp.json()
    return {
        "results": [
            {
                "id": f"unsplash_{p['id']}",
                "thumbnail_url": p["urls"]["small"],
                "full_url": p["urls"]["regular"],
                "source": "unsplash",
                "source_page": p["links"]["html"],
                "author": p["user"]["name"],
                "license": "Unsplash License",
            }
            for p in data.get("results", [])
        ],
        "total": data.get("total", 0),
    }


def search_tavily_images(query: str) -> dict:
    from pipeline import _search_tavily_query

    result = _search_tavily_query(query, include_images=True)
    images = result.get("images", [])

    def _extract_url(img, i: int) -> str:
        if isinstance(img, dict):
            return img.get("url", "")
        return str(img) if img else ""

    return {
        "results": [
            {
                "id": f"tavily_{i}",
                "thumbnail_url": url,
                "full_url": url,
                "source": "tavily",
                "source_page": url,
                "author": "",
                "license": "未知，请核实版权",
            }
            for i, img in enumerate(images)
            for url in [_extract_url(img, i)]
            if url and url.startswith("http")
        ],
        "total": len(images),
    }


def search_images(query: str, source: str = "pexels",
                  lang: str = "en", page: int = 1, per_page: int = 9) -> dict:
    if source == "pexels":
        return search_pexels(query, lang=lang, page=page, per_page=per_page)
    elif source == "unsplash":
        return search_unsplash(query, page=page, per_page=per_page)
    elif source == "tavily":
        return search_tavily_images(query)
    else:
        return {"results": [], "error": f"未知 source: {source}"}
