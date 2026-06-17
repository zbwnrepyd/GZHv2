"""研究 Agent 编排系统

P2: 多 Agent 并行采集 + 论坛校验 + 字段解析 + 存储
非核心 Agent 可最小接口 + fallback，不得破坏主流程。
"""
from __future__ import annotations

# 论坛
from research_agents.forum.moderator import ForumModerator, ForumReport, ForumFinding
from research_agents.forum.claim_card import ClaimCard
from research_agents.forum.conflict_detector import ConflictDetector
from research_agents.forum.refetch_planner import RefetchPlanner

# Agent 基类
from research_agents.agents import BaseAgent, AgentResult

# 解析器
from research_agents.resolvers.field_resolver_v2 import FieldResolverV2, FieldResult

# 存储
from research_agents.storage.candidate_store import (
    insert_candidate, get_candidates_for_field, select_candidate
)

__all__ = [
    "ForumModerator", "ForumReport", "ForumFinding",
    "ClaimCard", "ConflictDetector", "RefetchPlanner",
    "BaseAgent", "AgentResult",
    "FieldResolverV2", "FieldResult",
    "insert_candidate", "get_candidates_for_field", "select_candidate",
]
