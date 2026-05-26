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


def run_api_loader(api_json: dict, company: str = "Cursor") -> dict:
    parser_path = os.path.join(ROOT, "canvas", "js", "markdown-parser.js")
    loader_path = os.path.join(ROOT, "canvas", "js", "api-loader.js")
    script = f"""
const fs = require('fs');
const vm = require('vm');
const parserCode = fs.readFileSync({json.dumps(parser_path)}, 'utf8');
const loaderCode = fs.readFileSync({json.dumps(loader_path)}, 'utf8');
const context = {{
  fetch: async (url) => ({{
    ok: true,
    json: async () => ({json.dumps(api_json, ensure_ascii=False)}),
  }}),
  console,
}};
vm.createContext(context);
vm.runInContext(parserCode, context);
vm.runInContext(loaderCode, context);
context.loadFromAPI({json.dumps(company)}).then((result) => {{
  console.log(JSON.stringify(result));
}}).catch((err) => {{
  console.error(err && err.stack ? err.stack : err);
  process.exit(1);
}});
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

    def test_api_loader_parses_markdown_content_json_to_canvas_fields(self):
        api_json = {
            "company_name": "Cursor",
            "confirmed_count": 1,
            "cards": {
                "1": {
                    "markdown_content": textwrap.dedent(
                        """
                        ## 卡片1：公司基础信息

                        - **company_name**：Cursor
                        - **company_type**：AI 代码编辑器
                        - **location**：旧金山
                        """
                    ).strip()
                }
            },
        }

        loaded = run_api_loader(api_json)

        self.assertEqual(loaded["company_name"], "Cursor")
        self.assertEqual(loaded["allCardData"]["1"]["公司名"], "Cursor")
        self.assertEqual(loaded["allCardData"]["1"]["类型"], "AI 代码编辑器")
        self.assertEqual(loaded["allCardData"]["1"]["地理位置"], "旧金山")

    def test_api_loader_preserves_untitled_markdown_content_body(self):
        api_json = {
            "company_name": "Cursor",
            "confirmed_count": 1,
            "cards": {
                "2": {
                    "markdown_content": textwrap.dedent(
                        """
                        ## 公司介绍

                        Cursor 是面向开发者的 AI 代码编辑器。
                        """
                    ).strip()
                }
            },
        }

        loaded = run_api_loader(api_json)

        self.assertEqual(loaded["allCardData"]["2"]["_title"], "公司介绍")
        self.assertIn("Cursor 是面向开发者", loaded["allCardData"]["2"]["_body"])

    def test_api_loader_keeps_legacy_fields_and_image_paths(self):
        api_json = {
            "company_name": "Cursor",
            "confirmed_count": 1,
            "cards": {
                "4": {
                    "fields": {
                        "main_product_name": "Cursor",
                        "main_product_def": "AI 代码编辑器",
                    },
                    "img_paths": {
                        "main_product_img_src": "/static/cursor.png",
                    },
                }
            },
        }

        loaded = run_api_loader(api_json)

        self.assertEqual(loaded["allCardData"]["4"]["主产品名"], "Cursor")
        self.assertEqual(loaded["allCardData"]["4"]["产品定义"], "AI 代码编辑器")
        self.assertEqual(loaded["allCardData"]["4"]["_image"], "/static/cursor.png")
