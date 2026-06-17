"""GitHub Agent — 开源与技术信号采集

P2: 从骨架扩展为实际实现。
- 搜索 GitHub repos（README、docs、releases、issues）
- 提取技术栈、开发者采用度、产品成熟度、社区信号
- Stars/forks/contributors/last_commit/license/topics
"""
from __future__ import annotations
import json
import os
import re
import requests
from typing import Optional
from research_agents.agents import BaseAgent, AgentResult

# GitHub API 配置
_GITHUB_API_BASE = "https://api.github.com"
_GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _github_headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    if _GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {_GITHUB_TOKEN}"
    return headers


def _github_api(path: str) -> Optional[dict | list]:
    """调用 GitHub REST API。"""
    try:
        proxies = None
        proxy_url = os.environ.get("HTTPS_PROXY")
        if proxy_url:
            proxies = {"https": proxy_url}

        url = f"{_GITHUB_API_BASE}{path}"
        resp = requests.get(url, headers=_github_headers(),
                          timeout=20, proxies=proxies)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 403:
            # 速率限制
            return None
        return None
    except Exception:
        return None


def _search_github_repos(company_name: str, website_host: str = "",
                         max_results: int = 5) -> list[dict]:
    """搜索与公司相关的 GitHub repos。"""
    results = []

    # Query 1: 公司名直接搜索
    q = f'"{company_name}" in:name,description,readme archived:false'
    data = _github_api(f"/search/repositories?q={q}&sort=stars&order=desc&per_page={max_results}")
    if isinstance(data, dict):
        items = data.get("items", [])
        # 按 stars 过滤
        items = [i for i in items if i.get("stargazers_count", 0) > 0]
        results.extend(items)

    # Query 2: 官网 host 搜索
    if website_host and website_host not in company_name.lower():
        q2 = f'"{website_host}" in:name,description,readme archived:false'
        data2 = _github_api(f"/search/repositories?q={q2}&sort=stars&order=desc&per_page=3")
        if isinstance(data2, dict):
            items2 = data2.get("items", [])
            results.extend(items2)

    # 去重
    seen = set()
    unique = []
    for r in results:
        rid = r.get("id")
        if rid in seen:
            continue
        seen.add(rid)
        unique.append(r)

    return unique[:max_results]


def _fetch_repo_details(full_name: str) -> dict:
    """获取 repo 的详细信息（README、issues、community 指标等）。"""
    details = {}

    # 基本信息
    repo = _github_api(f"/repos/{full_name}")
    if isinstance(repo, dict):
        details["stars"] = repo.get("stargazers_count", 0)
        details["forks"] = repo.get("forks_count", 0)
        details["open_issues"] = repo.get("open_issues_count", 0)
        details["license"] = (repo.get("license") or {}).get("spdx_id", "")
        details["topics"] = repo.get("topics", [])
        details["language"] = repo.get("language", "")
        details["description"] = repo.get("description", "")
        details["created_at"] = repo.get("created_at", "")
        details["updated_at"] = repo.get("updated_at", "")
        details["pushed_at"] = repo.get("pushed_at", "")
        details["homepage"] = repo.get("homepage", "")

    # 贡献者数
    details["contributors"] = -1

    # README
    readme = _github_api(f"/repos/{full_name}/readme")
    if isinstance(readme, dict):
        import base64
        content = readme.get("content", "")
        if content:
            try:
                decoded = base64.b64decode(content).decode("utf-8", errors="replace")
                details["readme"] = decoded[:5000]
            except Exception:
                details["readme"] = ""

    # 最新 release
    releases = _github_api(f"/repos/{full_name}/releases?per_page=1")
    if isinstance(releases, list) and releases:
        details["latest_release"] = releases[0].get("tag_name", "")
        details["release_date"] = releases[0].get("published_at", "")

    # ── Issues (最近10条) ──
    issues = _github_api(
        f"/repos/{full_name}/issues?per_page=10&sort=updated&state=all"
    )
    if isinstance(issues, list):
        issue_summaries = []
        for issue in issues[:10]:
            title = (issue.get("title") or "")[:200]
            state = issue.get("state", "")
            labels = [l.get("name", "") for l in issue.get("labels", [])]
            comments = issue.get("comments", 0)
            issue_summaries.append(
                f"[{state}] {title} (labels: {', '.join(labels[:5])}, "
                f"comments: {comments})"
            )
        details["issues_summary"] = "\n".join(issue_summaries)
        details["issue_count"] = len(issue_summaries)

    # ── Discussions (通过 GraphQL 或 search API 尝试) ──
    # GitHub REST API 不直接支持 discussions，尝试通过 search 获取
    disc_data = _github_api(
        f"/search/issues?q=repo:{full_name}+type:discussion&per_page=5&sort=updated"
    )
    if isinstance(disc_data, dict) and disc_data.get("items"):
        disc_summaries = []
        for d in disc_data["items"][:5]:
            disc_summaries.append(
                f"{d.get('title', '')[:200]} (comments: {d.get('comments', 0)})"
            )
        details["discussions_summary"] = "\n".join(disc_summaries)
        details["discussion_count"] = len(disc_summaries)

    return details


# ── 技术信号提取 ──
_TECH_STACK_KEYWORDS = [
    "python", "javascript", "typescript", "rust", "go", "golang",
    "react", "vue", "angular", "next.js", "node.js",
    "aws", "gcp", "azure", "kubernetes", "docker",
    "postgresql", "mongodb", "redis", "graphql",
    "llm", "gpt", "transformer", "pytorch", "tensorflow",
    "api", "sdk", "cli", "webhook",
]

_MATURITY_KEYWORDS = [
    "v1.", "v2.", "v3.", "stable", "production", "beta", "alpha",
    "major", "release", "changelog", "breaking change",
]

_COMMUNITY_KEYWORDS = [
    "contributing", "code of conduct", "discussion", "community",
    "slack", "discord", "forum",
]


def _extract_tech_stack(text: str) -> list[str]:
    """从文本中提取技术栈。"""
    text_lower = text.lower()
    found = set()
    for kw in _TECH_STACK_KEYWORDS:
        if kw.lower() in text_lower:
            found.add(kw)
    return list(found)


class GitHubAgent(BaseAgent):
    """GitHub 开源信号深采"""

    agent_name = "github"

    def _run(self, company_key: str, context: dict) -> AgentResult:
        display_name = context.get("display_name", company_key)
        website_host = context.get("website_host", "")
        company_name = display_name or company_key

        # ── 搜索 repos ──
        repos = _search_github_repos(company_name, website_host, max_results=5)
        if not repos:
            return AgentResult(
                agent_name=self.agent_name,
                status="ok",
                note=f"No GitHub repos found for {company_name}",
            )

        documents = []
        field_candidates = []
        evidence_spans = []
        total_stars = 0

        for repo in repos[:5]:
            full_name = repo.get("full_name", "")
            html_url = repo.get("html_url", "")
            description = repo.get("description", "")
            stars = repo.get("stargazers_count", 0)
            forks = repo.get("forks_count", 0)
            language = repo.get("language", "")
            topics = repo.get("topics", [])
            total_stars += stars

            # 获取详细信息
            details = _fetch_repo_details(full_name)
            readme_text = details.get("readme", "") or description or ""

            # ── 文档 ──
            doc = {
                "source_type": "github",
                "source_url": html_url,
                "title": f"GitHub: {full_name}",
                "raw_text": f"{description}\nStars: {stars}\nForks: {forks}\n"
                           f"Language: {language}\nTopics: {', '.join(topics)}\n"
                           f"{readme_text[:3000]}",
                "trust_tier": "developer",
                "intent": "tech_signal",
            }
            documents.append(doc)

            # ── 技术栈信号 ──
            combined_text = f"{description} {' '.join(topics)} {readme_text}"
            tech_stack = _extract_tech_stack(combined_text)
            if tech_stack:
                field_candidates.append({
                    "field_key": "tech_stack",
                    "candidate_value": f"[GitHub] {', '.join(tech_stack[:8])}",
                    "confidence": 0.7,
                    "agent_name": self.agent_name,
                    "source_url": html_url,
                })

            # ── 产品成熟度信号 ──
            maturity_hits = sum(
                1 for kw in _MATURITY_KEYWORDS
                if kw.lower() in combined_text.lower()
            )
            if maturity_hits >= 2:
                field_candidates.append({
                    "field_key": "product_maturity",
                    "candidate_value": f"[GitHub] {stars}★ {forks} forks, "
                                      f"topics: {', '.join(topics[:5])}",
                    "confidence": 0.6,
                    "agent_name": self.agent_name,
                    "source_url": html_url,
                })

            # ── 证据片段 ──
            if description.strip():
                evidence_spans.append({
                    "field_key": "github_signal",
                    "quote_text": f"{full_name}: {description[:300]}",
                    "source_url": html_url,
                    "confidence": 0.7,
                })

            # ── 开发者采用度 ──
            if stars >= 100:
                field_candidates.append({
                    "field_key": "developer_adoption",
                    "candidate_value": f"[GitHub] {full_name}: {stars}★, "
                                      f"{forks} forks, {language}",
                    "confidence": 0.75,
                    "agent_name": self.agent_name,
                    "source_url": html_url,
                })

            # ── 社区活跃度（issues + discussions）──
            issue_count = details.get("issue_count", 0)
            disc_count = details.get("discussion_count", 0)
            if issue_count > 0 or disc_count > 0:
                field_candidates.append({
                    "field_key": "community_health",
                    "candidate_value": f"[GitHub] {full_name}: {issue_count} recent issues, "
                                      f"{disc_count} discussions",
                    "confidence": 0.55,
                    "agent_name": self.agent_name,
                    "source_url": html_url,
                })
                # 证据片段
                issues_text = details.get("issues_summary", "")
                if issues_text.strip():
                    evidence_spans.append({
                        "field_key": "community_health",
                        "quote_text": issues_text[:500],
                        "source_url": html_url,
                        "confidence": 0.5,
                    })

        return AgentResult(
            agent_name=self.agent_name,
            status="ok",
            field_candidates=field_candidates,
            documents=documents,
            evidence_spans=evidence_spans,
            note=f"GitHubAgent: {len(repos)} repos found, "
                 f"{total_stars} total stars, "
                 f"{len(field_candidates)} signal candidates for {company_name}",
        )
