"""P2 Agent 骨架 — identity/source_planning/official/query/github/media/community/insight/metric/competitor/report

非核心 agent 采用最小接口+fallback 模式，不得破坏主流程。
所有 agent 实现统一的 AgentProtocol 接口。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Protocol


@dataclass
class AgentResult:
    """Agent 统一返回结构"""
    agent_name: str
    status: str = "ok"  # ok|partial|failed|skipped
    field_candidates: list[dict] = field(default_factory=list)
    documents: list[dict] = field(default_factory=list)
    evidence_spans: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    note: str = ""


class AgentProtocol(Protocol):
    """所有 Agent 必须实现的协议"""
    agent_name: str

    def run(self, company_key: str, context: dict) -> AgentResult:
        ...


class BaseAgent:
    """Agent 基类，提供统一错误处理和空回退"""

    agent_name: str = "base"
    enabled: bool = True

    def run(self, company_key: str, context: dict) -> AgentResult:
        if not self.enabled:
            return AgentResult(agent_name=self.agent_name, status="skipped",
                              note="agent disabled")
        try:
            return self._run(company_key, context)
        except Exception as e:
            return AgentResult(
                agent_name=self.agent_name,
                status="failed",
                errors=[str(e)[:500]],
                note=f"{self.agent_name}: execution failed — not blocking",
            )

    def _run(self, company_key: str, context: dict) -> AgentResult:
        raise NotImplementedError("Subclass must implement _run")
