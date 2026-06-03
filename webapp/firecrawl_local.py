"""本地网页抓取 — trafilatura + BeautifulSoup4 回退"""
from __future__ import annotations
import trafilatura
import requests
from markdownify import markdownify as md


def scrape_url(url: str, timeout: int = 30) -> dict:
    """抓取网页，提取正文并转为 Markdown。

    Returns:
        {"markdown": "...", "title": "...", "error": None}
        or  {"markdown": "", "error": "..."}
    """
    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
            timeout=(20, timeout),
            allow_redirects=True,
        )
        resp.raise_for_status()

        html = resp.text
        if not html or len(html) < 100:
            return {"markdown": "", "title": "", "error": "页面内容过短"}

        # trafilatura 提取正文
        extracted = trafilatura.extract(
            html,
            output_format="markdown",
            with_metadata=True,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )

        if extracted and len(extracted) > 50:
            return {"markdown": extracted, "title": "", "error": None}

        # 回退：直接用 markdownify 转换 body
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        body = soup.find("body") or soup
        fallback = md(str(body), heading_style="ATX", strip=["img", "script", "style"])
        if fallback and len(fallback) > 50:
            return {"markdown": fallback, "title": "", "error": None}

        return {"markdown": "", "title": "", "error": "无法提取有效内容"}

    except requests.exceptions.Timeout:
        return {"markdown": "", "error": "请求超时"}
    except requests.exceptions.ConnectionError:
        return {"markdown": "", "error": "无法连接到目标网站"}
    except Exception as e:
        return {"markdown": "", "error": str(e)}
