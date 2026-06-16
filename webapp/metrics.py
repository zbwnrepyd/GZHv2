"""Explicit metric formulas for v3 operating fields."""
from __future__ import annotations


def calculate_cagr(begin_value: float, end_value: float, years: float) -> float:
    if begin_value <= 0 or end_value <= 0 or years <= 0:
        raise ValueError("begin_value, end_value and years must be positive")
    return ((end_value / begin_value) ** (1 / years) - 1) * 100


def calculate_ltv(arpu: float, gross_margin: float | None = None, churn_rate: float | None = None) -> float:
    if gross_margin is None or churn_rate is None:
        return float(arpu)
    if churn_rate <= 0:
        raise ValueError("churn_rate must be positive")
    return float(arpu) * float(gross_margin) / float(churn_rate)


def calculate_ltv_cac(ltv: float, cac: float) -> float:
    if cac <= 0:
        raise ValueError("cac must be positive")
    return float(ltv) / float(cac)


def ltv_cac_benchmark(stage: str, source: str = "") -> dict:
    ratio_by_stage = {
        "b2b_saas_seed": 3.0,
        "b2b_saas_series_a": 3.0,
        "consumer_ai": 2.0,
    }
    ratio = ratio_by_stage.get(stage, 3.0)
    return {
        "ltv_cac_ratio": ratio,
        "ltv_cac_is_benchmark": 1,
        "ltv_cac_benchmark_source": source or stage,
        "note": "行业平均/阶段平均，非公司披露值",
    }
