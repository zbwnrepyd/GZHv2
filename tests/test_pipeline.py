import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import pipeline


class PipelineFailureTests(unittest.TestCase):
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
