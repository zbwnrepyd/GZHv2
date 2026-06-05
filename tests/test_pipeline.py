import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import pipeline
import repositories.field_repo as field_repo


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

    def test_l3_retries_missing_founder_fields_inside_main_flow(self):
        def record(founder_edu="暂缺", founder_achievement="暂缺"):
            return {
                "company_type": "AI工具",
                "founder_name": "Ada Demo",
                "founder_edu": founder_edu,
                "founder_bg": "前研究员",
                "founder_achievement": founder_achievement,
                "data_confidence": "中",
            }

        # 枚举组 mock（3组各3字段）
        enum_a = '{"ai_model_dependency":"multi_model","data_flywheel":"partial","proprietary_data_asset":"yes_supplementary"}'
        enum_b = '{"incumbent_direct_competitor":"multiple","workflow_integration_level":"workflow_embedded","inference_cost_exposure":"medium"}'
        enum_c = '{"pricing_model":"subscription","customer_segment_type":"b2b2c","stack_layer":"vertical_app"}'
        vote_ai = '{"ai_model_dependency":"multi_model"}'
        vote_inc = '{"incumbent_direct_competitor":"multiple"}'
        vote_price = '{"pricing_model":"subscription"}'

        # 每个版本：L3(1) + 枚举组ABC(3) + 投票(3) + founder retry(1) = 8 calls
        e = [enum_a, enum_b, enum_c, vote_ai, vote_inc, vote_price]  # 6 enum calls per version
        responses = [
            "创始人 Ada Demo 毕业于 MIT，曾创办 Demo Labs 并获行业奖项。",  # L0
            "layer1",                                                       # L1
            "layer2",                                                       # L2
            # ── standard 版本 ──
            str(record()).replace("'", '"'),                                # L3
            *e,
            str(record("MIT", "创办 Demo Labs，获行业奖项")).replace("'", '"'),  # founder
            # ── business 版本 ──
            str(record()).replace("'", '"'),                                # L3
            *e,
            str(record("MIT", "创办 Demo Labs")).replace("'", '"'),         # founder
            # ── spread 版本 ──
            str(record()).replace("'", '"'),                                # L3
            *e,
            str(record("MIT", "创办 Demo Labs")).replace("'", '"'),         # founder
        ]
        events = []

        with patch.object(pipeline, "call_deepseek", side_effect=responses) as call, \
             patch.object(pipeline, "run_rule_layer", return_value={}):
            records = pipeline.llm_analysis(
                "DemoCo",
                "https://demo.example",
                {"website": {"text": "demo"}},
                lambda stage, detail: events.append((stage, detail)),
            )

        self.assertGreater(call.call_count, 7)  # 比原7次多出枚举提取调用
        self.assertEqual(records[0]["founder_edu"], "MIT")
        self.assertEqual(records[0]["founder_achievement"], "创办 Demo Labs，获行业奖项")
        self.assertFalse(any(stage == "补抓" for stage, _ in events))

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

        def fake_post(url, json, timeout, proxies=None):
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

    def test_prepare_raw_data_for_llm_trims_tavily_raw_content(self):
        raw = {
            "company_name": "DemoCo",
            "tavily": [
                {
                    "answer": "answer",
                    "results": [
                        {
                            "title": "Useful result",
                            "url": "https://example.com/useful",
                            "content": "short summary",
                            "score": 0.91,
                            "raw_content": "x" * 20000,
                            "extra": "drop me",
                        }
                    ],
                }
            ],
            "website": {"text": "homepage"},
        }

        prepared = pipeline._prepare_raw_data_for_llm(raw)

        result = prepared["tavily"][0]["results"][0]
        self.assertEqual(result["title"], "Useful result")
        self.assertEqual(result["url"], "https://example.com/useful")
        self.assertEqual(result["content"], "short summary")
        self.assertEqual(result["score"], 0.91)
        self.assertLess(len(result["raw_content"]), 3000)
        self.assertNotIn("extra", result)
        self.assertEqual(raw["tavily"][0]["results"][0]["raw_content"], "x" * 20000)

    def test_enum_group_ignores_non_object_llm_json(self):
        with patch.object(pipeline, "_load_prompt_text", return_value="prompt"), \
             patch.object(pipeline, "call_deepseek", return_value='"not an object"'):
            fields = pipeline._run_llm_enum_group("key", "A", "{}")

        self.assertEqual(fields, {})

    def test_run_pipeline_writes_field_rows_under_requested_company_name(self):
        inserted_batches = []
        records = [
            {
                "company_name": "limitless",
                "version": "standard",
                "company_type": "AI wearable",
                "company_def": "AI meeting memory platform",
                "data_confidence": "高",
            }
        ]

        with patch.object(pipeline, "_collect_all", return_value={"website": {"text": "ok"}}), \
             patch.object(pipeline, "llm_analysis", return_value=[dict(records[0])]), \
             patch.object(pipeline.database, "save_research_records", return_value=[101]), \
             patch.object(field_repo, "insert_research_fields_batch", side_effect=lambda _db, rows: inserted_batches.append(rows) or len(rows)), \
             patch("asset_pipeline.collect_image_variants_pipeline", return_value={}):
            ids = pipeline.run_pipeline("Limitless", "https://www.limitless.ai")

        self.assertEqual(ids, [101])
        self.assertTrue(inserted_batches)
        self.assertTrue(all(row["company_name"] == "Limitless" for row in inserted_batches[0]))
        self.assertTrue(any(row["field_key"] == "company_type" for row in inserted_batches[0]))


if __name__ == "__main__":
    unittest.main()
