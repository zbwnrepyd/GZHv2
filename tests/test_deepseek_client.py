import os
import sys
import unittest
from unittest.mock import patch


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import deepseek_client


class FakeDeepSeekResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "ok"}}]}


class DeepSeekClientTests(unittest.TestCase):
    def test_call_deepseek_uses_configured_api_url(self):
        original_url = deepseek_client.config.DEEPSEEK_API_URL
        deepseek_client.config.DEEPSEEK_API_URL = "https://deepseek.example.test/chat"
        try:
            with patch.object(
                deepseek_client.requests,
                "post",
                return_value=FakeDeepSeekResponse(),
            ) as post:
                result = deepseek_client.call_deepseek(
                    "test-key",
                    "system",
                    "user",
                    max_retries=1,
                )

            self.assertEqual(result, "ok")
            self.assertEqual(post.call_args.args[0], "https://deepseek.example.test/chat")
        finally:
            deepseek_client.config.DEEPSEEK_API_URL = original_url


if __name__ == "__main__":
    unittest.main()
