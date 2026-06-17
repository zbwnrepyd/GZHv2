"""Token 预算控制器 — 管理各层级 LLM 调用的输入 token 上限。

预算预设：
- L0: 标准 18000 / 深度 28000
- L1: 标准 8000
- L2: 标准 10000
- L3: 标准 12000
- 单事实字段: 800–1200
- 融资/创始人/客户字段: 1600
- 市场规模/TAM: 2200
- 竞品/生态位/GTM: 3000
"""
from __future__ import annotations
import re
from typing import Optional

# ── Token 估算常量 ──
# 中英文混合保守估计：~2.5 字符/token
CHARS_PER_TOKEN = 2.5

# ── 预算预设 ──
BUDGET_PRESETS = {
    # 层级预算
    "l0_standard": 18000,
    "l0_deep": 28000,
    "l1_standard": 8000,
    "l2_standard": 10000,
    "l3_standard": 12000,
    # 字段级预算
    "field_default": 1200,
    "field_fact": 800,
    "field_funding": 1600,
    "field_founder": 1600,
    "field_customer": 1600,
    "field_market": 2200,
    "field_competitive": 3000,
    "field_ecosystem": 3000,
    "field_gtm": 3000,
    "field_analysis": 2500,
    # 卡片级预算
    "card_default": 4000,
    # 限制
    "max_chunks_per_field": 5,
    "max_chunks_per_url": 3,
    "max_evidence_per_field": 8,
}

# ── 字段到预算的映射 ──
_FIELD_BUDGET_MAP: dict[str, str] = {
    # 高预算字段
    "funding_info": "field_funding",
    "funding_rounds": "field_funding",
    "founder_name": "field_founder",
    "founder_bg": "field_founder",
    "founder_edu": "field_founder",
    "founder_achievement": "field_founder",
    "ideal_customer_profile": "field_customer",
    "customer_names": "field_customer",
    "customer_selection_reasons": "field_customer",
    "tam": "field_market",
    "market_size_value": "field_market",
    "market_cagr": "field_market",
    "competitors_top3": "field_competitive",
    "competitive_position": "field_competitive",
    "competitive_advantages": "field_competitive",
    "ecosystem_niche": "field_ecosystem",
    "growth_strategy": "field_gtm",
    "gtm_motion": "field_gtm",
    "growth_flywheel": "field_gtm",
    "competitive_landscape": "field_analysis",
    "company_analysis": "field_analysis",
}


def estimate_tokens(text: str) -> int:
    """保守估算文本 token 数（中英文混合，~2.5 字符/token）。"""
    if not text:
        return 0
    return max(1, int(len(text) / CHARS_PER_TOKEN))


def get_field_budget(field_key: str, manifest_entry: dict | None = None) -> int:
    """获取字段上下文预算。

    优先级: field_manifest > _FIELD_BUDGET_MAP > 默认
    """
    # field_manifest 中的显式配置
    if manifest_entry and manifest_entry.get("context_budget_tokens"):
        return int(manifest_entry["context_budget_tokens"])

    # 映射表
    budget_key = _FIELD_BUDGET_MAP.get(field_key)
    if budget_key:
        return BUDGET_PRESETS[budget_key]

    # 默认
    return BUDGET_PRESETS["field_default"]


def get_field_max_chunks(field_key: str, manifest_entry: dict | None = None) -> int:
    """获取字段最大 chunk 数。"""
    if manifest_entry and manifest_entry.get("max_evidence_chunks"):
        return int(manifest_entry["max_evidence_chunks"])
    return BUDGET_PRESETS["max_chunks_per_field"]


class TokenBudget:
    """Token 预算追踪器 — 追踪单次 LLM 调用的输入 token 使用量。"""

    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.used_tokens = 0
        self.chunks_included = 0
        self.chunks_dropped = 0
        self._url_chunk_counts: dict[str, int] = {}

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.used_tokens)

    @property
    def is_full(self) -> bool:
        return self.used_tokens >= self.max_tokens

    def can_add(self, chunk_tokens: int) -> bool:
        return self.used_tokens + chunk_tokens <= self.max_tokens

    def add(self, chunk_tokens: int, source_url: str = "") -> bool:
        """尝试添加一个 chunk 的 token 数。返回是否成功。"""
        if not self.can_add(chunk_tokens):
            self.chunks_dropped += 1
            return False

        # URL 去重检查
        if source_url:
            url_count = self._url_chunk_counts.get(source_url, 0)
            if url_count >= BUDGET_PRESETS["max_chunks_per_url"]:
                self.chunks_dropped += 1
                return False
            self._url_chunk_counts[source_url] = url_count + 1

        self.used_tokens += chunk_tokens
        self.chunks_included += 1
        return True

    def add_chunk(self, chunk: dict) -> bool:
        """尝试添加一个 chunk。返回是否成功。"""
        tokens = chunk.get("token_estimate", 0)
        url = chunk.get("source_url", "")
        return self.add(tokens, url)

    def summary(self) -> dict:
        return {
            "budget": self.max_tokens,
            "used": self.used_tokens,
            "remaining": self.remaining,
            "chunks_included": self.chunks_included,
            "chunks_dropped": self.chunks_dropped,
        }
