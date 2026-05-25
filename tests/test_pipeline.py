import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import pipeline


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


if __name__ == "__main__":
    unittest.main()
