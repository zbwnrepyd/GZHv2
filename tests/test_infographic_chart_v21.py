"""v2.1 归一化与图表 option 测试 — 验证 normalize_group_scores + 图表 HTML 输出"""
from __future__ import annotations
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
from infographic import (
    normalize_group_scores,
    _truncate_label,
    _point_priority,
    build_competitive_landscape_svg,
    build_stack_positioning_svg,
)


class NormalizationTests(unittest.TestCase):
    """Revised Fix A: 非破坏式归一化测试"""

    def test_normalize_raw_fields_unchanged(self):
        companies = [
            {"name": "A", "score_defensibility": 8, "score_incumbent_attention": 6},
            {"name": "B", "score_defensibility": 4, "score_incumbent_attention": 2},
        ]
        normed, meta = normalize_group_scores(
            companies, ["score_defensibility", "score_incumbent_attention"],
        )
        # raw 字段不变
        self.assertEqual(normed[0]["score_defensibility"], 8)
        self.assertEqual(normed[0]["score_incumbent_attention"], 6)
        self.assertEqual(normed[1]["score_defensibility"], 4)
        self.assertEqual(normed[1]["score_incumbent_attention"], 2)

    def test_normalize_produces_norm_fields(self):
        companies = [
            {"name": "A", "score_defensibility": 8, "score_incumbent_attention": 6},
            {"name": "B", "score_defensibility": 4, "score_incumbent_attention": 2},
        ]
        normed, _ = normalize_group_scores(
            companies, ["score_defensibility"],
        )
        self.assertIn("score_defensibility_norm", normed[0])
        self.assertIn("score_defensibility_norm", normed[1])

    def test_normalize_range_zero_to_one(self):
        companies = [
            {"name": "A", "score_defensibility": 10},
            {"name": "B", "score_defensibility": 0},
        ]
        normed, _ = normalize_group_scores(companies, ["score_defensibility"])
        vals = [c["score_defensibility_norm"] for c in normed]
        self.assertAlmostEqual(max(vals), 1.0, places=2)
        self.assertAlmostEqual(min(vals), 0.0, places=2)

    def test_normalize_all_equal_to_neutral(self):
        companies = [
            {"name": "A", "score_defensibility": 5},
            {"name": "B", "score_defensibility": 5},
        ]
        normed, meta = normalize_group_scores(companies, ["score_defensibility"])
        self.assertIn("score_defensibility", meta["all_equal_keys"])
        for c in normed:
            self.assertAlmostEqual(c["score_defensibility_norm"], 0.5, places=2)

    def test_normalize_all_null_returns_none(self):
        companies = [
            {"name": "A", "score_defensibility": None},
            {"name": "B", "score_defensibility": None},
        ]
        normed, meta = normalize_group_scores(companies, ["score_defensibility"])
        self.assertIsNone(meta["ranges"]["score_defensibility"]["min"])
        self.assertIsNone(normed[0]["score_defensibility_norm"])

    def test_truncate_label_short_name_passes_through(self):
        self.assertEqual(_truncate_label("OpenAI", 8), "OpenAI")

    def test_truncate_label_long_name_cut(self):
        self.assertEqual(_truncate_label("AnthropicAI", 7), "Anthrop…")

    def test_point_priority_target_first(self):
        points = [
            {"company_name": "B"}, {"company_name": "A"}, {"company_name": "Target"},
        ]
        result = _point_priority(points, "Target", 12)
        self.assertEqual(result[0]["company_name"], "Target")

    def test_point_priority_capped(self):
        points = [{"company_name": f"C{i}"} for i in range(20)]
        result = _point_priority(points, "C0", 5)
        self.assertEqual(len(result), 5)
        self.assertEqual(result[0]["company_name"], "C0")


class CompetitiveChartV21Tests(unittest.TestCase):
    """v2.1 chart_competitive 渲染验证"""

    def test_chart_uses_zero_to_one_axes(self):
        html = build_competitive_landscape_svg([
            {"company_name": "TestCo", "score_incumbent_attention": 7, "score_defensibility": 8, "funding_stage_score": 6},
            {"company_name": "OtherCo", "score_incumbent_attention": 4, "score_defensibility": 3, "funding_stage_score": 4},
        ], "TestCo", {"theme": "light"})
        self.assertTrue("min:0" in html and "max:1" in html)
        self.assertNotIn("min:0, max:10", html)

    def test_chart_tooltip_contains_raw_and_norm(self):
        html = build_competitive_landscape_svg([
            {"company_name": "TestCo", "score_incumbent_attention": 7, "score_defensibility": 8, "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("护城河（相对）", html)
        self.assertIn("护城河（原始）", html)
        self.assertIn("巨头竞争压力（相对）", html)
        self.assertIn("巨头竞争压力（原始）", html)

    def test_chart_has_markline_at_zero_point_five(self):
        html = build_competitive_landscape_svg([
            {"company_name": "TestCo", "score_incumbent_attention": 7, "score_defensibility": 8, "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("xAxis:0.5", html)
        self.assertIn("yAxis:0.5", html)

    def test_chart_animation_disabled(self):
        html = build_competitive_landscape_svg([
            {"company_name": "TestCo", "score_incumbent_attention": 7, "score_defensibility": 8, "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("animation:false", html)

    def test_chart_no_data_handles_gracefully(self):
        html = build_competitive_landscape_svg([], "TestCo", {"theme": "light"})
        self.assertIn("暂无可用图表数据", html)
        self.assertIn("echarts.init", html)

    def test_chart_drops_null_incumbent_attention(self):
        html = build_competitive_landscape_svg([
            {"company_name": "TestCo", "score_incumbent_attention": None, "score_defensibility": 8, "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        # 缺失必需字段的点不应出现在图中
        self.assertIn("暂无可用图表数据", html)

    def test_chart_respects_max_companies(self):
        companies = [
            {"company_name": f"C{i}", "score_incumbent_attention": i % 10, "score_defensibility": i % 10, "funding_stage_score": 5}
            for i in range(20)
        ]
        html = build_competitive_landscape_svg(companies, "C0", {"theme": "light", "max_companies": 8})
        # point_priority 限制最多 8 个点
        # 简单检查：生成成功且有点数据
        self.assertIn("echarts.init", html)
        self.assertNotIn("暂无可用图表数据", html)


class EcosystemChartTests(unittest.TestCase):
    """chart_ecosystem 测试 — 动态标题 + 0-1 轴 + 固定点大小 + markPoint"""

    def test_dynamic_title(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 8.5, "stack_layer": "vertical_app", "funding_stage_score": 6},
            {"company_name": "OtherCo", "score_value_capture": 4.0, "stack_layer": "middleware", "funding_stage_score": 4},
        ], "TestCo", {"theme": "light"})
        self.assertIn("TestCo", html)
        self.assertIn("价值捕获", html)
        self.assertIn("：", html)

    def test_title_fallback(self):
        html = build_stack_positioning_svg([
            {"company_name": "OtherCo", "score_value_capture": 4.0, "stack_layer": "middleware", "funding_stage_score": 4},
        ], "GhostCo", {"theme": "light"})
        self.assertIn("AI 栈生态位图", html)

    def test_zero_to_one_axis(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": "vertical_app", "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        opt_start = html.find("var opt={")
        self.assertTrue("min:0,max:1" in html[opt_start:] if opt_start > 0 else "min:0,max:1" in html)

    def test_tooltip_raw_norm(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": "vertical_app", "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("价值捕获率（相对）", html)
        self.assertIn("价值捕获率（原始）", html)

    def test_null_stack_layer_handled(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": None, "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("暂无可用图表数据", html)

    def test_category_y_inverse(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": "vertical_app", "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("inverse:true", html)

    def test_subtitle(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": "vertical_app", "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("越往右，越能在产业链里赚到钱", html)

    def test_landscape_dimensions(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": "vertical_app", "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("1440px", html)
        self.assertIn("900px", html)

    def test_markpoint(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": "vertical_app", "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("markPoint", html)

    def test_bottom_guide(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": "vertical_app", "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        self.assertIn("价值捕获：低 → 中 → 高", html)

    def test_fixed_symbol_size(self):
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": "vertical_app", "funding_stage_score": 9},
            {"company_name": "OtherCo", "score_value_capture": 3, "stack_layer": "infrastructure", "funding_stage_score": 1},
        ], "TestCo", {"theme": "light"})
        self.assertIn("symbolSize", html)
        self.assertIn("is_highlight", html)


if __name__ == "__main__":
    unittest.main()
