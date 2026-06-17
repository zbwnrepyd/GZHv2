"""RefetchPlanner — 补采任务规划

P2 最小实现：根据 ForumModerator 输出和 field_manifest，生成定向补采任务。
只对 A/B/C 类字段生成补采，D/E 类不补采。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RefetchTask:
    field_key: str
    priority: str  # high|medium|low
    reason: str
    suggested_queries: list[str] = field(default_factory=list)


class RefetchPlanner:
    """补采规划器 — 根据缺口和字段类别生成定向补采任务。"""

    def __init__(self, manifest: dict | None = None):
        self.manifest = manifest or {}

    def plan(self, weak_evidence_fields: list[str],
             manual_needed_fields: list[str] = None) -> list[RefetchTask]:
        """生成补采计划。

        Args:
            weak_evidence_fields: evidence 不足的字段
            manual_needed_fields: 需要人工确认的字段

        Returns:
            按优先级排序的补采任务列表
        """
        manual_needed_fields = manual_needed_fields or []
        tasks = []

        for fk in weak_evidence_fields:
            entry = self.manifest.get(fk, {})
            category = entry.get("category", "A")
            if category not in ("A", "B", "C"):
                continue  # D/E 不补采
            tasks.append(RefetchTask(
                field_key=fk,
                priority="high" if category == "A" else "medium",
                reason=f"{fk}: 证据不足，类别 {category}，建议定向补采",
            ))

        # manual_needed 字段不补采（需人工）
        # 只记录，不生成任务
        return sorted(tasks, key=lambda t: {"high": 0, "medium": 1, "low": 2}.get(t.priority, 2))
