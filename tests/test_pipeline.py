import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import pipeline


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"{self.status_code} Error")

    def json(self):
        return self._payload


class PipelineFailureTests(unittest.TestCase):
    def test_extract_json_accepts_uppercase_fence_and_prose(self):
        text = """这里是结果：

```JSON
{"company_type": "AI工具", "data_confidence": "中"}
```

以上。"""

        parsed = pipeline._extract_json(text)

        self.assertEqual(parsed["company_type"], "AI工具")
        self.assertEqual(parsed["data_confidence"], "中")

    def test_extract_json_accepts_prose_wrapped_object(self):
        text = '结果如下：{"company_type": "AI搜索", "data_confidence": "高"} 请查收。'

        parsed = pipeline._extract_json(text)

        self.assertEqual(parsed["company_type"], "AI搜索")
        self.assertEqual(parsed["data_confidence"], "高")

    def test_l3_error_fails_before_writing_database(self):
        bad_records = [{"company_name": "BadCo", "version": "standard", "_error": "bad json"}]
        with patch.object(pipeline, "_collect_all", return_value={}), \
             patch.object(pipeline, "llm_analysis", return_value=bad_records), \
             patch.object(pipeline.database, "save_research_records") as save_records:
            with self.assertRaises(RuntimeError):
                pipeline.run_pipeline("BadCo", "https://bad.example")

        save_records.assert_not_called()

    def test_collection_source_summary_counts_success_and_failures(self):
        tavily = pipeline._summarize_collection_source(
            "tavily",
            [
                {"results": [{"title": "A"}, {"title": "B"}]},
                {"error": "quota", "results": []},
            ],
        )
        github = pipeline._summarize_collection_source(
            "github", {"items": [{"name": "repo"}]}
        )
        youtube = pipeline._summarize_collection_source(
            "youtube", {"items": [], "note": "no API key"}
        )
        website = pipeline._summarize_collection_source(
            "website", {"text": "hello world"}
        )

        self.assertEqual(tavily["status"], "ok")
        self.assertEqual(tavily["count"], 2)
        self.assertIn("quota", tavily["detail"])
        self.assertEqual(github["count"], 1)
        self.assertEqual(youtube["status"], "skipped")
        self.assertEqual(website["count"], 11)

    def test_collect_all_reports_structured_source_details(self):
        events = []

        def on_progress(stage, detail):
            events.append((stage, detail))

        with patch.object(pipeline, "_search_tavily", return_value=[{"results": [{"title": "A"}]}]), \
             patch.object(pipeline, "_search_github", return_value={"items": [{"name": "repo"}]}), \
             patch.object(pipeline, "_search_youtube", return_value={"items": [], "note": "no API key"}), \
             patch.object(pipeline, "_scrape_website", return_value={"text": "homepage"}):
            raw = pipeline._collect_all("DemoCo", "https://demo.example", on_progress)

        self.assertIn("_source_summary", raw)
        self.assertEqual(raw["_source_summary"]["tavily"]["count"], 1)
        self.assertEqual(raw["_source_summary"]["github"]["count"], 1)
        self.assertEqual(raw["_source_summary"]["youtube"]["status"], "skipped")
        self.assertTrue(any(isinstance(detail, dict) and "sources" in detail for _, detail in events))

    def test_tavily_search_tries_next_key_after_quota_limit(self):
        calls = []

        def fake_post(url, json, timeout):
            calls.append(json["api_key"])
            if json["api_key"] == "quota-key":
                return FakeResponse(
                    432,
                    {"detail": {"error": "usage limit"}},
                    "usage limit",
                )
            return FakeResponse(200, {"results": [{"title": "ok"}]})

        with patch.object(pipeline.config, "TAVILY_API_KEYS", ["quota-key", "working-key"]), \
             patch.object(pipeline.requests, "post", side_effect=fake_post):
            results = pipeline._search_tavily("DemoCo")

        self.assertEqual(results[0]["results"], [{"title": "ok"}])
        self.assertEqual(results[1]["results"], [{"title": "ok"}])
        self.assertEqual(
            calls,
            ["quota-key", "working-key", "quota-key", "working-key"],
        )


if __name__ == "__main__":
    unittest.main()
