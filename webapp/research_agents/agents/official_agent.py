"""OfficialAgent — 官网深爬，抓取关键页面文本。

P1 最小可用实现：
- 按 16 个固定路径抓取（/, /about, /company, /team, /founders,
  /pricing, /customers, /case-studies, /blog, /news, /press,
  /docs, /changelog, /security, /careers）
- 每页最多 5000 字，总字符上限 50000
- 失败不阻塞主流程
- 结果写入 source_documents，标题自动标记路径
"""
from __future__ import annotations
from typing import Optional

# 固定抓取路径（按字段支撑优先级排列）
OFFICIAL_PATHS: list[str] = [
    "/",
    "/about",
    "/company",
    "/team",
    "/founders",
    "/pricing",
    "/customers",
    "/case-studies",
    "/blog",
    "/news",
    "/press",
    "/docs",
    "/changelog",
    "/security",
    "/careers",
]

# 路径 → 可支撑字段映射
PATH_FIELD_MAP: dict[str, list[str]] = {
    "/": ["company_name", "company_def", "core_business"],
    "/about": ["company_def", "location", "founded_date", "core_business",
               "company_achievements", "industry_positioning"],
    "/company": ["company_def", "core_business", "core_competency"],
    "/team": ["founder_name", "founder_bg", "team_size", "team_highlight"],
    "/founders": ["founder_name", "founder_edu", "founder_bg",
                  "founder_achievement"],
    "/pricing": ["pricing_summary", "pricing_tiers", "pricing_strategy",
                 "revenue_model"],
    "/customers": ["customer_names", "customer_segment_primary",
                   "customer_selection_reasons"],
    "/case-studies": ["customer_names", "customer_selection_reasons",
                      "customer_choice_evidence", "product_pain_points"],
    "/blog": ["product_core_features", "product_tech_stack",
              "company_achievements", "timeline_events"],
    "/news": ["company_achievements", "funding_info", "timeline_events"],
    "/press": ["company_achievements", "funding_info"],
    "/docs": ["product_tech_stack", "product_core_features",
              "product_usage_playbook"],
    "/changelog": ["product_core_features", "product_tech_stack"],
    "/security": ["product_tech_stack", "core_competency"],
    "/careers": ["team_size", "tech_stack", "regional_market_focus"],
}

MAX_CHARS_PER_PAGE = 5000
MAX_TOTAL_CHARS = 50000


def _extract_text_from_html(html: str) -> str:
    """简单 HTML 正文提取（不依赖 trafilatura 时使用）。"""
    import re
    # 移除 script/style
    text = re.sub(r'<(script|style|noscript|iframe|svg)[^>]*>.*?</\1>',
                  '', html, flags=re.DOTALL | re.IGNORECASE)
    # 移除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', text)
    # 合并空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def crawl_official_site(company_url: str, company_key: str = "",
                        timeout: int = 15) -> list[dict]:
    """抓取官网关键路径，返回 source_documents 行列表。

    每个元素: {"path": str, "title": str, "text": str, "error": str|None}
    失败不抛异常——单页失败不影响其他页。
    """
    import requests
    from urllib.parse import urljoin, urlparse

    base_url = company_url.strip().rstrip("/")
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"
    parsed_base = urlparse(base_url)

    results = []
    total_chars = 0
    seen = set()

    for path in OFFICIAL_PATHS:
        url = urljoin(base_url, path)
        nurl = url.rstrip("/") if url.endswith("/") else url
        if nurl in seen:
            continue
        seen.add(nurl)

        result = {
            "path": path,
            "url": nurl,
            "title": f"{company_key or parsed_base.netloc}{path}",
            "text": "",
            "error": None,
        }

        try:
            resp = requests.get(
                nurl,
                headers={
                    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/120.0.0.0 Safari/537.36"),
                },
                timeout=timeout,
                allow_redirects=True,
            )
            if resp.status_code != 200:
                result["error"] = f"HTTP {resp.status_code}"
                results.append(result)
                continue

            content_type = resp.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                result["error"] = f"non-HTML content type: {content_type[:60]}"
                results.append(result)
                continue

            html = resp.text
            if not html:
                result["error"] = "empty response"
                results.append(result)
                continue

            # 尝试 trafilatura 提取，回退简单清洗
            text = ""
            try:
                import trafilatura
                extracted = trafilatura.extract(html, include_comments=False,
                                                include_tables=False)
                if extracted:
                    text = extracted
            except Exception:
                pass

            if not text:
                text = _extract_text_from_html(html)

            # 截断
            if len(text) > MAX_CHARS_PER_PAGE:
                text = text[:MAX_CHARS_PER_PAGE - 3].rstrip() + "..."

            result["text"] = text
            total_chars += len(text)

        except requests.Timeout:
            result["error"] = f"timeout ({timeout}s)"
        except requests.ConnectionError:
            result["error"] = "connection failed"
        except Exception as e:
            result["error"] = str(e)[:200]

        results.append(result)

        if total_chars >= MAX_TOTAL_CHARS:
            break

    return results


def crawl_and_store(db_path: str, company_url: str, company_key: str,
                    run_id: str = "", timeout: int = 15) -> int:
    """抓取官网并写入 source_documents。返回写入的文档数。"""
    from research.document_store import insert_document

    docs = crawl_official_site(company_url, company_key, timeout=timeout)
    count = 0
    for doc in docs:
        if doc["error"] or not doc["text"].strip():
            continue
        trust_tier = "official" if doc["path"] in ("/", "/about", "/company",
                                                    "/team", "/founders",
                                                    "/pricing") else "official"
        source_type = _path_to_source_type(doc["path"])
        doc_id = insert_document(
            db_path=db_path,
            company_key=company_key,
            source_type=source_type,
            source_url=doc["url"],
            title=doc["title"],
            raw_text=doc["text"],
            trust_tier=trust_tier,
            intent="overview",
            run_id=run_id,
        )
        if doc_id > 0:
            count += 1
    return count


def _path_to_source_type(path: str) -> str:
    if path in ("/", "/about", "/company"):
        return "official_site"
    if path in ("/team", "/founders"):
        return "official_site"
    if path == "/pricing":
        return "pricing_page"
    if path in ("/customers", "/case-studies"):
        return "case_study"
    if path in ("/blog", "/news", "/press"):
        return "official_blog"
    if path == "/docs":
        return "official_site"
    return "official_site"
