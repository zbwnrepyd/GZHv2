"""Tests for image_query.py — 搜索词生成与占位符过滤"""
import os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))

from image_query import build_image_queries, _json_array


class BuildImageQueriesTests(unittest.TestCase):
    """测试 build_image_queries 数据清洗逻辑"""

    def test_filters_zunque_product_name_from_tavily_queries(self):
        """product_name='暂缺' 时不生成包含「暂缺」的 Tavily 查询"""
        record = {
            "company_name": "TestCo",
            "website_url": "https://testco.com",
            "main_product_name": "暂缺",
            "other_products": [],
            "competitors": [],
        }
        result = build_image_queries(record)
        pm = result["product_main"]
        # Tavily queries 不应包含 "暂缺"
        for q in pm["tavily_queries"]:
            self.assertNotIn("暂缺", q, f"查询含占位符: {q}")

    def test_filters_non_http_main_product_img_src(self):
        """main_product_img_src 非 http 时不作为 playwright_url"""
        record = {
            "company_name": "TestCo",
            "website_url": "https://testco.com",
            "main_product_name": "TestProduct",
            "main_product_img_src": "官网产品截图",  # 中文描述，非 URL
            "other_products": [],
            "competitors": [],
        }
        result = build_image_queries(record)
        pm = result["product_main"]
        # playwright_urls 应该只有 website_url，不含中文描述
        self.assertEqual(len(pm["playwright_urls"]), 1)
        self.assertEqual(pm["playwright_urls"][0], "https://testco.com")

    def test_keeps_valid_main_product_img_src(self):
        """有效的 http URL 保留在 playwright_urls 中"""
        record = {
            "company_name": "TestCo",
            "website_url": "https://testco.com",
            "main_product_name": "TestProduct",
            "main_product_img_src": "https://testco.com/product-screenshot.png",
            "other_products": [],
            "competitors": [],
        }
        result = build_image_queries(record)
        pm = result["product_main"]
        self.assertIn("https://testco.com/product-screenshot.png", pm["playwright_urls"])
        self.assertIn("https://testco.com", pm["playwright_urls"])

    def test_handles_empty_competitors(self):
        """空竞品列表返回空 per_comp"""
        record = {
            "company_name": "TestCo",
            "website_url": "https://testco.com",
            "main_product_name": "TestProduct",
            "other_products": [],
            "competitors": [],
        }
        result = build_image_queries(record)
        self.assertEqual(result["competitors"]["per_comp"], [])

    def test_handles_empty_other_products(self):
        """空其他产品列表返回空 per_product"""
        record = {
            "company_name": "TestCo",
            "website_url": "https://testco.com",
            "main_product_name": "TestProduct",
            "other_products": [],
            "competitors": [],
        }
        result = build_image_queries(record)
        self.assertEqual(result["products_other"]["per_product"], [])

    def test_skips_zunque_competitor_names_in_queries(self):
        """竞品名为「暂缺」时跳过，不生成无意义查询"""
        record = {
            "company_name": "TestCo",
            "website_url": "https://testco.com",
            "main_product_name": "TestProduct",
            "other_products": [],
            "competitors": [
                {"name": "暂缺", "url": ""},
                {"name": "RealCompetitor", "url": "https://realcompetitor.com"},
            ],
        }
        result = build_image_queries(record)
        per_comp = result["competitors"]["per_comp"]
        # 只应有 RealCompetitor，暂缺被跳过
        self.assertEqual(len(per_comp), 1)
        self.assertEqual(per_comp[0]["name"], "RealCompetitor")

    def test_skips_zunque_product_name_in_other_products(self):
        """其他产品名为「暂缺」时跳过"""
        record = {
            "company_name": "TestCo",
            "website_url": "https://testco.com",
            "main_product_name": "TestProduct",
            "other_products": [
                {"name": "暂缺", "url": ""},
                {"name": "RealProduct", "url": "https://testco.com/real"},
            ],
            "competitors": [],
        }
        result = build_image_queries(record)
        per_product = result["products_other"]["per_product"]
        self.assertEqual(len(per_product), 1)
        self.assertEqual(per_product[0]["name"], "RealProduct")

    def test_handles_missing_fields_gracefully(self):
        """所有字段缺失时不崩溃"""
        result = build_image_queries({})
        self.assertIsInstance(result, dict)
        self.assertIn("product_main", result)
        self.assertEqual(result["competitors"]["per_comp"], [])


class JsonArrayTests(unittest.TestCase):
    """测试 _json_array 安全解析"""

    def test_parses_json_string(self):
        self.assertEqual(_json_array('[{"name":"a"}]'), [{"name": "a"}])

    def test_returns_list_as_is(self):
        self.assertEqual(_json_array([{"name": "a"}]), [{"name": "a"}])

    def test_handles_none(self):
        self.assertEqual(_json_array(None), [])

    def test_handles_empty_string(self):
        self.assertEqual(_json_array(""), [])

    def test_handles_invalid_json(self):
        self.assertEqual(_json_array("not json"), [])


if __name__ == "__main__":
    unittest.main()
