"""社区信号 Agent — Product Hunt/Hacker News/Reddit/G2/Capterra 采集

P2: 从禁用骨架扩展为启用实现。
- Product Hunt: 搜索产品发布、投票数、评论
- Hacker News: 搜索讨论、Show HN
- Reddit: 搜索相关讨论
- 提取用户痛点、10分钟惊喜点、替代竞品、传播钩子、使用场景
限制: 社区来源不能用于确认融资、收入、学历、团队规模等硬事实。
"""
from __future__ import annotations
import json
import os
import re
import requests
from typing import Optional
from research_agents.agents import BaseAgent, AgentResult

# Tavily API 配置
_TAVILY_ENDPOINT = "https://api.tavily.com/search"


def _get_tavily_keys() -> list[str]:
    """获取所有可用的 Tavily API Key。"""
    keys_str = os.environ.get("TAVILY_API_KEYS", "")
    if keys_str:
        return [k.strip() for k in keys_str.split(",") if k.strip()]
    single = os.environ.get("TAVILY_API_KEY", "")
    return [single] if single else []


def _tavily_search(query: str, max_results: int = 5,
                   include_domains: str = "",
                   search_depth: str = "basic") -> list[dict]:
    """通过 Tavily 搜索指定域。"""
    keys = _get_tavily_keys()
    if not keys:
        return []

    domains = [d.strip() for d in include_domains.split(",") if d.strip()] if include_domains else None

    for api_key in keys:
        try:
            proxies = None
            proxy_url = os.environ.get("HTTPS_PROXY")
            if proxy_url:
                proxies = {"https": proxy_url}

            payload = {
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
            }
            if domains:
                payload["include_domains"] = domains

            resp = requests.post(
                _TAVILY_ENDPOINT,
                json=payload,
                timeout=25,
                proxies=proxies,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
            if resp.status_code == 429:
                continue
        except Exception:
            continue
    return []


# ── 社区信号关键词 ──
_PAIN_POINT_KEYWORDS = [
    "frustrat", "pain point", "problem", "struggle", "hard",
    "difficult", "expensive", "slow", "broken", "missing",
    "痛点", "问题", "困难", "麻烦",
]

_ALTERNATIVE_KEYWORDS = [
    "alternative", "replace", "instead of", "vs", "versus",
    "better than", "compared to", "switch from",
    "替代", "替换", "竞品",
]

_HOOK_KEYWORDS = [
    "amazing", "incredible", "impressive", "game changer",
    "revolutionary", "finally", "check this out",
    "惊人", "革命性", "终于", "神器",
]

_USE_CASE_KEYWORDS = [
    "use case", "workflow", "how i use", "setup",
    "integration", "daily", "routine",
    "使用场景", "使用方式", "案例",
]

_COMMUNITY_DOMAINS = {
    "product_hunt": "producthunt.com",
    "hacker_news": "news.ycombinator.com",
    "reddit": "reddit.com",
    "g2": "g2.com",
    "capterra": "capterra.com",
}


def _keyword_hits(text: str, keywords: list[str]) -> int:
    """计算文本中关键词命中数。"""
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


class CommunityAgent(BaseAgent):
    """社区信号采集 — Product Hunt, Hacker News, Reddit 等"""

    agent_name = "community"
    enabled = True  # P2: 启用

    def _run(self, company_key: str, context: dict) -> AgentResult:
        display_name = context.get("display_name", company_key)
        company_name = display_name or company_key
        website_host = context.get("website_host", "")

        # ── 多源搜索 ──
        search_name = company_name
        all_results = []

        # Product Hunt
        ph_results = _tavily_search(
            f'"{company_name}" site:producthunt.com',
            max_results=3,
        )
        for r in ph_results:
            r["_community_source"] = "product_hunt"
        all_results.extend(ph_results)

        # Hacker News
        hn_results = _tavily_search(
            f'"{company_name}" site:news.ycombinator.com',
            max_results=3,
        )
        for r in hn_results:
            r["_community_source"] = "hacker_news"
        all_results.extend(hn_results)

        # Reddit (public discussion)
        reddit_results = _tavily_search(
            f'"{company_name}" site:reddit.com',
            max_results=2,
        )
        for r in reddit_results:
            r["_community_source"] = "reddit"
        all_results.extend(reddit_results)

        if not all_results:
            return AgentResult(
                agent_name=self.agent_name,
                status="ok",
                note=f"No community signals found for {company_name}",
            )

        # ── 去重 ──
        seen_urls = set()
        unique_results = []
        for r in all_results:
            url = r.get("url", "")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            unique_results.append(r)

        # ── 提取信号 ──
        documents = []
        field_candidates = []
        evidence_spans = []

        for r in unique_results[:8]:
            title = r.get("title", "")
            content = r.get("content", "")
            url = r.get("url", "")
            comm_source = r.get("_community_source", "community")
            combined_text = f"{title}\n{content}"

            # 文档
            documents.append({
                "source_type": comm_source,
                "source_url": url,
                "title": title,
                "raw_text": content[:3000],
                "trust_tier": "community",
                "intent": "community_signal",
            })

            hp = _keyword_hits(combined_text, _PAIN_POINT_KEYWORDS)
            ha = _keyword_hits(combined_text, _ALTERNATIVE_KEYWORDS)
            hh = _keyword_hits(combined_text, _HOOK_KEYWORDS)
            hu = _keyword_hits(combined_text, _USE_CASE_KEYWORDS)

            # 用户痛点
            if hp >= 2:
                field_candidates.append({
                    "field_key": "user_pain_points",
                    "candidate_value": f"[{comm_source}] {title}: {content[:200]}",
                    "confidence": 0.5,
                    "agent_name": self.agent_name,
                    "source_url": url,
                })
                evidence_spans.append({
                    "field_key": "user_pain_points",
                    "quote_text": content[:300],
                    "source_url": url,
                    "confidence": 0.45,
                })

            # 替代竞品
            if ha >= 2:
                field_candidates.append({
                    "field_key": "alternative_competitors",
                    "candidate_value": f"[{comm_source}] {title}: {content[:200]}",
                    "confidence": 0.5,
                    "agent_name": self.agent_name,
                    "source_url": url,
                })

            # 传播钩子
            if hh >= 2:
                field_candidates.append({
                    "field_key": "viral_hook",
                    "candidate_value": f"[{comm_source}] {title}: {content[:200]}",
                    "confidence": 0.45,
                    "agent_name": self.agent_name,
                    "source_url": url,
                })

            # 使用场景
            if hu >= 2:
                field_candidates.append({
                    "field_key": "usage_scenarios",
                    "candidate_value": f"[{comm_source}] {title}: {content[:200]}",
                    "confidence": 0.5,
                    "agent_name": self.agent_name,
                    "source_url": url,
                })

        return AgentResult(
            agent_name=self.agent_name,
            status="ok",
            field_candidates=field_candidates,
            documents=documents,
            evidence_spans=evidence_spans,
            note=f"CommunityAgent: {len(unique_results)} results from "
                 f"{len(set(r['_community_source'] for r in unique_results if '_community_source' in r))} sources, "
                 f"{len(field_candidates)} signal candidates for {company_name}",
        )
