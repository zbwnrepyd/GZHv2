import os
import sys
import tempfile
import unittest

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

from image_candidate import ImageCandidate
from image_quality import inspect_local_image, validate_candidate
from image_scorer import score_candidate


class ImageQualityTests(unittest.TestCase):
    def _image(self, size=(800, 500), color=(40, 120, 200), fmt="PNG") -> str:
        fd, path = tempfile.mkstemp(suffix=f".{fmt.lower()}")
        os.close(fd)
        Image.new("RGB", size, color).save(path, fmt)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    def test_rejects_small_non_logo_images_with_reason(self):
        path = self._image(size=(120, 80))
        candidate = ImageCandidate(
            company_name="DemoCo",
            asset_key="product_main",
            image_url="https://example.com/small.png",
            source_page="https://example.com",
            source_type="web_tavily",
            local_path=path,
        )

        inspect_local_image(candidate)
        passed, reason = validate_candidate(candidate)

        self.assertFalse(passed)
        self.assertIn("尺寸过小", reason)
        self.assertEqual(candidate.width, 120)
        self.assertEqual(candidate.height, 80)

    def test_logo_allows_64_square_image(self):
        path = self._image(size=(80, 80))
        candidate = ImageCandidate(
            company_name="DemoCo",
            asset_key="logo",
            image_url="https://example.com/logo.png",
            source_page="https://example.com",
            source_type="official_og_image",
            local_path=path,
        )

        inspect_local_image(candidate)
        passed, reason = validate_candidate(candidate)

        self.assertTrue(passed, reason)

    def test_rejects_extreme_ratio_images(self):
        path = self._image(size=(1800, 200))
        candidate = ImageCandidate(
            company_name="DemoCo",
            asset_key="product_main",
            image_url="https://example.com/banner.png",
            source_page="https://example.com",
            source_type="official_og_image",
            local_path=path,
        )

        inspect_local_image(candidate)
        passed, reason = validate_candidate(candidate)

        self.assertFalse(passed)
        self.assertIn("比例极端", reason)

    def test_scoring_prefers_official_relevant_large_image(self):
        official = ImageCandidate(
            company_name="DemoCo",
            asset_key="product_main",
            image_url="https://demo.example/product-dashboard.png",
            source_page="https://demo.example/product",
            source_type="official_og_image",
            title="DemoCo app dashboard screenshot",
            alt_text="DemoCo product dashboard",
            width=1200,
            height=630,
            file_size=180000,
        )
        tavily = ImageCandidate(
            company_name="DemoCo",
            asset_key="product_main",
            image_url="https://cdn.example/random.jpg",
            source_page="https://blog.example/random",
            source_type="web_tavily",
            title="generic office",
            alt_text="",
            width=500,
            height=320,
            file_size=30000,
        )

        score_candidate(official, product_names=["DemoCo"])
        score_candidate(tavily, product_names=["DemoCo"])

        self.assertGreater(official.final_score, tavily.final_score)
        self.assertGreaterEqual(official.source_score, 90)
        self.assertGreater(official.relevance_score, tavily.relevance_score)


if __name__ == "__main__":
    unittest.main()
