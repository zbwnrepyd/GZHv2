import asyncio
import os
import sqlite3
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "webapp"))


class DeepResearchReportPipelineTests(unittest.TestCase):
    def test_report_named_modules_are_importable(self):
        import identity_resolver
        import query_templates
        import search_backends
        import source_fetchers
        import extractors
        import normalizers
        import field_writer

        self.assertTrue(callable(identity_resolver.build_company_identity))
        self.assertTrue(callable(query_templates.build_field_queries))
        self.assertTrue(callable(search_backends.run_parallel_search))
        self.assertTrue(callable(source_fetchers.fetch_documents))
        self.assertTrue(callable(extractors.extract_field_candidates))
        self.assertTrue(callable(normalizers.normalize_candidate))
        self.assertTrue(callable(field_writer.upsert_research_fields))

    def test_query_templates_map_v3_fields_to_intents(self):
        from identity_resolver import build_company_identity
        from query_templates import build_field_queries

        identity = build_company_identity("Perplexity", "https://www.perplexity.ai")
        queries = build_field_queries(identity, [
            "market_size_value",
            "product_tech_stack",
            "customer_names",
            "competitors_top3",
            "competitive_position",
        ])
        intents = {q["intent"] for q in queries}
        query_text = " ".join(q["query"] for q in queries)

        self.assertTrue({"market_size", "tech_stack", "customers", "competition"}.issubset(intents))
        self.assertIn("Perplexity", query_text)
        self.assertIn("site:perplexity.ai", query_text)

    def test_async_document_fetcher_dedupes_and_extracts_visible_text(self):
        from source_fetchers import fetch_documents

        async def fake_fetch(_client, url, _ctx):
            return {
                "url": url,
                "norm_url": "https://example.com/about",
                "status_code": 200,
                "content_type": "text/html",
                "html": "<html><script>drop()</script><body><h1>About Demo</h1><p>Visible text</p></body></html>",
                "sha1": "abc123",
            }

        docs = asyncio.run(fetch_documents(
            [
                {"url": "https://example.com/about?utm_source=x"},
                {"url": "https://example.com/about"},
            ],
            fetcher=fake_fetch,
        ))

        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["status"], "ok")
        self.assertIn("About Demo", docs[0]["text"])
        self.assertNotIn("drop()", docs[0]["text"])

    def test_extract_normalize_and_write_field_candidates(self):
        from extractors import extract_field_candidates
        from normalizers import normalize_candidate
        from field_writer import upsert_research_fields

        fd, db_path = tempfile.mkstemp(suffix=".sqlite")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(db_path) and os.remove(db_path))
        with sqlite3.connect(db_path) as conn:
            with open(os.path.join(ROOT, "db/init_research_db.sql"), encoding="utf-8") as f:
                conn.executescript(f.read())
            for rel in (
                "db/migrations/001_research_fields.sql",
                "db/migrations/009_evidence_items.sql",
                "db/migrations/010_field_resolution.sql",
                "db/migrations/011_v3_fields.sql",
            ):
                with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
                    conn.executescript(f.read())

        docs = [{
            "url": "https://example.com/report",
            "title": "Market report",
            "text": "The AI search market size reached USD 12.5B in 2026 with CAGR 24.3%.",
            "source_type": "report",
        }]
        candidates = extract_field_candidates("market_size_value", docs)
        normalized = [normalize_candidate("market_size_value", c) for c in candidates]
        count = upsert_research_fields(db_path, "DemoCo", normalized)

        self.assertGreaterEqual(count, 1)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT field_key, field_value, value_type, norm_value, currency_code, source_urls "
                "FROM research_fields WHERE company_name='DemoCo'"
            ).fetchone()
        self.assertEqual(row["field_key"], "market_size_value")
        self.assertEqual(row["value_type"], "number")
        self.assertEqual(row["norm_value"], "12.5")
        self.assertEqual(row["currency_code"], "USD")
        self.assertIn("https://example.com/report", row["source_urls"])

    def test_youtube_intel_returns_auditable_fallback_status(self):
        from source_fetchers import extract_youtube_intel

        result = extract_youtube_intel(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            metadata_lookup=lambda url: {"video_id": "dQw4w9WgXcQ", "title": "Demo"},
            subtitle_loader=lambda url: "",
            asr_transcriber=lambda url: "",
            scene_detector=lambda url: [],
        )

        self.assertEqual(result["meta"]["video_id"], "dQw4w9WgXcQ")
        self.assertEqual(result["transcript_status"], "unavailable")
        self.assertIn("metadata", result["attempted_methods"])
        self.assertIn("public_subtitles", result["attempted_methods"])
        self.assertIn("asr", result["attempted_methods"])


if __name__ == "__main__":
    unittest.main()
