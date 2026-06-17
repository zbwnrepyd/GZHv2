"""查询规划 Agent

P2 最小实现：根据字段 manifest 生成采集任务优先级排序。
"""
from __future__ import annotations
from research_agents.agents import BaseAgent, AgentResult


class SourcePlanningAgent(BaseAgent):
    agent_name = "source_planning"

    def _run(self, company_key: str, context: dict) -> AgentResult:
        # 最小实现：返回字段优先级排序
        field_priorities = [
            {"field_key": "company_name", "priority": "A", "source": "official"},
            {"field_key": "funding_info", "priority": "A", "source": "search"},
            {"field_key": "founder_name", "priority": "A", "source": "official"},
            {"field_key": "market_size_value", "priority": "C", "source": "market_report"},
            {"field_key": "cac", "priority": "D", "source": "unavailable"},
        ]
        return AgentResult(
            agent_name=self.agent_name,
            field_candidates=[
                {"field_key": "source_plan", "candidate_value": str(field_priorities),
                 "agent_name": self.agent_name}
            ],
        )
