import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

from screenshot_client import BAD_PAGE_KEYWORDS, is_bad_page_text


class ScreenshotClientTests(unittest.TestCase):
    def test_detects_login_captcha_and_cloudflare_pages(self):
        self.assertIn("cloudflare", BAD_PAGE_KEYWORDS)
        self.assertTrue(is_bad_page_text("Please login to continue"))
        self.assertTrue(is_bad_page_text("Verify you are human - Cloudflare"))
        self.assertFalse(is_bad_page_text("DemoCo product dashboard with automation charts"))


if __name__ == "__main__":
    unittest.main()
