"""报告生成 Agent — Standard/Business/Spread 文案生成

P2 最小实现：包装现有 LLM 层调用，生成多版本文案。
"""
from __future__ import annotations
from research_agents.agents import BaseAgent, AgentResult


class ReportAgent(BaseAgent):
    agent_name = "report"

    def _run(self, company_key: str, context: dict) -> AgentResult:
        # Standard/Business/Spread 文案由 L0-L3 LLM 分析生成
        # 此 Agent 负责结果结构化
        return AgentResult(
            agent_name=self.agent_name,
            status="ok",
            note="ReportAgent skeleton — report generation delegated to L0-L3 pipeline",
        )
