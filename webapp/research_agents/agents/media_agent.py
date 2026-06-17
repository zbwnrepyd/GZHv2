"""媒体 Agent — YouTube 视频/访谈采集 + 字幕提取分析

P2: 从骨架扩展为实际实现。
- 搜索 founder interview / product demo / podcast
- 提取标题、描述、频道信息
- 分析创始人背景、GTM、产品理念、冷启动、关键指标信号
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
                   search_depth: str = "basic",
                   include_domains: str = "youtube.com") -> list[dict]:
    """通过 Tavily 搜索 YouTube 视频。"""
    keys = _get_tavily_keys()
    if not keys:
        return []

    for api_key in keys:
        try:
            proxies = None
            proxy_url = os.environ.get("HTTPS_PROXY")
            if proxy_url:
                proxies = {"https": proxy_url}

            resp = requests.post(
                _TAVILY_ENDPOINT,
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": max_results,
                    "search_depth": search_depth,
                    "include_domains": [include_domains] if include_domains else None,
                },
                timeout=25,
                proxies=proxies,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
            # 额度限制 → 尝试下一个 key
            if resp.status_code == 429:
                continue
        except Exception:
            continue
    return []


# ── YouTube 字幕获取 ──
def _get_youtube_transcript(video_id: str) -> str:
    """尝试获取 YouTube 视频字幕（使用 YouTube Data API caption 端点）。"""
    api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if not api_key:
        return ""

    try:
        proxies = None
        proxy_url = os.environ.get("HTTPS_PROXY")
        if proxy_url:
            proxies = {"https": proxy_url}

        # 先获取 caption 列表
        caption_url = (
            f"https://www.googleapis.com/youtube/v3/captions"
            f"?videoId={video_id}&part=snippet&key={api_key}"
        )
        resp = requests.get(caption_url, timeout=10, proxies=proxies)
        if resp.status_code != 200:
            return ""

        captions_data = resp.json()
        items = captions_data.get("items", [])
        if not items:
            return ""

        # 优先英文/自动字幕
        en_caption = None
        auto_caption = None
        for item in items:
            snippet = item.get("snippet", {})
            lang = snippet.get("language", "")
            track = snippet.get("trackKind", "")
            if lang == "en" and track == "standard":
                en_caption = item
                break
            elif lang == "en" and track == "ASR":
                auto_caption = item
            elif auto_caption is None and track == "ASR":
                auto_caption = item

        target = en_caption or auto_caption
        if not target:
            return ""

        # 下载字幕（需要 OAuth，但可以尝试用 download 端点）
        caption_id = target.get("id", "")
        if not caption_id:
            return ""

        download_url = (
            f"https://www.googleapis.com/youtube/v3/captions/{caption_id}"
            f"?key={api_key}&tfmt=srt"
        )
        resp = requests.get(download_url, timeout=15, proxies=proxies)
        if resp.status_code == 200:
            text = resp.text
            # 清理 SRT 时间戳
            cleaned = re.sub(r'\d+\n\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}', '', text)
            cleaned = re.sub(r'<[^>]+>', '', cleaned)
            cleaned = re.sub(r'\n\s*\n', '\n', cleaned).strip()
            return cleaned[:5000]
        return ""
    except Exception:
        return ""


def _extract_video_id(url: str) -> str:
    """从 YouTube URL 提取 video_id。"""
    patterns = [
        r'youtube\.com/watch\?v=([^&]+)',
        r'youtu\.be/([^?]+)',
        r'youtube\.com/embed/([^?]+)',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return ""


# ── 信号提取 ──
_FOUNDER_KEYWORDS = [
    "founder", "ceo", "cto", "co-founder", "创始人",
    "interview", "story", "journey", "background",
]

_GTM_KEYWORDS = [
    "go to market", "gtm", "launch", "growth",
    "customer acquisition", "sales strategy", "distribution",
    "上市", "增长策略", "获客",
]

_COLD_START_KEYWORDS = [
    "cold start", "chicken and egg", "first customer",
    "initial traction", "early days", "launch",
    "冷启动", "早期用户", "种子用户",
]

_PRODUCT_KEYWORDS = [
    "product", "feature", "demo", "tutorial",
    "use case", "workflow", "integration",
    "产品", "功能", "演示",
]

_METRIC_KEYWORDS = [
    "revenue", "arr", "mrr", "users", "customers",
    "growth rate", "retention", "churn",
    "收入", "用户数", "增长",
]


def _keyword_score(text: str, keywords: list[str]) -> float:
    """计算文本与关键词列表的匹配度（0-1）。"""
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    if not hits:
        return 0.0
    return min(hits / len(keywords) * 3, 1.0)


class MediaAgent(BaseAgent):
    """YouTube 视频/访谈采集 + 信号提取"""

    agent_name = "media"

    def _run(self, company_key: str, context: dict) -> AgentResult:
        display_name = context.get("display_name", company_key)
        website_host = context.get("website_host", "")
        company_name = display_name or company_key

        # ── 搜索 query ──
        queries = []
        if website_host:
            queries.append(f'"{company_name}" founder interview site:youtube.com')
            queries.append(f'"{company_name}" product demo site:youtube.com')
            queries.append(f'"{company_name}" podcast site:youtube.com')
        else:
            queries.append(f'"{company_name}" interview site:youtube.com')
            queries.append(f'"{company_name}" demo site:youtube.com')

        all_results = []
        for q in queries[:2]:  # 限制 query 数量
            results = _tavily_search(q, max_results=3, search_depth="basic",
                                     include_domains="youtube.com")
            all_results.extend(results)

        if not all_results:
            return AgentResult(
                agent_name=self.agent_name,
                status="ok",
                note=f"No YouTube results found for {company_name}",
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

        for r in unique_results[:5]:
            title = r.get("title", "")
            content = r.get("content", "")
            url = r.get("url", "")
            combined_text = f"{title}\n{content}"

            doc = {
                "source_type": "youtube",
                "source_url": url,
                "title": title,
                "raw_text": content[:3000],
                "trust_tier": "media",
                "intent": "media_analysis",
            }
            documents.append(doc)

            # 提取 video_id 并尝试获取字幕
            video_id = _extract_video_id(url)
            transcript = ""
            if video_id:
                transcript = _get_youtube_transcript(video_id)
                if transcript:
                    combined_text += f"\n{transcript[:3000]}"

            # 创始人信号
            founder_score = _keyword_score(combined_text, _FOUNDER_KEYWORDS)
            if founder_score > 0.3:
                field_candidates.append({
                    "field_key": "founder_bg",
                    "candidate_value": f"[Media] {title}: {content[:200]}",
                    "confidence": round(0.4 + founder_score * 0.4, 2),
                    "agent_name": self.agent_name,
                    "source_url": url,
                })

            # GTM 信号
            gtm_score = _keyword_score(combined_text, _GTM_KEYWORDS)
            if gtm_score > 0.3:
                field_candidates.append({
                    "field_key": "gtm_motion",
                    "candidate_value": f"[Media] {title}: {content[:200]}",
                    "confidence": round(0.4 + gtm_score * 0.4, 2),
                    "agent_name": self.agent_name,
                    "source_url": url,
                })

            # 冷启动信号
            cold_start_score = _keyword_score(combined_text, _COLD_START_KEYWORDS)
            if cold_start_score > 0.3:
                field_candidates.append({
                    "field_key": "cold_start",
                    "candidate_value": f"[Media] {title}: {content[:200]}",
                    "confidence": round(0.4 + cold_start_score * 0.4, 2),
                    "agent_name": self.agent_name,
                    "source_url": url,
                })

            # 产品信号
            product_score = _keyword_score(combined_text, _PRODUCT_KEYWORDS)
            if product_score > 0.3:
                field_candidates.append({
                    "field_key": "product_pain_points",
                    "candidate_value": f"[Media] {title}: {content[:200]}",
                    "confidence": round(0.4 + product_score * 0.4, 2),
                    "agent_name": self.agent_name,
                    "source_url": url,
                })

            # 指标信号
            metric_score = _keyword_score(combined_text, _METRIC_KEYWORDS)
            if metric_score > 0.3:
                for kw in ["arr", "mrr", "revenue", "users", "customers"]:
                    if kw.lower() in combined_text.lower():
                        field_candidates.append({
                            "field_key": kw.upper() if kw.isupper() else kw,
                            "candidate_value": f"[Media] {title}: {content[:200]}",
                            "confidence": 0.5,
                            "agent_name": self.agent_name,
                            "source_url": url,
                        })

            # 证据片段
            if content.strip():
                evidence_spans.append({
                    "field_key": "media_source",
                    "quote_text": content[:500],
                    "source_url": url,
                    "confidence": 0.6,
                })

        return AgentResult(
            agent_name=self.agent_name,
            status="ok",
            field_candidates=field_candidates,
            documents=documents,
            evidence_spans=evidence_spans,
            note=f"MediaAgent: {len(unique_results)} YouTube results, "
                 f"{len(field_candidates)} signal candidates extracted for {company_name}",
        )
