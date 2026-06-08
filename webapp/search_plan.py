"""搜索计划生成 — 按意图生成多 query，覆盖 founders/funding/product/pricing/competitors 等。

deep 模式覆盖 10 类意图，standard 模式覆盖 6 类核心意图。
每类意图使用多个搜索别名（原始名、小写、首字母大写、域名等）生成 query。
"""
from __future__ import annotations
from dataclasses import dataclass
from config import config


@dataclass
class TavilyQuery:
    query: str
    intent: str
    term: str


@dataclass
class SearchPlan:
    tavily_queries: list[TavilyQuery]
    github_queries: list[str]
    youtube_queries: list[str]
    query_count: int


TAVILY_QUERY_TEMPLATES: dict[str, list[str]] = {
    "overview": [
        "{term} AI startup overview product company",
        "{term} official website about product",
    ],
    "founders": [
        "{term} founder education background LinkedIn",
        "{term} founder interview biography",
    ],
    "funding": [
        "{term} funding seed series investors valuation",
        "{term} raised funding TechCrunch Crunchbase PitchBook",
    ],
    "product": [
        "{term} product features screenshot demo docs",
        "{term} use cases customers product tour",
    ],
    "pricing": [
        "{term} pricing plans subscription",
        "site:{host} pricing plans",
    ],
    "competitors": [
        "{term} competitors alternatives vs",
        "{term} market map competitors",
    ],
    "gtm": [
        "{term} go to market growth strategy customers",
        "{term} Product Hunt launch users growth",
    ],
    "timeline": [
        "{term} launch history timeline founded",
        "{term} announcement rebrand acquisition",
    ],
    "community": [
        "{term} Product Hunt Hacker News Reddit Twitter review",
    ],
    "interview": [
        "{term} founder interview podcast YouTube",
        "{term} CEO interview video",
    ],
}


def _depth() -> str:
    return config.RESEARCH_DEPTH


def _query_budget() -> int:
    if _depth() == "deep":
        return config.TAVILY_QUERY_BUDGET_DEEP
    return config.TAVILY_QUERY_BUDGET_STANDARD


def build_search_plan(display_name: str, root_domain: str,
                      website_host: str, aliases: list[str]) -> SearchPlan:
    depth = _depth()
    budget = _query_budget()

    core_intents = ["overview", "founders", "funding",
                    "product", "pricing", "competitors"]
    if depth == "deep":
        core_intents.extend(["gtm", "timeline", "community", "interview"])

    tavily_queries: list[TavilyQuery] = []
    terms = list(dict.fromkeys(aliases))[:6]

    for intent in core_intents:
        templates = TAVILY_QUERY_TEMPLATES.get(intent, [])
        for term in terms[:4]:
            for tmpl in templates[:1]:
                if len(tavily_queries) >= budget:
                    break
                q = tmpl.format(term=term, host=website_host,
                                root=root_domain)
                tavily_queries.append(
                    TavilyQuery(query=q, intent=intent, term=term))
            if len(tavily_queries) >= budget:
                break
        if len(tavily_queries) >= budget:
            break

    github_queries: list[str] = []
    if root_domain:
        github_queries.append(f"{root_domain} in:name,description,readme")
    if display_name:
        github_queries.append(f"{display_name} in:name,description,readme")
    if website_host:
        github_queries.append(f"{website_host} in:readme")
    github_queries = list(dict.fromkeys(
        [q for q in github_queries if q.strip()]))

    youtube_queries: list[str] = []
    if display_name:
        youtube_queries.append(f"{display_name} founder interview")
    if root_domain:
        youtube_queries.append(f"{root_domain} founder interview")
    if display_name:
        youtube_queries.append(f"{display_name} product demo")
    if website_host:
        youtube_queries.append(f"{website_host} founder interview")
    youtube_queries = list(dict.fromkeys(
        [q for q in youtube_queries if q.strip()]))

    return SearchPlan(
        tavily_queries=tavily_queries,
        github_queries=github_queries,
        youtube_queries=youtube_queries,
        query_count=len(tavily_queries),
    )
