"""公司身份归一化 Agent

P2 最小实现：复用 company_identity.py，输出标准化的 CompanyIdentity。
"""
from __future__ import annotations
from research_agents.agents import BaseAgent, AgentResult
from company_identity import build_company_identity


class IdentityAgent(BaseAgent):
    agent_name = "identity"

    def _run(self, company_key: str, context: dict) -> AgentResult:
        company_name = context.get("company_name", company_key)
        company_url = context.get("company_url", "")
        identity = build_company_identity(company_name, company_url)
        return AgentResult(
            agent_name=self.agent_name,
            field_candidates=[{
                "field_key": "company_identity",
                "candidate_value": identity.company_key,
                "agent_name": self.agent_name,
                "display_name": identity.display_name,
                "website_host": identity.website_host,
                "aliases": identity.aliases,
            }],
        )
