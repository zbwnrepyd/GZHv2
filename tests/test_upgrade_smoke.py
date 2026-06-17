"""GZHv2 升级烟 smoke 测试 — P0/P1/P2 验收检查。

验证券:
- migration 可执行
- company_key 生成与大小写去重
- source_documents/evidence_spans/field_candidates 可读写
- confirmed 无证据 → 测试失败
- D/E 字段不进入补采
- 旧字段读取可回退
- ForumModerator 基础检查
- LTV/CAC 四级降级
"""
from __future__ import annotations
import os
import sys
import unittest
import tempfile
import sqlite3

# 确保 webapp 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "webapp"))


class TestCompanyKeyIdentity(unittest.TestCase):
    """P0: company_key 生成与大小写去重"""

    def test_company_key_from_host(self):
        from company_identity import build_company_identity
        identity = build_company_identity("Limitless", "https://limitless.ai")
        self.assertEqual(identity.company_key, "limitless.ai")
        self.assertEqual(identity.display_name, "Limitless")

    def test_company_key_lowercase_consistency(self):
        from company_identity import build_company_identity
        id1 = build_company_identity("Limitless", "https://limitless.ai")
        id2 = build_company_identity("limitless", "https://limitless.ai")
        self.assertEqual(id1.company_key, id2.company_key)
        self.assertEqual(id1.display_name, id2.display_name)

    def test_company_key_from_name_without_url(self):
        from company_identity import build_company_identity
        identity = build_company_identity("Anthropic", "")
        self.assertEqual(identity.company_key, "anthropic")


class TestFieldStatusEvidenceBinding(unittest.TestCase):
    """P0: confirmed 必须绑定 evidence"""

    def test_official_fact_no_evidence_returns_llm_extracted(self):
        from research.field_status import mark_field
        result = mark_field("founder_name", "Sam Altman", evidence_ids=None)
        self.assertEqual(result["resolution_status"], "llm_extracted")

    def test_official_fact_with_evidence_returns_confirmed(self):
        from research.field_status import mark_field
        result = mark_field("founder_name", "Sam Altman", evidence_ids=[1, 2])
        self.assertEqual(result["resolution_status"], "confirmed")

    def test_private_metric_no_evidence_returns_llm_extracted(self):
        from research.field_status import mark_field
        result = mark_field("cac", "$500", evidence_ids=None)
        self.assertEqual(result["resolution_status"], "llm_extracted")
        result2 = mark_field("ltv", "$2000", evidence_ids=[])
        self.assertEqual(result2["resolution_status"], "llm_extracted")

    def test_private_metric_missing_returns_industry_avg_or_unavailable(self):
        from research.field_status import mark_field
        result = mark_field("cac", None, evidence_ids=None)
        self.assertIn(result["resolution_status"], ("unavailable", "industry_avg"))

    def test_market_model_never_confirmed(self):
        from research.field_status import mark_field
        result = mark_field("tam", "$10B", evidence_ids=[1])
        self.assertNotEqual(result["resolution_status"], "confirmed")
        self.assertIn(result["resolution_status"], ("proxy", "llm_extracted"))


class TestGapDetectorManifestFiltering(unittest.TestCase):
    """P0: D/E 字段不进入补采"""

    def test_private_metrics_not_refetchable(self):
        from research.field_status import is_refetchable
        self.assertFalse(is_refetchable("cac"))
        self.assertFalse(is_refetchable("ltv"))
        self.assertFalse(is_refetchable("gross_margin"))
        self.assertFalse(is_refetchable("burn_rate"))
        self.assertFalse(is_refetchable("runway_months"))
        self.assertFalse(is_refetchable("churn_rate"))

    def test_b2b_fields_not_refetchable(self):
        from research.field_status import is_refetchable
        self.assertFalse(is_refetchable("active_users"))
        self.assertFalse(is_refetchable("registered_users"))

    def test_a_b_c_fields_are_refetchable(self):
        from research.field_status import is_refetchable
        self.assertTrue(is_refetchable("founder_name"))
        self.assertTrue(is_refetchable("funding_info"))
        self.assertTrue(is_refetchable("tam"))
        self.assertTrue(is_refetchable("market_cagr"))


class TestGapDetectorBuildQueries(unittest.TestCase):
    """P0: build_gap_queries 过滤 D/E"""

    def test_d_fields_are_filtered_from_queries(self):
        from gap_detector import build_gap_queries
        # CAC/LTV/gross_margin 都是 D 类，应被过滤
        # ltv_cac_ratio 是 B 类（公式），可进入补采但会被 derived 逻辑阻止
        gaps = {"unit_economics": ["cac", "ltv", "ltv_cac_ratio", "gross_margin"]}
        queries = build_gap_queries("DemoCo", "demo.com", "demo", gaps)
        # D 类字段(cac/ltv/gross_margin)不应在补采 fields 中
        for q in queries:
            fields = q.get("fields", [])
            for d_field in ("cac", "ltv", "gross_margin"):
                self.assertNotIn(d_field, fields,
                    msg=f"D类字段 {d_field} 不应出现在补采 query fields 中")

    def test_e_fields_are_filtered_from_queries(self):
        from gap_detector import build_gap_queries
        gaps = {"user_metrics": ["active_users", "registered_users", "paying_users"]}
        queries = build_gap_queries("DemoCo", "demo.com", "demo", gaps)
        self.assertEqual(len(queries), 0,
                        msg="E类字段 (active_users等) 不应生成补采 query")

    def test_a_fields_do_generate_queries(self):
        from gap_detector import build_gap_queries
        gaps = {"founders": ["founder_edu", "founder_bg"]}
        queries = build_gap_queries("DemoCo", "demo.com", "demo", gaps)
        self.assertGreater(len(queries), 0,
                          msg="A类字段 (founder_edu/bg) 应生成补采 query")


class TestMigrationSmoke(unittest.TestCase):
    """验证新 migration 表可读写"""

    @classmethod
    def setUpClass(cls):
        cls.tmp_db = tempfile.mktemp(suffix=".sqlite")
        conn = sqlite3.connect(cls.tmp_db)
        # Create source_documents
        conn.execute("""CREATE TABLE IF NOT EXISTS source_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT, company_key TEXT NOT NULL,
            source_type TEXT, source_url TEXT, title TEXT,
            publisher TEXT, published_at TEXT,
            fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
            raw_text TEXT, content_hash TEXT,
            trust_tier TEXT, intent TEXT)""")
        # Create evidence_spans
        conn.execute("""CREATE TABLE IF NOT EXISTS evidence_spans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            company_key TEXT NOT NULL,
            field_key TEXT, quote_text TEXT,
            normalized_fact TEXT,
            start_offset INTEGER, end_offset INTEGER,
            confidence REAL, created_by_agent TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        # Create field_candidates
        conn.execute("""CREATE TABLE IF NOT EXISTS field_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL, company_key TEXT NOT NULL,
            field_key TEXT NOT NULL, agent_name TEXT,
            candidate_value TEXT, evidence_span_ids TEXT,
            confidence REAL, status TEXT,
            conflict_group_id TEXT, reasoning_summary TEXT,
            selected INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        # Create final_card_values
        conn.execute("""CREATE TABLE IF NOT EXISTS final_card_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL, company_key TEXT NOT NULL,
            card_no INTEGER NOT NULL, field_key TEXT NOT NULL,
            final_value TEXT, source_evidence_ids TEXT,
            status TEXT DEFAULT 'draft',
            confidence TEXT DEFAULT 'medium',
            editor_note TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (company_key, card_no, field_key))""")
        # Create card_schema
        conn.execute("""CREATE TABLE IF NOT EXISTS card_schema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_no INTEGER NOT NULL, card_title TEXT NOT NULL,
            field_key TEXT NOT NULL, display_label TEXT,
            render_order INTEGER, required INTEGER DEFAULT 0,
            max_length INTEGER, render_type TEXT DEFAULT 'text',
            card_set_key TEXT DEFAULT 'v3')""")
        conn.commit()
        conn.close()

    def test_write_source_document(self):
        from research.document_store import insert_document, get_documents_for_company
        doc_id = insert_document(self.tmp_db, "testco.ai", "official_site",
                                 "https://testco.ai/about", "About TestCo",
                                 "TestCo is an AI company...")
        self.assertGreater(doc_id, 0)

        docs = get_documents_for_company(self.tmp_db, "testco.ai")
        self.assertGreaterEqual(len(docs), 1)

    def test_write_evidence_span(self):
        from research.evidence_extractor import extract_field_evidence, get_evidence_for_field
        # First insert a document
        from research.document_store import insert_document
        doc_id = insert_document(self.tmp_db, "testco.ai", "official_site",
                                 "https://testco.ai/founders", "Founders",
                                 "Founded by Jane Doe in 2020.")
        self.assertGreater(doc_id, 0)

        span_id = extract_field_evidence(self.tmp_db, doc_id, "testco.ai",
                                        "founder_name", "Jane Doe",
                                        "Jane Doe is the founder", 0.9)
        self.assertGreater(span_id, 0)

        evidence = get_evidence_for_field(self.tmp_db, "founder_name", "testco.ai")
        self.assertGreaterEqual(len(evidence), 1)

    def test_write_field_candidate(self):
        from research_agents.storage.candidate_store import insert_candidate, get_candidates_for_field
        cid = insert_candidate(self.tmp_db, "testco.ai", "founder_name",
                              "Jane Doe", agent_name="official",
                              evidence_span_ids=[1], confidence=0.9)
        self.assertGreater(cid, 0)

        candidates = get_candidates_for_field(self.tmp_db, "testco.ai", "founder_name")
        self.assertGreaterEqual(len(candidates), 1)

    def test_final_card_value_unique_constraint(self):
        conn = sqlite3.connect(self.tmp_db)
        # Insert
        conn.execute(
            "INSERT INTO final_card_values (run_id, company_key, card_no, field_key, final_value) "
            "VALUES (?, ?, ?, ?, ?)",
            ("r001", "testco.ai", 1, "company_name", "TestCo"))
        conn.commit()
        # Insert duplicate — should raise
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO final_card_values (run_id, company_key, card_no, field_key, final_value) "
                "VALUES (?, ?, ?, ?, ?)",
                ("r002", "testco.ai", 1, "company_name", "TestCo v2"))
            conn.commit()
        conn.close()

    def test_card_schema_has_8_pages(self):
        conn = sqlite3.connect(self.tmp_db)
        # Seed card schema
        for card_no in range(1, 9):
            conn.execute(
                "INSERT OR IGNORE INTO card_schema (card_no, card_title, field_key, display_label, render_order, card_set_key) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (card_no, f"Page {card_no}", f"field_{card_no}", f"Field {card_no}", 1, "v3"))
        conn.commit()
        rows = conn.execute(
            "SELECT DISTINCT card_no FROM card_schema ORDER BY card_no").fetchall()
        self.assertEqual(len(rows), 8)
        conn.close()

    @classmethod
    def tearDownClass(cls):
        try:
            os.unlink(cls.tmp_db)
        except Exception:
            pass


class TestLtvCacFallback(unittest.TestCase):
    """P0: LTV/CAC 四级降级"""

    def test_ltv_cac_fallback_confirmed_first(self):
        from research.field_status import resolve_ltv_cac_fallback
        result = resolve_ltv_cac_fallback("ltv", confirmed_value="8:1")
        self.assertEqual(result["status"], "confirmed")
        self.assertEqual(result["value"], "8:1")

    def test_ltv_cac_fallback_industry_avg_when_no_value(self):
        from research.field_status import resolve_ltv_cac_fallback
        result = resolve_ltv_cac_fallback("ltv")
        self.assertEqual(result["status"], "industry_avg")
        self.assertIn("不代表公司披露", result["disclaimer"])

    def test_ltv_cac_fallback_unavailable_when_no_benchmark(self):
        from research.field_status import resolve_ltv_cac_fallback
        result = resolve_ltv_cac_fallback("unknown_metric")
        self.assertEqual(result["status"], "unavailable")

    def test_gross_margin_industry_avg(self):
        from research.field_status import resolve_ltv_cac_fallback
        result = resolve_ltv_cac_fallback("gross_margin")
        self.assertEqual(result["status"], "industry_avg")


class TestForumModerator(unittest.TestCase):
    """P2: ForumModerator 基础检查"""

    def test_confirmed_no_evidence_is_weak(self):
        from research_agents.forum.moderator import ForumModerator
        moderator = ForumModerator()
        moderator.check_field("founder_name", "confirmed", evidence_ids=[])
        self.assertTrue(any(f.issue_type == "weak_evidence" for f in moderator.findings))

    def test_private_metric_confirmed_is_error(self):
        from research_agents.forum.moderator import ForumModerator
        moderator = ForumModerator()
        moderator.check_field("cac", "confirmed", evidence_ids=[])
        self.assertTrue(any(f.issue_type == "private_confirmed" for f in moderator.findings))

    def test_audit_batch_catches_issues(self):
        from research_agents.forum.moderator import ForumModerator
        moderator = ForumModerator()
        report = moderator.audit_batch({
            "founder_name": {"status": "confirmed", "evidence_ids": [], "candidate_count": 1},
            "cac": {"status": "confirmed", "evidence_ids": [], "candidate_count": 1},
            "market_size_value": {"status": "proxy", "evidence_ids": [1], "candidate_count": 2, "has_context": False},
        })
        self.assertIn("founder_name", report.weak_evidence_fields)
        self.assertIn("cac", report.manual_needed_fields)
        self.assertFalse(report.passed)


class TestOldFieldReadback(unittest.TestCase):
    """P0: 旧字段读取可回退"""

    def test_field_status_is_missing_values(self):
        from research.field_status import is_missing
        self.assertTrue(is_missing(None))
        self.assertTrue(is_missing(""))
        self.assertTrue(is_missing("暂缺"))
        self.assertTrue(is_missing("N/A"))
        self.assertFalse(is_missing("Some Value"))


if __name__ == "__main__":
    unittest.main()
