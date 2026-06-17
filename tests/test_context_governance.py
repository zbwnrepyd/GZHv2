"""噪音与上下文治理 — 端到端测试

验证：
1. raw_text / raw_content 不进入 LLM prompt
2. L0 token 不超过 18000
3. 噪声 chunk 不进入 packed_context
4. confirmed 字段只引用 packed_context 内 evidence
5. posthoc weak evidence 不得 confirmed
6. 市场字段缺口径不得 confirmed
7. 私有指标不得误 confirmed
"""
import unittest
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "webapp"))
# 模拟导入路径
from research.context.document_cleaner import clean_document_text
from research.context.evidence_ranker import score_chunk
from research.context.token_budget import TokenBudget, estimate_tokens, BUDGET_PRESETS


class TestRawTextNotInLLM(unittest.TestCase):
    """验证 raw_text / raw_content 不进入 LLM prompt"""

    def test_prepare_raw_data_excludes_raw_sources(self):
        """_prepare_raw_data_for_llm 不应包含 raw_sources"""
        from pipeline import _prepare_raw_data_for_llm

        raw_data = {
            "company_key": "anthropic",
            "company_name": "Anthropic",
            "display_name": "Anthropic",
            "website_host": "anthropic.com",
            "company_url": "https://anthropic.com",
            "aliases": [],
            "_source_summary": {"tavily": {"count": 10}},
            "_source_warnings": [],
            "_evidence_pool": [],
            "_packed_context": {
                "chunks": [
                    {"chunk_text": "Anthropic raised $4B...", "chunk_type": "about",
                     "source_type": "press_release", "source_url": "https://example.com",
                     "title": "Anthropic Funding", "token_estimate": 100,
                     "final_score": 0.8}
                ],
                "evidence_spans": [],
                "used_tokens": 150,
                "dropped_count": 5,
            },
        }

        prepared = _prepare_raw_data_for_llm(raw_data)

        # 不应包含 raw_sources
        self.assertNotIn("raw_sources", prepared,
                        "raw_sources should NOT be in L0 input")
        # 不应包含 raw_text
        prepared_str = json.dumps(prepared)
        self.assertNotIn("raw_content", prepared_str.lower(),
                        "raw_content should NOT appear in L0 input")
        # 应包含 packed_context
        self.assertIn("packed_context", prepared,
                     "packed_context should be in L0 input")
        # 应包含 company_identity
        self.assertIn("company_identity", prepared)

    def test_fallback_without_packed_context(self):
        """无 packed_context 时回退到轻量 evidence_summary（不含 raw_text）"""
        from pipeline import _prepare_raw_data_for_llm

        raw_data = {
            "company_key": "anthropic",
            "company_name": "Anthropic",
            "display_name": "Anthropic",
            "website_host": "anthropic.com",
            "company_url": "https://anthropic.com",
            "aliases": [],
            "_source_summary": {},
            "_source_warnings": [],
            "_evidence_pool": [],
            "_packed_context": {},  # 空
        }

        prepared = _prepare_raw_data_for_llm(raw_data)

        # 无 packed_context 时不传 raw_sources
        self.assertNotIn("raw_sources", prepared)
        self.assertNotIn("raw_text", json.dumps(prepared).lower())


class TestL0Budget(unittest.TestCase):
    """验证 L0 token 预算控制"""

    def test_l0_budget_default(self):
        """L0 预算默认 18000"""
        self.assertEqual(BUDGET_PRESETS["l0_standard"], 18000)
        self.assertEqual(BUDGET_PRESETS["l0_deep"], 28000)

    def test_budget_not_exceeded_with_large_input(self):
        """即使在大量输入下也不超预算"""
        budget = TokenBudget(max_tokens=18000)
        # 模拟大量 chunks
        added = 0
        for i in range(500):
            if budget.add(200, f"https://example.com/page{i}"):
                added += 1
        self.assertLessEqual(budget.used_tokens, 18000)
        # 应该丢弃了一些（URL 限制 + token 限制）
        self.assertGreater(budget.chunks_dropped, 0)

    def test_single_field_budget(self):
        """单字段预算不应超过 field_manifest 限制"""
        from research.context.token_budget import get_field_budget

        funding_budget = get_field_budget("funding_info")
        self.assertEqual(funding_budget, 1600)

        market_budget = get_field_budget("tam")
        self.assertEqual(market_budget, 2200)

        default_budget = get_field_budget("some_unknown_field")
        self.assertEqual(default_budget, BUDGET_PRESETS["field_default"])


class TestNoiseChunkExclusion(unittest.TestCase):
    """验证噪声 chunk 不进入 packed_context"""

    def test_noise_chunk_not_passed(self):
        """噪声 chunk 应被排除"""
        company_identity = {
            "display_name": "Anthropic",
            "website_host": "anthropic.com",
            "aliases": [],
        }

        # 噪声 chunk
        noise_chunk = {
            "document_id": 1, "company_key": "anthropic",
            "source_type": "official_site", "source_url": "https://a.com",
            "title": "Footer", "chunk_text": "© 2025 All rights reserved",
            "chunk_type": "footer", "token_estimate": 50, "is_noise": 1,
        }
        result = score_chunk(noise_chunk, company_identity)
        self.assertEqual(result["is_noise"], 1)
        self.assertLess(result["final_score"], 0.35)

    def test_cookie_chunk_excluded(self):
        """Cookie chunk 应被标记为噪音"""
        company_identity = {
            "display_name": "Example",
            "website_host": "example.com",
            "aliases": [],
        }
        chunk = {
            "document_id": 2, "company_key": "example",
            "source_type": "official_site", "source_url": "https://example.com/cookies",
            "title": "Cookie Policy",
            "chunk_text": "Cookie Policy We use cookies to improve your experience. "
                         "By continuing you agree to our use of cookies.",
            "chunk_type": "cookie", "token_estimate": 100, "is_noise": 1,
        }
        result = score_chunk(chunk, company_identity)
        self.assertEqual(result["is_noise"], 1)
        self.assertAlmostEqual(result["noise_score"], 1.0)


class TestConfirmedEvidenceRequirement(unittest.TestCase):
    """验证 confirmed 字段证据要求"""

    def test_official_fact_no_evidence_not_confirmed(self):
        """无证据的 official_fact 不得 confirmed"""
        from research.field_resolver import resolve_field
        from research.field_resolver import FieldResult

        entry = {
            "category": "A",
            "resolution_type": "official_fact",
            "if_missing": "unavailable",
        }
        result = resolve_field(
            "funding_info", "Raised $10M",
            {}, entry,
            evidence_span_ids=[],  # 无证据
        )
        self.assertNotEqual(result.resolution_status, "confirmed",
                           "Should NOT be confirmed without evidence")
        self.assertEqual(result.resolution_status, "llm_extracted")

    def test_official_fact_with_evidence_confirmed(self):
        """有证据的 official_fact 可 confirmed"""
        from research.field_resolver import resolve_field

        entry = {
            "category": "A",
            "resolution_type": "official_fact",
            "if_missing": "unavailable",
        }
        result = resolve_field(
            "funding_info", "Raised $10M",
            {}, entry,
            evidence_span_ids=[1, 2],  # 有证据
        )
        self.assertEqual(result.resolution_status, "confirmed")

    def test_private_metric_no_evidence_not_confirmed(self):
        """无证据的私有指标不得 confirmed"""
        from research.field_resolver import resolve_field

        entry = {
            "category": "D",
            "resolution_type": "private_metric",
            "if_missing": "unavailable",
        }
        result = resolve_field(
            "cac", "$500",
            {}, entry,
            evidence_span_ids=[],  # 无证据
        )
        self.assertNotEqual(result.resolution_status, "confirmed",
                           "Private metric should NOT be confirmed without evidence")


class TestMarketFieldValidation(unittest.TestCase):
    """市场字段需要 region/segment/year/source"""

    def test_market_field_without_context_not_confirmed(self):
        """缺 region/segment/year 的市场字段不得 confirmed"""
        from research.field_resolver import resolve_field

        entry = {
            "category": "C",
            "resolution_type": "market_model",
            "allow_proxy": True,
            "required_context": ["region", "segment", "year", "source"],
        }
        result = resolve_field(
            "tam", "$10B",
            {}, entry,
            evidence_span_ids=[],
        )
        # 市场字段始终 proxy，缺 context 会更严格
        self.assertIn(result.resolution_status, ("proxy", "manual_needed"))
        self.assertNotEqual(result.resolution_status, "confirmed")

    def test_market_field_with_missing_context_is_manual_needed(self):
        """缺关键上下文时标 manual_needed"""
        from research.field_resolver import _resolve_market_model

        entry = {
            "category": "C",
            "resolution_type": "market_model",
            "allow_proxy": True,
            "required_context": ["region", "segment", "year", "source"],
        }
        result = _resolve_market_model("market_size_value", entry)
        # allow_proxy=True 但有 required_context 缺失 → manual_needed
        self.assertEqual(result.resolution_status, "manual_needed")


class TestPosthocWeakEvidence(unittest.TestCase):
    """posthoc weak evidence 不得 confirmed"""

    def test_posthoc_evidence_not_in_evidence_map(self):
        """posthoc_weak_matcher 创建的证据不应出现在 evidence_map 中"""
        from research.evidence_extractor import build_evidence_map
        import sqlite3
        import tempfile

        db_path = tempfile.mktemp(suffix=".sqlite")
        conn = sqlite3.connect(db_path)
        conn.execute("""CREATE TABLE evidence_spans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER, company_key TEXT, field_key TEXT,
            quote_text TEXT, normalized_fact TEXT,
            start_offset INTEGER, end_offset INTEGER,
            confidence REAL, created_by_agent TEXT
        )""")
        # 插入 posthoc 弱证据
        conn.execute(
            "INSERT INTO evidence_spans (document_id, company_key, field_key, "
            "quote_text, confidence, created_by_agent) VALUES (1, 'test', "
            "'funding_info', 'raised $10M', 0.4, 'posthoc_weak_matcher')"
        )
        # 插入正常证据
        conn.execute(
            "INSERT INTO evidence_spans (document_id, company_key, field_key, "
            "quote_text, confidence, created_by_agent) VALUES (1, 'test', "
            "'funding_info', 'raised $10M in Series A', 0.8, 'chunk_pre_extractor')"
        )
        conn.commit()

        evidence_map = build_evidence_map(db_path, "test", ["funding_info"])
        conn.close()

        # posthoc_weak 证据不应出现在 map 中
        span_ids = evidence_map.get("funding_info", [])
        # 应只有 1 条（正常证据），posthoc 被排除
        self.assertEqual(len(span_ids), 1,
                        "posthoc_weak_matcher evidence should NOT appear in evidence_map")

        import os
        os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
