"""测试文档清洗器 — 验证噪音文本过滤"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "webapp"))
from research.context.document_cleaner import clean_document_text


class TestDocumentCleaner(unittest.TestCase):

    def test_cookie_page_detected(self):
        """cookie/privacy/terms 页面应被识别为噪音页"""
        text = """
        Cookie Policy
        We use cookies to improve your browsing experience.
        By continuing to browse this site, you agree to our use of cookies.
        Cookie settings and preferences can be adjusted in your browser.
        """
        result = clean_document_text(text, source_type="official_site")
        self.assertTrue(result["is_noise_page"],
                       f"Cookie page should be detected as noise, flags={result['noise_flags']}")
        self.assertTrue(result["is_low_quality"])

    def test_privacy_page_detected(self):
        """Privacy Policy 页面应被识别"""
        text = """
        Privacy Policy
        Last updated: January 2026
        This Privacy Policy describes how we collect, use, and share your personal data.
        Data Protection Policy compliance with GDPR.
        """
        result = clean_document_text(text)
        self.assertTrue(result["is_noise_page"],
                       f"Privacy page should be detected, flags={result['noise_flags']}")

    def test_terms_page_detected(self):
        """Terms of Service 页面应被识别"""
        text = """
        Terms of Service
        Please read these terms and conditions carefully before using our service.
        By accessing or using the service, you agree to be bound by these terms.
        """
        result = clean_document_text(text)
        self.assertTrue(result["is_noise_page"])

    def test_login_page_detected(self):
        """Sign in / Sign up 页面应被识别"""
        text = """
        Sign In to Your Account
        Email address
        Password
        Forgot password? Reset password
        Don't have an account? Sign up now
        """
        result = clean_document_text(text)
        self.assertTrue(result["is_noise_page"],
                       f"Auth page should be detected, flags={result['noise_flags']}")

    def test_footer_removed(self):
        """Footer 行应被过滤"""
        text = """Our company provides AI solutions.
© 2025 Example Corp. All rights reserved.
Privacy Policy | Terms of Service | Cookie Settings
Subscribe to our newsletter for updates."""
        result = clean_document_text(text)
        self.assertNotIn("All rights reserved", result["clean_text"])
        self.assertNotIn("Subscribe to our newsletter", result["clean_text"])

    def test_cta_removed(self):
        """CTA 行应被过滤"""
        text = """Our product helps teams collaborate better.
Start free trial today! No credit card required.
Book a demo with our sales team."""
        result = clean_document_text(text)
        self.assertNotIn("Start free trial", result["clean_text"])
        self.assertNotIn("Book a demo", result["clean_text"])

    def test_youtube_greeting_removed(self):
        """YouTube 寒暄/口播应被过滤"""
        text = """Hey guys, welcome back to the channel!
Don't forget to like and subscribe and hit the bell icon.
Today we're looking at this amazing AI startup.
Thanks for watching, see you in the next video!"""
        result = clean_document_text(text)
        self.assertNotIn("Hey guys", result["clean_text"])
        self.assertNotIn("like and subscribe", result["clean_text"])
        self.assertNotIn("Thanks for watching", result["clean_text"])

    def test_sponsor_mention_removed(self):
        """赞助口播应被过滤"""
        text = """This video is sponsored by Example Corp.
Brought to you by our friends at Acme Inc.
The product itself is quite interesting."""
        result = clean_document_text(text)
        self.assertNotIn("sponsored by", result["clean_text"])
        self.assertNotIn("Brought to you by", result["clean_text"])
        self.assertIn("product itself", result["clean_text"])

    def test_normal_text_preserved(self):
        """正常内容应被保留"""
        text = """Anthropic is an AI safety company based in San Francisco.
Founded in 2021 by Dario Amodei and Daniela Amodei.
The company has raised over $7 billion in funding.
Their flagship product is Claude, an AI assistant."""
        result = clean_document_text(text)
        self.assertFalse(result["is_noise_page"])
        self.assertFalse(result["is_low_quality"])
        self.assertIn("Anthropic", result["clean_text"])
        self.assertIn("Claude", result["clean_text"])
        self.assertIn("$7 billion", result["clean_text"])

    def test_short_noise_page_fully_removed(self):
        """短噪音页面（<500字符全噪音）应完全丢弃"""
        text = """Cookie Policy
We use cookies. Cookie settings."""
        result = clean_document_text(text)
        self.assertEqual(result["clean_text"], "")
        self.assertTrue(result["is_low_quality"])

    def test_advertisement_removed(self):
        """广告应被过滤"""
        text = """Advertisement
Sponsored Content — This is a promoted story.
The company announced their latest funding round."""
        result = clean_document_text(text)
        self.assertNotIn("Sponsored Content", result["clean_text"])

    def test_removed_ratio_tracked(self):
        """过滤率应被正确统计"""
        text = "Real content here.\n" * 10
        text += "\nSubscribe to our newsletter!\n"
        text += "Follow us on social media!\n"
        text += "© 2025 All Rights Reserved\n"
        result = clean_document_text(text)
        self.assertGreater(result["removed_ratio"], 0.0)
        self.assertLess(result["removed_ratio"], 1.0)  # 不应完全清空


if __name__ == "__main__":
    unittest.main()
