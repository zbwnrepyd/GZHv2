import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import competitive_batch
import db


class CompetitiveBatchTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        schema_path = os.path.join(ROOT, "db", "init_research_db.sql")
        with open(schema_path, encoding="utf-8") as f:
            schema = f.read()
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(schema)
        db.save_research_records(
            self.db_path,
            [
                {
                    "company_name": "Cursor",
                    "version": "standard",
                    "company_type": "AI 代码编辑器",
                    "company_def": "AI-first code editor for developers",
                    "funding_info": "Series B $60M",
                    "website_url": "https://cursor.com",
                    "customer_segment": "开发者和工程团队",
                    "revenue_model": "订阅制和团队版",
                    "moat": "深度嵌入开发工作流。",
                }
            ],
        )

    def tearDown(self):
        os.remove(self.db_path)

    def test_batch_extract_writes_fields_scores_and_review_flags(self):
        def fake_call(system_prompt, user_prompt):
            return """{
              "ai_model_dependency": "fine_tuned",
              "workflow_integration_level": "workflow_embedded",
              "data_flywheel": "partial",
              "proprietary_data_asset": "yes_supplementary",
              "incumbent_direct_competitor": "multiple",
              "customer_segment_type": "developer_api",
              "pricing_model": "subscription",
              "inference_cost_exposure": "medium",
              "stack_layer": "vertical_app",
              "uncertain": ["ai_model_dependency", "incumbent_direct_competitor"]
            }"""

        result = competitive_batch.batch_extract(
            self.db_path,
            call_fn=fake_call,
            company_names=["Cursor"],
        )

        self.assertEqual(result[0]["company_name"], "Cursor")
        self.assertTrue(result[0]["needs_review"])
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT ai_model_dependency, customer_segment_type, funding_stage, "
                "score_defensibility, score_incumbent_attention, score_value_capture "
                "FROM research WHERE company_name='Cursor' AND version='standard'"
            ).fetchone()

        self.assertEqual(row["ai_model_dependency"], "fine_tuned")
        self.assertEqual(row["customer_segment_type"], "developer_api")
        self.assertEqual(row["funding_stage"], "series_b")
        self.assertAlmostEqual(row["score_defensibility"], 5.9)
        self.assertAlmostEqual(row["score_incumbent_attention"], 5.4)
        self.assertAlmostEqual(row["score_value_capture"], 5.9)

    def test_dry_run_does_not_write_database(self):
        def fake_call(system_prompt, user_prompt):
            return '{"ai_model_dependency":"fine_tuned","workflow_integration_level":"workflow_embedded","data_flywheel":"partial","proprietary_data_asset":"yes_supplementary","incumbent_direct_competitor":"multiple","customer_segment_type":"developer_api","pricing_model":"subscription","inference_cost_exposure":"medium","stack_layer":"vertical_app","uncertain":[]}'

        competitive_batch.batch_extract(
            self.db_path,
            call_fn=fake_call,
            company_names=["Cursor"],
            dry_run=True,
        )

        with sqlite3.connect(self.db_path) as conn:
            value = conn.execute(
                "SELECT ai_model_dependency FROM research WHERE company_name='Cursor' AND version='standard'"
            ).fetchone()[0]

        self.assertEqual(value, "no_ai_core")

    def test_recompute_scores_backfills_legacy_rows_and_distribution(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE research SET ai_model_dependency=NULL, funding_stage=NULL, "
                "funding_stage_score=NULL, score_defensibility=NULL"
            )
            conn.commit()

        summary = competitive_batch.recompute_scores(self.db_path)

        self.assertEqual(summary["updated"], 1)
        self.assertIn("score_defensibility", summary["distribution"])
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT funding_stage, funding_stage_score, score_defensibility FROM research"
            ).fetchone()

        self.assertEqual(row["funding_stage"], "series_b")
        self.assertEqual(row["funding_stage_score"], 7)
        self.assertIsNotNone(row["score_defensibility"])

    def test_batch_extract_continues_when_one_company_returns_bad_json(self):
        db.save_research_records(
            self.db_path,
            [
                {
                    "company_name": "Harvey",
                    "version": "standard",
                    "company_type": "法律 AI",
                    "company_def": "AI legal workflow platform",
                    "funding_info": "Series C $100M",
                }
            ],
        )
        calls = []

        def flaky_call(system_prompt, user_prompt):
            calls.append(user_prompt)
            if "Cursor" in user_prompt:
                return '{"ai_model_dependency": "fine_tuned"'
            return '{"ai_model_dependency":"fine_tuned","workflow_integration_level":"system_of_record","data_flywheel":"partial","proprietary_data_asset":"yes_supplementary","incumbent_direct_competitor":"none","customer_segment_type":"b2b_enterprise","pricing_model":"enterprise_contract","inference_cost_exposure":"medium","stack_layer":"vertical_app","uncertain":[]}'

        results = competitive_batch.batch_extract(
            self.db_path,
            call_fn=flaky_call,
            company_names=["Cursor", "Harvey"],
        )

        self.assertEqual(len(results), 2)
        self.assertTrue(any(r["company_name"] == "Cursor" and "error" in r for r in results))
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            harvey = conn.execute(
                "SELECT ai_model_dependency, score_defensibility FROM research WHERE company_name='Harvey'"
            ).fetchone()

        self.assertEqual(harvey["ai_model_dependency"], "fine_tuned")
        self.assertIsNotNone(harvey["score_defensibility"])

    def test_batch_extract_retries_bad_json_once(self):
        calls = []

        def retrying_call(system_prompt, user_prompt):
            calls.append(user_prompt)
            if len(calls) == 1:
                return '{"ai_model_dependency": "fine_tuned"'
            return '{"ai_model_dependency":"fine_tuned","workflow_integration_level":"workflow_embedded","data_flywheel":"partial","proprietary_data_asset":"yes_supplementary","incumbent_direct_competitor":"multiple","customer_segment_type":"developer_api","pricing_model":"subscription","inference_cost_exposure":"medium","stack_layer":"vertical_app","uncertain":[]}'

        results = competitive_batch.batch_extract(
            self.db_path,
            call_fn=retrying_call,
            company_names=["Cursor"],
        )

        self.assertEqual(len(calls), 2)
        self.assertNotIn("error", results[0])
        self.assertEqual(results[0]["ai_model_dependency"], "fine_tuned")


if __name__ == "__main__":
    unittest.main()
