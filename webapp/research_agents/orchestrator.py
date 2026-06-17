"""研究编排器 — orchestrator

PDF §10: 协调多 Agent 采集流程。
- 输入公司名/官网 → CompanyIdentityAgent → SourcePlanningAgent → 多 Agent 并行采集
- 管理 Agent 生命周期、结果收集、错误处理
- 不替代 pipeline.py，作为 Agent 层的编排入口
"""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional, Callable

from research_agents.agents import AgentResult, BaseAgent


@dataclass
class OrchestratorState:
    """编排器运行状态"""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    company_key: str = ""
    company_name: str = ""
    website_url: str = ""
    status: str = "idle"  # idle|running|completed|failed
    started_at: str = ""
    finished_at: str = ""

    # Agent 结果
    identity: Optional[AgentResult] = None
    source_plan: Optional[AgentResult] = None
    collection_results: dict[str, AgentResult] = field(default_factory=dict)
    resolution_results: dict[str, AgentResult] = field(default_factory=dict)

    # 汇总
    total_documents: int = 0
    total_evidence_spans: int = 0
    total_field_candidates: int = 0
    errors: list[str] = field(default_factory=list)


class Orchestrator:
    """多 Agent 研究编排器。

    使用方式:
        orch = Orchestrator(db_path)
        state = orch.run("sardine.ai", {"display_name": "Sardine", "website_url": "https://sardine.ai"})
    """

    def __init__(self, db_path: str, progress_callback: Callable = None):
        self.db_path = db_path
        self._progress = progress_callback or (lambda step, msg, **kw: None)
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent):
        """注册 Agent。"""
        self._agents[agent.agent_name] = agent

    def _report(self, step: str, message: str, **kw):
        try:
            self._progress(step, message, **kw)
        except Exception:
            pass

    def run(self, company_key: str, context: dict,
            cancel_token=None) -> OrchestratorState:
        """执行完整的研究编排流程。"""
        state = OrchestratorState(
            company_key=company_key,
            company_name=context.get("display_name", company_key),
            website_url=context.get("website_url", ""),
        )

        import datetime
        state.started_at = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        state.status = "running"

        try:
            # ── Phase 1: 身份归一化 ──
            self._report("编排", "Phase 1: 公司身份归一化...")
            identity_agent = self._agents.get("identity")
            if identity_agent:
                state.identity = identity_agent.run(company_key, context)
                if state.identity and state.identity.status == "ok":
                    # 提取身份信息更新 company_key
                    pass

            # ── Phase 2: 采集计划 ──
            self._report("编排", "Phase 2: 生成采集计划...")
            source_planner = self._agents.get("source_planning")
            if source_planner:
                state.source_plan = source_planner.run(company_key, context)

            # ── Phase 3: 多 Agent 并行采集 ──
            self._report("编排", "Phase 3: 并行采集...")
            collection_agents = [
                name for name in ["official", "query", "github", "media",
                                  "community", "insight"]
                if name in self._agents
            ]
            # 串行执行（安全优先，不引入线程复杂性）
            for name in collection_agents:
                if cancel_token and cancel_token.is_set():
                    state.status = "cancelled"
                    return state
                try:
                    result = self._agents[name].run(company_key, context)
                    state.collection_results[name] = result
                    if result.status != "failed":
                        state.total_documents += len(result.documents)
                        state.total_evidence_spans += len(result.evidence_spans)
                        state.total_field_candidates += len(
                            result.field_candidates)
                    self._report(
                        "编排",
                        f"  {name}: {result.status} — "
                        f"{len(result.field_candidates)} candidates, "
                        f"{len(result.documents)} docs",
                    )
                except Exception as e:
                    state.errors.append(f"{name}: {e}")
                    self._report("编排", f"  {name}: FAILED — {e}")

            # ── Phase 4: 结果汇总 ──
            self._report("编排",
                         f"Phase 4: 采集完成 — "
                         f"{state.total_documents} docs, "
                         f"{state.total_evidence_spans} spans, "
                         f"{state.total_field_candidates} candidates")

            state.status = "completed"
        except Exception as e:
            state.status = "failed"
            state.errors.append(str(e))
            self._report("编排", f"编排异常: {e}")

        state.finished_at = datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
        return state

    def collect_field_candidates(self, state: OrchestratorState) -> list[dict]:
        """从所有 Agent 结果中收集 field_candidates。"""
        all_candidates = []
        for result in state.collection_results.values():
            if result and result.status != "failed":
                all_candidates.extend(result.field_candidates)
        return all_candidates

    def collect_documents(self, state: OrchestratorState) -> list[dict]:
        """从所有 Agent 结果中收集 documents。"""
        all_docs = []
        for result in state.collection_results.values():
            if result and result.status != "failed":
                all_docs.extend(result.documents)
        return all_docs


def create_default_orchestrator(db_path: str,
                                progress_callback: Callable = None) -> Orchestrator:
    """创建预注册了所有可用 Agent 的编排器。"""
    orch = Orchestrator(db_path, progress_callback)

    # 注册所有可用的 Agent（失败不阻塞）
    agent_modules = [
        ("identity", "research_agents.agents.identity_agent", "IdentityAgent"),
        ("source_planning", "research_agents.agents.source_planning_agent",
         "SourcePlanningAgent"),
        ("official", "research_agents.agents.official_agent", "OfficialAgent"),
        ("query", "research_agents.agents.query_agent", "QueryAgent"),
        ("github", "research_agents.agents.github_agent", "GitHubAgent"),
        ("media", "research_agents.agents.media_agent", "MediaAgent"),
        ("community", "research_agents.agents.community_agent", "CommunityAgent"),
        ("insight", "research_agents.agents.insight_agent", "InsightAgent"),
    ]

    for name, module_path, class_name in agent_modules:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            agent_cls = getattr(mod, class_name)
            orch.register(agent_cls())
        except Exception as e:
            orch._report("编排", f"Agent {name} 注册失败: {e}")

    return orch
