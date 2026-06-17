"""内部洞察 Agent — 行业均值 + 历史样本复用

P2 最小实现：提供 LTV/CAC 等私有指标的行业基准值。
"""
from __future__ import annotations
from research_agents.agents import BaseAgent, AgentResult

# SaaS 行业基准（来源：公开报告汇总）
_INDUSTRY_BENCHMARKS: dict[str, dict] = {
    "ltv": {"value": "6:1–8:1", "status": "industry_avg",
            "note": "SaaS 行业中位数，不代表公司披露"},
    "cac": {"value": "$500–$5,000", "status": "industry_avg",
            "note": "SaaS 行业区间，不代表公司披露"},
    "ltv_cac_ratio": {"value": "3:1–5:1", "status": "industry_avg",
                      "note": "SaaS 行业健康基准，不代表公司披露"},
    "gross_margin": {"value": "70%–80%", "status": "industry_avg",
                     "note": "SaaS 行业中位数，不代表公司披露"},
    "churn_rate": {"value": "3%–7% 月", "status": "industry_avg",
                   "note": "SaaS 行业区间，不代表公司披露"},
    "burn_rate": {"value": "N/A", "status": "unavailable",
                  "note": "公司差异极大，无通用基准"},
    "runway_months": {"value": "18–24 月", "status": "industry_avg",
                      "note": "SaaS 行业参考，不代表公司披露"},
}


class InsightAgent(BaseAgent):
    agent_name = "insight"

    def _run(self, company_key: str, context: dict) -> AgentResult:
        candidates = []
        for fk, info in _INDUSTRY_BENCHMARKS.items():
            candidates.append({
                "field_key": fk,
                "candidate_value": info["value"],
                "agent_name": self.agent_name,
                "confidence": 0.3,
                "status": info["status"],
                "reasoning_summary": info["note"],
            })
        return AgentResult(
            agent_name=self.agent_name,
            field_candidates=candidates,
            note="Industry benchmarks provided — must display disclaimer '不代表公司披露'",
        )
