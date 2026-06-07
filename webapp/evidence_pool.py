"""证据池 — URL 规范化、来源打分、实体匹配、去重。

将 Tavily/GitHub/YouTube/官网的原始结果标准化为 EvidenceItem，
按 URL 去重，按来源权威性 + 实体匹配度打分，过滤低质量证据。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


DROP_QUERY_KEYS = {
    "fbclid", "gclid", "ref", "ref_src",
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
}


@dataclass
class EvidenceItem:
    source: str = ""
    intent: str = ""
    title: str = ""
    url: str = ""
    normalized_url: str = ""
    content: str = ""
    raw_content: str = ""
    source_score: float = 0.0
    entity_score: float = 0.0
    final_score: float = 0.0
    query: str = ""
    collected_at: str = ""


# ── URL 规范化 ──

def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/")

    kept: list[tuple[str, str]] = []
    for k, v in parse_qsl(parsed.query, keep_blank_values=False):
        lk = k.lower()
        if lk in DROP_QUERY_KEYS:
            continue
        kept.append((k, v))

    return urlunparse((scheme, netloc, path, "", urlencode(kept), ""))


# ── 来源打分 ──

_SOURCE_SCORES: dict[str, float] = {
    "website": 1.00,
    "github_official": 0.85,
    "yc": 0.85,
    "product_hunt": 0.85,
    "techcrunch": 0.75,
    "the_verge": 0.75,
    "venturebeat": 0.75,
    "forbes": 0.75,
    "crunchbase": 0.70,
    "pitchbook": 0.70,
    "youtube": 0.65,
    "hacker_news": 0.40,
    "reddit": 0.40,
    "twitter": 0.40,
    "other": 0.30,
}


def _classify_source(url: str, source_type: str) -> str:
    if source_type == "website":
        return "website"
    host = urlparse(url).netloc.lower().replace("www.", "")
    if "github.com" in host:
        return "github_official"
    if "ycombinator.com" in host:
        return "yc"
    if "producthunt.com" in host:
        return "product_hunt"
    if "techcrunch.com" in host:
        return "techcrunch"
    if "theverge.com" in host:
        return "the_verge"
    if "venturebeat.com" in host:
        return "venturebeat"
    if "forbes.com" in host:
        return "forbes"
    if "crunchbase.com" in host:
        return "crunchbase"
    if "pitchbook.com" in host:
        return "pitchbook"
    if "youtube.com" in host:
        return "youtube"
    if "news.ycombinator.com" in host:
        return "hacker_news"
    if "reddit.com" in host:
        return "reddit"
    if any(x in host for x in ["twitter.com", "x.com"]):
        return "twitter"
    return "other"


def source_score(url: str, source_type: str) -> float:
    cls = _classify_source(url, source_type)
    return _SOURCE_SCORES.get(cls, 0.30)


# ── 实体匹配 ──

def entity_score(title: str, url: str, content: str,
                 display_name: str, website_host: str,
                 root_domain: str) -> float:
    text = f"{title} {url} {content}".lower()
    score = 0.0
    if website_host and website_host in text:
        score += 0.55
    if display_name.lower() in text:
        score += 0.25
    if root_domain and root_domain in text:
        score += 0.10
    if any(anchor in text for anchor in
           ["ai", "startup", "founder", "funding", "pricing", "product"]):
        score += 0.10
    return min(score, 1.0)


def final_score(url: str, source_type: str, title: str, content: str,
                display_name: str, website_host: str,
                root_domain: str) -> float:
    s = source_score(url, source_type)
    e = entity_score(title, url, content,
                     display_name, website_host, root_domain)
    return round(s * 0.6 + e * 0.4, 4)


# ── 去重 ──

def dedupe_evidence(items: list[EvidenceItem]) -> list[EvidenceItem]:
    by_url: dict[str, EvidenceItem] = {}
    for item in items:
        key = item.normalized_url
        if not key:
            continue
        old = by_url.get(key)
        if old is None or item.final_score > old.final_score:
            by_url[key] = item
        elif old is not None:
            existing = set(old.intent.split(","))
            existing.update(item.intent.split(","))
            old.intent = ",".join(sorted(existing))
    return sorted(by_url.values(), key=lambda x: x.final_score, reverse=True)


def filter_evidence(items: list[EvidenceItem],
                    min_score: float = 0.35) -> list[EvidenceItem]:
    return [i for i in items if i.final_score >= min_score]
