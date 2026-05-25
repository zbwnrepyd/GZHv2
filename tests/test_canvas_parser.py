import json
import os
import subprocess
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))


def run_parser(markdown: str) -> dict:
    parser_path = os.path.join(ROOT, "canvas", "js", "markdown-parser.js")
    script = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync({json.dumps(parser_path)}, 'utf8');
const context = {{}};
vm.createContext(context);
vm.runInContext(code, context);
const result = context.parseFullMarkdown({json.dumps(markdown)});
console.log(JSON.stringify(result));
"""
    output = subprocess.check_output(["node", "-e", script], text=True)
    return json.loads(output)


class CanvasParserTests(unittest.TestCase):
    def test_parse_confirmed_markdown_english_keys_for_card7(self):
        markdown = textwrap.dedent(
            """
            ## 卡片7：总结

            - **moat**：迁移成本高，数据结构和团队流程深度绑定。
            - **competitors**：[{"name":"Airtable","product":"Airtable","data":"ARR 公开估计"}]
            - **market_opportunity**：AI 工作流重构带来新机会。
            """
        ).strip()

        parsed = run_parser(markdown)

        self.assertEqual(parsed["7"]["竞争壁垒"], "迁移成本高，数据结构和团队流程深度绑定。")
        self.assertIn("TOP1", parsed["7"]["竞争格局"])
        self.assertIn("Airtable", parsed["7"]["竞争格局"])
        self.assertEqual(parsed["7"]["赛道契机"], "AI 工作流重构带来新机会。")

    def test_parse_confirmed_markdown_json_timeline_for_card3(self):
        markdown = textwrap.dedent(
            """
            ## 卡片3：发展沿袭

            - **timeline_events**：[{"date":"2024-01","event":"发布首个版本","impact":"获得首批用户"}]
            """
        ).strip()

        parsed = run_parser(markdown)

        self.assertNotIn("[{", parsed["3"]["发展沿袭时间线"])
        self.assertIn("2024-01", parsed["3"]["发展沿袭时间线"])
        self.assertIn("发布首个版本", parsed["3"]["发展沿袭时间线"])
        self.assertIn("获得首批用户", parsed["3"]["发展沿袭时间线"])

    def test_parse_draft_list_cards(self):
        markdown = textwrap.dedent(
            """
            ## 卡片3：发展沿袭

            - **2024-01** 发布产品 — *获得首批用户*

            ## 卡片5：其他产品

            - **Calendar**：日历产品（日程联动）

            ## 卡片7：总结

            **竞争壁垒**：生态粘性强
            **TOP1**：Airtable — 数据库产品（公开数据）
            **赛道契机**：AI 办公需求上升
            """
        ).strip()

        parsed = run_parser(markdown)

        self.assertIn("2024-01", parsed["3"]["发展沿袭时间线"])
        self.assertIn("Calendar", parsed["5"]["其他产品"])
        self.assertIn("Airtable", parsed["7"]["竞争格局"])
