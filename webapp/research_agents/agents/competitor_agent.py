"""竞品分析 Agent — 竞争对手识别与分析

P2 最小实现：包装现有竞品分析逻辑。
"""
from __future__ import annotations
from research_agents.agents import BaseAgent, AgentResult


class CompetitorAgent(BaseAgent):
    agent_name = "competitor"

    def _run(self, company_key: str, context: dict) -> AgentResult:
        return AgentResult(
            agent_name=self.agent_name,
            status="ok",
            note="CompetitorAgent skeleton — competitive analysis delegated to existing pipeline",
        )
