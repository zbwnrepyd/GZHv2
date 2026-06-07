"""验证大小写变体共享 company_key。"""
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

from company_identity import build_company_identity


class PipelineCaseInsensitiveTests(unittest.TestCase):
    def test_limitless_case_variants_share_company_key(self):
        a = build_company_identity("Limitless", "https://www.limitless.ai")
        b = build_company_identity("limitless", "https://limitless.ai")
        self.assertEqual(a.company_key, b.company_key)
        self.assertEqual(a.company_key, "limitless.ai")
        self.assertEqual(a.display_name, "Limitless")

    def test_anthropic_case_variants(self):
        a = build_company_identity("Anthropic", "https://www.anthropic.com")
        b = build_company_identity("anthropic", "https://anthropic.com")
        self.assertEqual(a.company_key, b.company_key)

    def test_no_url_uses_lower_name(self):
        identity = build_company_identity("DeepSeek", "")
        self.assertEqual(identity.company_key, "deepseek")
        self.assertEqual(identity.display_name, "DeepSeek")

    def test_www_stripped_from_host(self):
        identity = build_company_identity("Test", "https://www.example.com")
        self.assertEqual(identity.website_host, "example.com")


if __name__ == "__main__":
    unittest.main()
