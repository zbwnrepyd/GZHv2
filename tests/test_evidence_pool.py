import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

from evidence_pool import (
    normalize_url, source_score, dedupe_evidence, EvidenceItem,
)


class EvidencePoolTests(unittest.TestCase):
    def test_normalize_url_strips_utm(self):
        result = normalize_url(
            "https://www.limitless.ai/?utm_source=x&a=1")
        self.assertEqual(result, "https://limitless.ai?a=1")

    def test_normalize_url_removes_trailing_slash(self):
        result = normalize_url("https://limitless.ai/about/")
        self.assertEqual(result, "https://limitless.ai/about")

    def test_normalize_url_empty_returns_empty(self):
        self.assertEqual(normalize_url(""), "")

    def test_dedupe_keeps_highest_score(self):
        a = EvidenceItem(url="https://a.com", normalized_url="https://a.com",
                         final_score=0.8, intent="funding")
        b = EvidenceItem(url="https://a.com", normalized_url="https://a.com",
                         final_score=0.5, intent="founders")
        result = dedupe_evidence([a, b])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].final_score, 0.8)
        self.assertIn("founders", result[0].intent)
        self.assertIn("funding", result[0].intent)

    def test_source_score_website_max(self):
        s = source_score("https://limitless.ai", "website")
        self.assertEqual(s, 1.0)

    def test_source_score_techcrunch(self):
        s = source_score("https://techcrunch.com/article", "tavily")
        self.assertEqual(s, 0.75)


if __name__ == "__main__":
    unittest.main()
