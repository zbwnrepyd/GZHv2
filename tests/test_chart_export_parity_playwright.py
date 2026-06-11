"""v2.1 Playwright PNG 导出一致性测试 — 验证 preview HTML 与导出 PNG 一致"""
from __future__ import annotations
import hashlib
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))
from infographic import build_competitive_landscape_svg, build_stack_positioning_svg


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _render_to_png(html: str, width: int = 800, height: int = 600) -> bytes:
    """用 Playwright 将 HTML 渲染为 PNG 字节"""
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False) as f:
        f.write(html)
        html_path = f.name

    try:
        from playwright.sync_api import sync_playwright
        from asset_pipeline import _find_chromium

        with sync_playwright() as p:
            exe = _find_chromium()
            if not exe:
                raise RuntimeError("Chromium not found")
            browser = p.chromium.launch(
                headless=True, executable_path=exe,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(f"file://{html_path}")
            # 等待 ECharts 渲染完成（canvas 出现）
            try:
                page.wait_for_function(
                    "() => document.querySelector('canvas') !== null",
                    timeout=5000,
                )
            except Exception:
                pass  # 即使没有 canvas 也截一张
            page.wait_for_timeout(500)
            png_bytes = page.screenshot(full_page=False)
            browser.close()
            return png_bytes
    finally:
        if os.path.exists(html_path):
            os.remove(html_path)


@unittest.skipUnless(
    os.environ.get("RUN_PLAYWRIGHT_TESTS") == "1",
    "Set RUN_PLAYWRIGHT_TESTS=1 to run Playwright parity tests",
)
class ChartExportParityTests(unittest.TestCase):
    """Playwright PNG 导出一致性测试（需要 Chromium + ECharts vendor）"""

    def test_competitive_chart_renders_png(self):
        """竞争图可以生成非空 PNG"""
        html = build_competitive_landscape_svg([
            {"company_name": "TestCo", "score_incumbent_attention": 7, "score_defensibility": 8, "funding_stage_score": 6},
            {"company_name": "OtherCo", "score_incumbent_attention": 4, "score_defensibility": 3, "funding_stage_score": 4},
        ], "TestCo", {"theme": "light"})
        png = _render_to_png(html)
        self.assertGreater(len(png), 1024, "PNG 太小，可能渲染失败")
        # 验证是 PNG 格式
        self.assertTrue(png[:4] == b"\x89PNG" or png[:8].startswith(b"\x89PNG"))

    def test_competitive_chart_same_html_same_png(self):
        """同一 HTML 两次渲染应产生相同 PNG（确定性渲染）"""
        html = build_competitive_landscape_svg([
            {"company_name": "TestCo", "score_incumbent_attention": 7, "score_defensibility": 8, "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        png1 = _render_to_png(html)
        png2 = _render_to_png(html)
        h1 = _sha256_bytes(png1)
        h2 = _sha256_bytes(png2)
        self.assertEqual(h1, h2, "两次渲染的 PNG hash 不一致（可能是动画/随机因素）")

    def test_ecosystem_chart_renders_png(self):
        """生态位图可以生成非空 PNG"""
        html = build_stack_positioning_svg([
            {"company_name": "TestCo", "score_value_capture": 7, "stack_layer": "vertical_app", "funding_stage_score": 6},
            {"company_name": "OtherCo", "score_value_capture": 4, "stack_layer": "middleware", "funding_stage_score": 4},
        ], "TestCo", {"theme": "light"})
        png = _render_to_png(html)
        self.assertGreater(len(png), 1024)

    def test_chart_export_dimensions_correct(self):
        """导出的 PNG 尺寸应与 viewport 一致（800×600）"""
        html = build_competitive_landscape_svg([
            {"company_name": "TestCo", "score_incumbent_attention": 7, "score_defensibility": 8, "funding_stage_score": 6},
        ], "TestCo", {"theme": "light"})
        from PIL import Image
        import io
        png = _render_to_png(html)
        img = Image.open(io.BytesIO(png))
        self.assertEqual(img.size, (800, 600), f"Expected 800×600, got {img.size}")


if __name__ == "__main__":
    unittest.main()
