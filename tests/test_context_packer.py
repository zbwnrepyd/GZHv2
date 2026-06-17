"""测试上下文打包器 — 验证 token 预算控制"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "webapp"))
from research.context.token_budget import TokenBudget, estimate_tokens, BUDGET_PRESETS


class TestTokenBudget(unittest.TestCase):

    def test_budget_not_exceeded(self):
        """预算不应被超过"""
        budget = TokenBudget(max_tokens=1000)
        self.assertTrue(budget.add(500))
        self.assertTrue(budget.add(400))
        self.assertFalse(budget.add(200))  # 超预算
        self.assertEqual(budget.used_tokens, 900)
        self.assertEqual(budget.chunks_dropped, 1)

    def test_url_dedup(self):
        """同一 URL 最多 3 个 chunk"""
        budget = TokenBudget(max_tokens=10000)
        url = "https://example.com/article"
        self.assertTrue(budget.add(100, url))
        self.assertTrue(budget.add(100, url))
        self.assertTrue(budget.add(100, url))
        self.assertFalse(budget.add(100, url))  # 第 4 个同名 URL 应被拒绝
        self.assertEqual(budget.chunks_dropped, 1)

    def test_different_urls_ok(self):
        """不同 URL 不受限制"""
        budget = TokenBudget(max_tokens=10000)
        self.assertTrue(budget.add(100, "https://a.com"))
        self.assertTrue(budget.add(100, "https://b.com"))
        self.assertTrue(budget.add(100, "https://c.com"))
        self.assertTrue(budget.add(100, "https://d.com"))
        self.assertEqual(budget.chunks_dropped, 0)

    def test_summary_accurate(self):
        """摘要应准确反映状态"""
        budget = TokenBudget(max_tokens=500)
        budget.add(200)
        budget.add(150)
        s = budget.summary()
        self.assertEqual(s["budget"], 500)
        self.assertEqual(s["used"], 350)
        self.assertEqual(s["remaining"], 150)
        self.assertEqual(s["chunks_included"], 2)

    def test_budget_presets_valid(self):
        """预算预设应在合理范围内"""
        self.assertLessEqual(BUDGET_PRESETS["l0_standard"], 20000)
        self.assertLessEqual(BUDGET_PRESETS["l0_deep"], 30000)
        self.assertEqual(BUDGET_PRESETS["max_chunks_per_url"], 3)


class TestTokenEstimation(unittest.TestCase):

    def test_empty_text(self):
        self.assertEqual(estimate_tokens(""), 0)
        self.assertEqual(estimate_tokens(None), 0)

    def test_chinese_text(self):
        """中文文本 token 估算"""
        text = "这是一段中文文本用于测试"
        tokens = estimate_tokens(text)
        self.assertGreater(tokens, 0)
        self.assertLess(tokens, len(text))  # token 数应小于字符数

    def test_english_text(self):
        """英文文本 token 估算"""
        text = "This is a sample English text for token estimation testing purposes"
        tokens = estimate_tokens(text)
        self.assertGreater(tokens, 0)
        self.assertLess(tokens, len(text))

    def test_mixed_text(self):
        """中英混合文本"""
        text = "Anthropic 是一家 AI 安全公司，总部位于 San Francisco。"
        tokens = estimate_tokens(text)
        self.assertGreater(tokens, 0)

    def test_large_text(self):
        """长文本 token 估算不超过合理范围"""
        text = "content " * 10000
        tokens = estimate_tokens(text)
        chars_per_token = len(text) / tokens
        # 应该在 2-3 字符/token 之间
        self.assertGreater(chars_per_token, 1.5)
        self.assertLess(chars_per_token, 4.0)


if __name__ == "__main__":
    unittest.main()
