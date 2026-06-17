"""指标解析 Agent — 运营指标验证与降级

P2 最小实现：提供指标验证和降级建议。
"""
from __future__ import annotations
from research_agents.agents import BaseAgent, AgentResult


class MetricAgent(BaseAgent):
    agent_name = "metric"

    def _run(self, company_key: str, context: dict) -> AgentResult:
        return AgentResult(
            agent_name=self.agent_name,
            status="ok",
            note="MetricAgent skeleton — delegates to FieldResolver for metric status resolution",
        )
