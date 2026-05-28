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


def render_card_source(card_index: int, card_data: dict, company: str = "ProjectSlug") -> str:
    renderer_path = os.path.join(ROOT, "canvas", "js", "html-card-renderer.js")
    script = f"""
const fs = require('fs');
const vm = require('vm');
const code = fs.readFileSync({json.dumps(renderer_path)}, 'utf8');
const context = {{}};
vm.createContext(context);
vm.runInContext(code, context);
const source = context.renderCardSource({{
  companyName: {json.dumps(company)},
  cardIndex: {card_index},
  cardData: {json.dumps(card_data, ensure_ascii=False)},
}});
console.log(source);
"""
    return subprocess.check_output(["node", "-e", script], text=True)


class CanvasParserTests(unittest.TestCase):
    def test_parse_confirmed_markdown_english_keys_for_card7(self):
        markdown = textwrap.dedent(
            """
            ## 卡片7：竞争格局

            - **moat**：迁移成本高，数据结构和团队流程深度绑定。
            - **competitors**：[{"name":"Airtable","product":"Airtable","data":"ARR 公开估计"}]

            ## 卡片8：总结

            - **market_opportunity**：AI 工作流重构带来新机会。
            """
        ).strip()

        parsed = run_parser(markdown)

        self.assertEqual(parsed["7"]["竞争壁垒"], "迁移成本高，数据结构和团队流程深度绑定。")
        self.assertIn("TOP1", parsed["7"]["竞争格局"])
        self.assertIn("Airtable", parsed["7"]["竞争格局"])
        self.assertEqual(parsed["8"]["赛道契机"], "AI 工作流重构带来新机会。")
        self.assertNotIn("赛道契机", parsed["7"])

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

            ## 卡片7：竞争格局

            **竞争壁垒**：生态粘性强
            **TOP1**：Airtable — 数据库产品（公开数据）

            ## 卡片8：总结

            **赛道契机**：AI 办公需求上升
            """
        ).strip()

        parsed = run_parser(markdown)

        self.assertIn("2024-01", parsed["3"]["发展沿袭时间线"])
        self.assertIn("Calendar", parsed["5"]["其他产品"])
        self.assertIn("Airtable", parsed["7"]["竞争格局"])
        self.assertEqual(parsed["8"]["赛道契机"], "AI 办公需求上升")

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

    def test_api_loader_preserves_homepage_unlabeled_type(self):
        api_json = {
            "company_name": "Cursor",
            "confirmed_count": 1,
            "cards": {
                "1": {
                    "markdown_content": textwrap.dedent(
                        """
                        ## 卡片1：首页

                        # Cursor

                        **AI 代码编辑器**
                        """
                    ).strip()
                }
            },
        }

        loaded = run_api_loader(api_json)

        self.assertEqual(loaded["allCardData"]["1"]["公司名"], "Cursor")
        self.assertEqual(loaded["allCardData"]["1"]["类型"], "AI 代码编辑器")

    def test_parser_maps_editor_markdown_aliases_to_canvas_fields(self):
        markdown = textwrap.dedent(
            """
            ## 卡片2：公司介绍

            **位置**：San Francisco
            **融资**：A轮 $10M

            ## 卡片4：主产品

            ## Cursor

            **亮点**：Agent 编程
            **成就**：ARR 快速增长

            ## 卡片6：商业模式

            **盈利**：订阅制
            **冷启动**：开发者社区
            **GTM**：PLG
            **飞轮**：用户越多插件越多

            ## 卡片7：竞争格局

            **壁垒**：迁移成本高

            ## 卡片8：总结

            **机遇**：AI IDE 重构开发流程
            """
        ).strip()

        parsed = run_parser(markdown)

        self.assertEqual(parsed["2"]["地理位置"], "San Francisco")
        self.assertEqual(parsed["2"]["融资信息"], "A轮 $10M")
        self.assertEqual(parsed["4"]["亮点功能"], "Agent 编程")
        self.assertEqual(parsed["4"]["产品成就"], "ARR 快速增长")
        self.assertEqual(parsed["6"]["盈利方式"], "订阅制")
        self.assertEqual(parsed["6"]["冷启动策略"], "开发者社区")
        self.assertEqual(parsed["6"]["GTM与增长策略"], "PLG")
        self.assertEqual(parsed["6"]["增长飞轮"], "用户越多插件越多")
        self.assertEqual(parsed["7"]["竞争壁垒"], "迁移成本高")
        self.assertEqual(parsed["8"]["赛道契机"], "AI IDE 重构开发流程")

    def test_renderer_prefers_final_markdown_company_name_over_url_slug(self):
        source = render_card_source(
            1,
            {"公司名": "Cursor", "类型": "AI 代码编辑器"},
            company="WrongSlug",
        )

        self.assertIn("Cursor", source)
        self.assertNotIn("WrongSlug</h1>", source)

    def test_renderer_uses_final_body_when_structured_fields_are_missing(self):
        source = render_card_source(
            8,
            {"_body": "**机遇**：AI IDE 重构开发流程"},
            company="Cursor",
        )

        self.assertIn("AI IDE 重构开发流程", source)
        self.assertNotIn("暂缺", source)

    def test_parser_normalizes_card7_title_from_legacy_summary_heading(self):
        api_json = {
            "company_name": "Zuma",
            "confirmed_count": 1,
            "cards": {
                "7": {
                    "markdown_content": textwrap.dedent(
                        """
                        ## 卡片7：总结

                        **壁垒**：垂直场景数据和集成壁垒。
                        """
                    ).strip()
                }
            },
        }

        loaded = run_api_loader(api_json, company="Zuma")

        self.assertEqual(loaded["allCardData"]["7"]["_title"], "竞争格局")

    def test_renderer_breadcrumb_contains_all_card_sections(self):
        source = render_card_source(
            7,
            {"竞争壁垒": "垂直场景数据和集成壁垒。", "竞争格局": "头部玩家分散。"},
            company="Zuma",
        )

        for label in ["首页", "公司介绍", "发展沿袭", "主产品", "其他产品", "商业模式", "竞争格局", "总结"]:
            self.assertIn(label, source)
        self.assertIn("<strong>竞争格局</strong>", source)

    def test_renderer_breadcrumb_uses_formal_card5_title(self):
        source = render_card_source(
            5,
            {"其他产品": "- **AI催租助手**：自动化处理租金催缴流程。"},
            company="Zuma",
        )

        self.assertIn("<strong>其他产品</strong>", source)
        self.assertNotIn("产品线", source)

    def test_parser_maps_unlabeled_intro_body_to_expected_fields(self):
        markdown = textwrap.dedent(
            """
            ## 卡片2：公司介绍

            **位置**：San Francisco

            面向开发者的 AI 代码编辑器。

            **创始人**：Michael Truell

            ## 卡片4：主产品

            ## Cursor

            AI 代码编辑器，直接嵌入开发流程。

            **亮点**：智能补全和 Agent 编程
            """
        ).strip()

        parsed = run_parser(markdown)

        self.assertEqual(parsed["2"]["公司定义"], "面向开发者的 AI 代码编辑器。")
        self.assertEqual(parsed["4"]["主产品名"], "Cursor")
        self.assertEqual(parsed["4"]["产品定义"], "AI 代码编辑器，直接嵌入开发流程。")

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

    def test_api_loader_keeps_remote_markdown_images_for_folder(self):
        api_json = {
            "company_name": "Cursor",
            "confirmed_count": 1,
            "cards": {
                "4": {
                    "markdown_content": textwrap.dedent(
                        """
                        ## 卡片4：主产品

                        ## Cursor

                        AI 代码编辑器。

                        ![产品图片](https://example.com/cursor.png)
                        """
                    ).strip()
                }
            },
        }

        loaded = run_api_loader(api_json)

        self.assertEqual(loaded["allCardData"]["4"]["_image"], "https://example.com/cursor.png")
