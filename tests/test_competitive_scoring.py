import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import competitive_scoring


class CompetitiveScoringTests(unittest.TestCase):
    def test_scores_follow_axis_formulas(self):
        row = {
            "ai_model_dependency": "fine_tuned",
            "workflow_integration_level": "workflow_embedded",
            "data_flywheel": "partial",
            "proprietary_data_asset": "yes_supplementary",
            "incumbent_direct_competitor": "multiple",
            "customer_segment_type": "developer_api",
            "funding_stage": "series_b",
            "pricing_model": "usage_based",
            "inference_cost_exposure": "medium",
        }

        scores = competitive_scoring.compute_scores(row)

        # v2 新公式预期值
        # defensibility: 0.30×5 + 0.25×7 + 0.20×7 + 0.15×5 + 0.10×5 = 5.9
        self.assertAlmostEqual(scores["score_defensibility"], 5.9)
        # incumbent_attention: 0.40×9 + 0.25×3 + 0.20×3 + 0.15×3 = 5.4
        self.assertAlmostEqual(scores["score_incumbent_attention"], 5.4)
        # value_capture: 0.35×4 + 0.25×4 + 0.25×7 + 0.15×7 = 5.2
        self.assertAlmostEqual(scores["score_value_capture"], 5.2)
        self.assertEqual(scores["funding_stage_score"], 7)

    def test_funding_stage_inference_overrides_understated_default(self):
        row = competitive_scoring.normalize_fields({
            "funding_stage": "pre_seed",
            "funding_info": "B轮 $80M",
        })

        self.assertEqual(row["funding_stage"], "series_b")

    def test_funding_stage_can_be_inferred_from_funding_info(self):
        self.assertEqual(
            competitive_scoring.infer_funding_stage("Series B $80M, investors A and B"),
            "series_b",
        )
        self.assertEqual(
            competitive_scoring.infer_funding_stage("C轮 $275M，估值$10B"),
            "series_c_plus",
        )
        self.assertEqual(
            competitive_scoring.infer_funding_stage("A轮 $16.4M，NEA领投"),
            "series_a",
        )
        self.assertEqual(
            competitive_scoring.infer_funding_stage("种子轮 $10M，a16z领投"),
            "seed",
        )
        self.assertEqual(
            competitive_scoring.infer_funding_stage("Pre-seed round, $2M"),
            "pre_seed",
        )


if __name__ == "__main__":
    unittest.main()
