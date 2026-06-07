import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

from company_identity import (
    build_company_identity, _normalize_host, _display_name,
)


class CompanyIdentityTests(unittest.TestCase):
    def test_normalize_host_strips_www(self):
        self.assertEqual(_normalize_host("https://www.limitless.ai"),
                         "limitless.ai")
        self.assertEqual(_normalize_host("https://limitless.ai"),
                         "limitless.ai")
        self.assertEqual(_normalize_host("limitless.ai"), "limitless.ai")

    def test_display_name_capitalizes_lowercase(self):
        self.assertEqual(_display_name("limitless"), "Limitless")
        self.assertEqual(_display_name("Limitless"), "Limitless")
        self.assertEqual(_display_name(""), "")

    def test_case_variants_share_company_key(self):
        a = build_company_identity("Limitless", "https://www.limitless.ai")
        b = build_company_identity("limitless", "https://limitless.ai")
        self.assertEqual(a.company_key, b.company_key)
        self.assertEqual(a.company_key, "limitless.ai")

    def test_aliases_include_case_and_domain_variants(self):
        identity = build_company_identity("Limitless",
                                          "https://www.limitless.ai")
        aliases = identity.aliases
        self.assertIn("Limitless", aliases)
        self.assertIn("limitless", aliases)
        self.assertIn("limitless.ai", aliases)

    def test_no_url_uses_lower_name_as_key(self):
        identity = build_company_identity("Anthropic", "")
        self.assertEqual(identity.company_key, "anthropic")
        self.assertEqual(identity.display_name, "Anthropic")


if __name__ == "__main__":
    unittest.main()
