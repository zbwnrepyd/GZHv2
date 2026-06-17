"""FieldResolver v2 — 按字段类型分派到专用解析器。

P1: 替代旧 field_resolver.py 的单一函数模式。
按 official_fact、market_model、private_metric、derived、analysis、b2b_remap
分派到对应解析器，统一返回 FieldResult。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# 复用 v1 的 FieldResult（保持兼容）
@dataclass
class FieldResult:
    field_key: str
    value: Optional[str] = None
    resolution_status: str = "unavailable"
    confidence: str = "medium"
    source_fields: list[str] = field(default_factory=list)
    formula: str = ""
    assumptions: list[str] = field(default_factory=list)
    unavailable_reason: str = ""
    resolution_method: str = ""
    evidence_span_ids: list = field(default_factory=list)
    region: str = ""
    segment: str = ""
    year: str = ""
    source_note: str = ""
    disclaimer: str = ""


class FieldResolverV2:
    """字段解析器 V2 — 多策略路由。

    使用方式:
        resolver = FieldResolverV2(manifest, evidence_map, is_b2b=False)
        result = resolver.resolve(field_key, value)
    """

    def __init__(self, manifest: dict,
                 evidence_map: dict[str, list] | None = None,
                 is_b2b: bool = False):
        self.manifest = manifest
        self.evidence_map = evidence_map or {}
        self.is_b2b = is_b2b
        self._resolved: dict[str, FieldResult] = {}

    def resolve(self, field_key: str, value: str | None) -> FieldResult:
        entry = self.manifest.get(field_key, self.manifest.get("_default", {}))
        resolution_type = entry.get("resolution_type", "llm_extract")
        has_evidence = bool(self.evidence_map.get(field_key))

        if resolution_type == "official_fact":
            return self._resolve_official_fact(field_key, value, entry, has_evidence)
        elif resolution_type == "market_model":
            return self._resolve_market_model(field_key, value, entry, has_evidence)
        elif resolution_type == "private_metric":
            return self._resolve_private_metric(field_key, value, entry, has_evidence)
        elif resolution_type == "derived":
            return self._resolve_derived(field_key, value, entry)
        elif resolution_type == "b2b_remap":
            return self._resolve_b2b_remap(field_key, value, entry, has_evidence)
        elif resolution_type == "analysis":
            return self._resolve_analysis(field_key, value, entry, has_evidence)
        else:
            return self._resolve_llm_extract(field_key, value, entry, has_evidence)

    # ── 各策略实现 ──

    def _resolve_official_fact(self, field_key: str, value: str | None,
                               entry: dict, has_evidence: bool) -> FieldResult:
        if _is_missing(value):
            return FieldResult(field_key=field_key, resolution_status="unavailable",
                             resolution_method="official_fact_missing",
                             unavailable_reason=f"{field_key}: 公开信息未找到")
        if has_evidence:
            return FieldResult(field_key=field_key, value=str(value),
                             resolution_status="confirmed", confidence="high",
                             resolution_method="official_fact",
                             evidence_span_ids=self.evidence_map.get(field_key, []))
        return FieldResult(field_key=field_key, value=str(value),
                         resolution_status="llm_extracted", confidence="low",
                         resolution_method="official_fact_no_evidence",
                         unavailable_reason=f"{field_key}: LLM提取但未绑定证据")

    def _resolve_market_model(self, field_key: str, value: str | None,
                              entry: dict, has_evidence: bool) -> FieldResult:
        if _is_missing(value):
            return FieldResult(field_key=field_key,
                             resolution_status="manual_needed",
                             resolution_method="market_model_missing",
                             unavailable_reason=f"{field_key}: 市场估算需要报告支撑")
        required = entry.get("required_context", [])
        missing_ctx = [c for c in required if c not in entry]
        status = "proxy"
        reason = ""
        if missing_ctx:
            status = "manual_needed"
            reason = f"缺少口径参数: {', '.join(missing_ctx)}"
        return FieldResult(field_key=field_key, value=str(value),
                         resolution_status=status,
                         resolution_method="market_model",
                         evidence_span_ids=self.evidence_map.get(field_key, []),
                         unavailable_reason=reason)

    def _resolve_private_metric(self, field_key: str, value: str | None,
                                entry: dict, has_evidence: bool) -> FieldResult:
        if _is_missing(value):
            # 四级降级：-> industry_avg -> unavailable
            from research.field_status import _LTV_CAC_INDUSTRY_BENCHMARKS
            if field_key in _LTV_CAC_INDUSTRY_BENCHMARKS:
                return FieldResult(
                    field_key=field_key,
                    value=_LTV_CAC_INDUSTRY_BENCHMARKS[field_key],
                    resolution_status="industry_avg",
                    resolution_method="industry_avg_fallback",
                    disclaimer="行业平均，不代表公司披露",
                )
            return FieldResult(field_key=field_key,
                             resolution_status="unavailable",
                             resolution_method="private_metric_unavailable",
                             unavailable_reason=f"{field_key}: 私有经营指标，公开未披露")
        if has_evidence:
            return FieldResult(field_key=field_key, value=str(value),
                             resolution_status="confirmed",
                             resolution_method="private_metric_confirmed",
                             evidence_span_ids=self.evidence_map.get(field_key, []))
        return FieldResult(field_key=field_key, value=str(value),
                         resolution_status="llm_extracted",
                         resolution_method="private_metric_no_evidence",
                         unavailable_reason=f"{field_key}: LLM提取，无公开来源证据")

    def _resolve_derived(self, field_key: str, value: str | None,
                         entry: dict) -> FieldResult:
        required = entry.get("required_inputs", [])
        formula = entry.get("formula", "")
        for inp in required:
            if inp not in self._resolved or self._resolved[inp].value is None:
                return FieldResult(field_key=field_key,
                                 resolution_status="unavailable",
                                 resolution_method="blocked_formula",
                                 formula=formula,
                                 unavailable_reason=f"依赖 {inp} 缺失")
        return FieldResult(field_key=field_key, value=str(value) if value else None,
                         resolution_status="derived",
                         resolution_method="formula",
                         formula=formula,
                         source_fields=required)

    def _resolve_b2b_remap(self, field_key: str, value: str | None,
                           entry: dict, has_evidence: bool) -> FieldResult:
        if self.is_b2b:
            return FieldResult(field_key=field_key,
                             resolution_status="not_applicable",
                             resolution_method="b2b_remap",
                             unavailable_reason=f"B2B 不适配，建议使用 {entry.get('b2b_replace', 'account数')}")
        if _is_missing(value):
            return FieldResult(field_key=field_key, resolution_status="unavailable",
                             resolution_method="b2b_remap_missing")
        return FieldResult(field_key=field_key, value=str(value),
                         resolution_status="confirmed" if has_evidence else "llm_extracted",
                         resolution_method="b2b_remap")

    def _resolve_analysis(self, field_key: str, value: str | None,
                          entry: dict, has_evidence: bool) -> FieldResult:
        if _is_missing(value):
            return FieldResult(field_key=field_key,
                             resolution_status="unavailable",
                             resolution_method="analysis_missing")
        return FieldResult(field_key=field_key, value=str(value),
                         resolution_status="llm_extracted",
                         resolution_method="analysis",
                         evidence_span_ids=self.evidence_map.get(field_key, []))

    def _resolve_llm_extract(self, field_key: str, value: str | None,
                             entry: dict, has_evidence: bool) -> FieldResult:
        if _is_missing(value):
            return FieldResult(field_key=field_key,
                             resolution_status="unavailable",
                             resolution_method="llm_extract_missing")
        return FieldResult(field_key=field_key, value=str(value),
                         resolution_status="llm_extracted",
                         resolution_method="llm_extract")


_MISSING = {"", "暂缺", "unknown", "Unknown", "N/A", "n/a", "none", "None", "NULL"}


def _is_missing(value) -> bool:
    if value is None:
        return True
    return str(value).strip() in _MISSING
