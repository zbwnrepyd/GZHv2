import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

import db
import markdown_builder


class MarkdownBuilderTests(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        with open(os.path.join(ROOT, "db", "init_research_db.sql"), encoding="utf-8") as f:
            schema = f.read()
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(schema)
        db.save_research_records(
            self.db_path,
            [
                {
                    "company_name": "DemoCo",
                    "version": "standard",
                    "company_type": "AI 工具",
                    "location": "San Francisco",
                    "company_def": "面向内容团队的 AI 工作流。",
                    "timeline_events": [
                        {"date": "2024-01", "event": "上线 Beta", "impact": "获得首批用户"}
                    ],
                    "competitors": [
                        {"name": "Airtable", "product": "数据库协作", "data": "公开案例多"}
                    ],
                    "moat": "流程沉淀强。",
                    "market_opportunity": "AI 内容生产转向流程系统。",
                }
            ],
        )

    def tearDown(self):
        os.remove(self.db_path)

    def test_build_card_markdown_expands_json_fields(self):
        card3 = markdown_builder.build_card_markdown(
            self.db_path, "DemoCo", 3, "standard"
        )
        card7 = markdown_builder.build_card_markdown(
            self.db_path, "DemoCo", 7, "standard"
        )

        self.assertIn("## 卡片3：发展沿袭", card3)
        self.assertIn("2024-01", card3)
        self.assertIn("获得首批用户", card3)
        self.assertIn("## 卡片7：总结", card7)
        self.assertIn("**TOP1**：Airtable", card7)
        self.assertNotIn("[{", card7)

    def test_build_card_markdown_returns_empty_for_missing_record(self):
        markdown = markdown_builder.build_card_markdown(
            self.db_path, "MissingCo", 1, "standard"
        )

        self.assertEqual(markdown, "")


if __name__ == "__main__":
    unittest.main()
