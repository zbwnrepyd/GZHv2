"""ForumModerator — 字段校验与冲突检测。

P2 最小实现：
- 检查 confirmed 字段是否有 evidence
- 检查市场字段是否有口径
- 检查候选值冲突
- 检查私有指标是否被误标为 confirmed
- 输出 weak_evidence_fields、conflict_fields、manual_needed_fields、refetch_tasks
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ForumFinding:
    """论坛检查发现的问题"""
    field_key: str
    issue_type: str  # weak_evidence|conflict|no_context|private_confirmed|missing_evidence
    severity: str  # error|warning|info
    detail: str
    suggestion: str = ""


@dataclass
class ForumReport:
    """论坛检查报告"""
    weak_evidence_fields: list[str] = field(default_factory=list)
    conflict_fields: list[str] = field(default_factory=list)
    manual_needed_fields: list[str] = field(default_factory=list)
    refetch_tasks: list[dict] = field(default_factory=list)
    findings: list[ForumFinding] = field(default_factory=list)
    passed: bool = True


# 私有指标字段列表（不应标记为 confirmed 除非有直接证据）
_PRIVATE_METRIC_FIELDS = {
    "cac", "ltv", "churn_rate", "retention_rate",
    "gross_margin", "burn_rate", "runway_months",
    "arr", "mrr", "revenue_metrics", "growth_metrics",
}

# 市场字段（需要口径）
_MARKET_FIELDS = {
    "market_size_value", "market_cagr", "tam", "tam_value",
    "sam", "som", "market_size_source_note",
}


class ForumModerator:
    """论坛主持人 — 字段级质量检查。

    输入字段解析结果，输出问题清单和补采任务。
    不做复杂辩论，只做四类检查：
    1. confirmed 无证据 → weak_evidence
    2. 市场字段无口径 → no_context
    3. 多候选值冲突 → conflict
    4. 私有指标误 confirmed → private_confirmed
    """

    def __init__(self, manifest: dict | None = None):
        self.manifest = manifest or {}
        self.findings: list[ForumFinding] = []

    def check_field(self, field_key: str, status: str,
                    evidence_ids: list | None = None,
                    candidate_count: int = 1,
                    has_context: bool = False) -> None:
        """检查单个字段的各项质量指标。"""
        ev_count = len(evidence_ids or [])

        # 1. confirmed 无证据
        if status == "confirmed" and ev_count == 0:
            self.findings.append(ForumFinding(
                field_key=field_key,
                issue_type="weak_evidence",
                severity="error",
                detail=f"{field_key}: 标记为 confirmed 但未绑定任何 evidence_span",
                suggestion="添加至少一条证据源，或降级为 llm_extracted",
            ))

        # 2. 市场字段无口径
        if field_key in _MARKET_FIELDS and not has_context:
            if status not in ("manual_needed", "unavailable", "not_applicable"):
                self.findings.append(ForumFinding(
                    field_key=field_key,
                    issue_type="no_context",
                    severity="warning",
                    detail=f"{field_key}: 市场字段缺少 region/segment/year/source 口径",
                    suggestion="补充市场边界参数，或标记为 manual_needed/proxy",
                ))

        # 3. 多候选值冲突
        if candidate_count > 1:
            self.findings.append(ForumFinding(
                field_key=field_key,
                issue_type="conflict",
                severity="info",
                detail=f"{field_key}: 存在 {candidate_count} 个候选值，可能存在冲突",
                suggestion="需要 ForumModerator 仲裁或人工选择",
            ))

        # 4. 私有指标误 confirmed
        if field_key in _PRIVATE_METRIC_FIELDS and status == "confirmed":
            self.findings.append(ForumFinding(
                field_key=field_key,
                issue_type="private_confirmed",
                severity="error",
                detail=f"{field_key}: 私有经营指标不应标记为 confirmed，公开互联网无法确认",
                suggestion="降级为 unavailable、proxy 或 industry_avg",
            ))

    def audit_batch(self, fields: dict[str, dict]) -> ForumReport:
        """批量审计一组字段。

        Args:
            fields: {field_key: {status, evidence_ids, candidate_count, has_context}}

        Returns:
            ForumReport 综合报告
        """
        self.findings = []
        for fk, meta in fields.items():
            self.check_field(
                field_key=fk,
                status=meta.get("status", "draft"),
                evidence_ids=meta.get("evidence_ids"),
                candidate_count=meta.get("candidate_count", 1),
                has_context=meta.get("has_context", False),
            )

        report = ForumReport()
        for f in self.findings:
            report.findings.append(f)
            if f.issue_type == "weak_evidence":
                report.weak_evidence_fields.append(f.field_key)
            elif f.issue_type == "conflict":
                report.conflict_fields.append(f.field_key)
            elif f.issue_type == "private_confirmed":
                # 私有指标误 confirmed → 需要人工确认
                report.manual_needed_fields.append(f.field_key)
            elif f.issue_type == "no_context":
                report.manual_needed_fields.append(f.field_key)

        # A/B/C 类的 weak_evidence 字段 → 可补采
        for f in self.findings:
            if f.issue_type == "weak_evidence":
                category = self.manifest.get(f.field_key, {}).get("category", "A")
                if category in ("A", "B", "C"):
                    report.refetch_tasks.append({
                        "field_key": f.field_key,
                        "reason": f.detail,
                        "priority": "high" if category == "A" else "medium",
                    })

        report.passed = len([f for f in self.findings if f.severity == "error"]) == 0
        return report
