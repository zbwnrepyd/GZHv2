"""ClaimCard — 字段声明卡，记录一个字段的完整证据链。

P2 最小实现：存储字段声明及其证据绑定状态。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ClaimCard:
    """字段声明卡"""
    field_key: str
    claim_value: str
    evidence_span_ids: list[int] = field(default_factory=list)
    source_tier: str = ""
    confidence: float = 0.0
    agent_name: str = ""
    risk_flags: list[str] = field(default_factory=list)

    @property
    def has_evidence(self) -> bool:
        return len(self.evidence_span_ids) > 0

    @property
    def is_weak(self) -> bool:
        return not self.has_evidence or self.confidence < 0.5

    def to_dict(self) -> dict:
        return {
            "field_key": self.field_key,
            "claim_value": self.claim_value,
            "evidence_span_ids": self.evidence_span_ids,
            "source_tier": self.source_tier,
            "confidence": self.confidence,
            "agent_name": self.agent_name,
            "risk_flags": self.risk_flags,
            "has_evidence": self.has_evidence,
            "is_weak": self.is_weak,
        }
