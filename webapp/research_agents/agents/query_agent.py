"""查询搜索 Agent — Tavily 搜索整合

P2 最小实现：包装现有 Tavily 搜索逻辑，输出标准化 AgentResult。
"""
from __future__ import annotations
from research_agents.agents import BaseAgent, AgentResult


class QueryAgent(BaseAgent):
    agent_name = "query"

    def _run(self, company_key: str, context: dict) -> AgentResult:
        # 最小实现：搜索逻辑已在 pipeline._search_tavily 中
        return AgentResult(
            agent_name=self.agent_name,
            status="ok",
            note="Tavily search delegated to pipeline._search_tavily — agent provides result wrapper only",
        )
