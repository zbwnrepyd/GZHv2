"""ConflictDetector — 字段候选值冲突检测

P2 最小实现：检测同一字段的多个候选值是否冲突。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ConflictResult:
    field_key: str
    is_conflict: bool
    candidates: list[dict] = field(default_factory=list)
    conflict_type: str = ""  # value_mismatch|source_disagreement|timing_mismatch
    recommendation: str = ""


class ConflictDetector:
    """冲突检测器 — 判断同一字段的多个候选值是否冲突。"""

    def detect(self, field_key: str,
               candidates: list[dict]) -> ConflictResult:
        """检测候选值冲突。

        Args:
            field_key: 字段名
            candidates: [{"candidate_value": str, "agent_name": str, "confidence": float}, ...]

        Returns:
            ConflictResult
        """
        if len(candidates) <= 1:
            return ConflictResult(
                field_key=field_key,
                is_conflict=False,
                candidates=candidates,
            )

        values = [c.get("candidate_value", "") for c in candidates]
        unique_values = set(v.strip() for v in values if v.strip())

        if len(unique_values) <= 1:
            return ConflictResult(
                field_key=field_key,
                is_conflict=False,
                candidates=candidates,
            )

        # 简单冲突检测：不同 Agent 给出不同值
        return ConflictResult(
            field_key=field_key,
            is_conflict=True,
            candidates=candidates,
            conflict_type="value_mismatch",
            recommendation=f"{field_key}: {len(unique_values)} 个不同候选值，需人工仲裁",
        )
