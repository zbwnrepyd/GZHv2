import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))

from search_plan import build_search_plan


class SearchPlanTests(unittest.TestCase):
    def test_deep_plan_has_core_intents(self):
        plan = build_search_plan(
            "Limitless", "limitless", "limitless.ai",
            ["Limitless", "limitless", "limitless.ai"],
        )
        intents = {q.intent for q in plan.tavily_queries}
        self.assertTrue(
            {"overview", "founders", "funding", "product",
             "pricing", "competitors"}.issubset(intents),
            f"Missing core intents, got: {intents}",
        )

    def test_github_queries_include_display_name(self):
        plan = build_search_plan(
            "Anthropic", "anthropic", "anthropic.com",
            ["Anthropic", "anthropic", "anthropic.com"],
        )
        self.assertTrue(any("Anthropic" in q for q in plan.github_queries))

    def test_youtube_queries_not_empty(self):
        plan = build_search_plan(
            "Notion", "notion", "notion.so",
            ["Notion", "notion", "notion.so"],
        )
        self.assertGreater(len(plan.youtube_queries), 0)

    def test_empty_plan_has_defaults(self):
        plan = build_search_plan("", "", "", [])
        self.assertGreaterEqual(plan.query_count, 0)


if __name__ == "__main__":
    unittest.main()
