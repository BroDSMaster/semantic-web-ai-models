"""Regression checks for sourced model offerings, pricing and evaluations."""
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class CatalogTests(unittest.TestCase):
    def normalize(self, model=None, endpoints=None):
        from model_catalog.normalize import normalize
        base = {"id": "anthropic/claude-opus-test", "name": "Claude Opus Test",
                "description": "Provider claim", "context_length": 200000,
                "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
                "supported_parameters": ["tools"], "pricing": {"prompt": "0", "completion": None}}
        base.update(model or {})
        return normalize({"data": [base]}, endpoints or {},
                         {"retrieved_at": "2026-10-05T00:00:00+00:00", "catalog_url": "https://openrouter.ai/api/v1/models"})

    def test_zero_is_a_price_but_null_is_not(self):
        tables = self.normalize()
        self.assertEqual(len(tables["prices"]), 1)
        self.assertEqual(tables["prices"][0]["amount"], "0")
        self.assertEqual(tables["prices"][0]["unit"], "million_tokens")

    def test_price_decimal_precision_and_non_token_units(self):
        tables = self.normalize({"pricing": {"prompt": "0.000000123456789", "request": "0.01"}})
        by_kind = {p["category"]: p for p in tables["prices"]}
        self.assertEqual(by_kind["prompt"]["amount"], "0.123456789")
        self.assertEqual(by_kind["request"]["unit"], "request")
        self.assertEqual(by_kind["request"]["amount"], "0.01")

    def test_provider_is_host_not_model_developer(self):
        tables = self.normalize(endpoints={"anthropic/claude-opus-test": {"data": {
            "endpoints": [{"name": "Azure | opus", "tag": "azure/global", "provider_name": "Azure",
                           "context_length": 100000, "pricing": {"prompt": "0.000005"}}]}}})
        self.assertEqual(len(tables["offerings"]), 2)
        endpoint = next(o for o in tables["offerings"] if o["kind"] == "openrouter_endpoint")
        self.assertEqual(endpoint["provider_name"], "Azure")
        self.assertEqual(tables["models"][0]["developer_name"], "Anthropic")
        self.assertEqual(endpoint["context_length"], 100000)

    def test_family_supports_claude_query_and_preserves_variant(self):
        regular = self.normalize()
        batch = self.normalize({"id": "anthropic/claude-opus-test:batch"})
        self.assertEqual(regular["models"][0]["family_name"], "Claude")
        self.assertNotEqual(regular["models"][0]["id"], batch["models"][0]["id"])
        self.assertEqual(batch["offerings"][0]["mode"], "batch")

    def test_catalog_created_is_not_release_date(self):
        tables = self.normalize({"created": 1770219050})
        self.assertTrue(tables["models"][0]["catalog_created"])
        self.assertFalse(tables["models"][0].get("release_date"))

    def test_benchmark_zero_and_scale_keep_provenance(self):
        tables = self.normalize({"benchmarks": {"artificial_analysis": {"intelligence_index": 0, "coding_index": None}}})
        self.assertEqual(len(tables["evaluations"]), 1)
        self.assertEqual(tables["evaluations"][0]["score"], "0")
        self.assertEqual(tables["evaluations"][0]["source_url"], "https://openrouter.ai/api/v1/models")

    def test_invalid_catalog_cannot_replace_snapshot(self):
        from model_catalog.collect import validate_catalog
        for payload in ({"data": []}, {"data": {}}, {"data": [{"name": "missing ID"}]}):
            with self.assertRaises(ValueError):
                validate_catalog(payload)

    def test_endpoint_uses_variant_id_not_paid_canonical_slug(self):
        from model_catalog.collect import endpoint_url
        url = endpoint_url({"id": "google/gemma-test:free", "links": {"details": "/api/v1/models/google/gemma-test/endpoints"}})
        self.assertIn("gemma-test%3Afree/endpoints", url)

    def test_opus_query_returns_sourced_provider_prices(self):
        from model_catalog.transform import build_graph
        tables = self.normalize(endpoints={"anthropic/claude-opus-test": {"data": {
            "endpoints": [{"name": "Azure | opus", "tag": "azure/global", "provider_name": "Azure",
                           "pricing": {"prompt": "0.000005", "completion": "0.000025"}}]}}})
        graph = build_graph(tables)
        query = (Path(__file__).resolve().parents[1] / "queries/models/opus_providers_prices.rq").read_text()
        result = list(graph.query(query))
        azure = [row for row in result if str(row.provider) == "Azure"]
        self.assertEqual({(str(row.category), str(row.usdPerMillionTokens)) for row in azure},
                         {("prompt", "5"), ("completion", "25")})
        self.assertTrue(all(str(row.source).startswith("https://openrouter.ai/") for row in azure))

    def test_price_rdf_preserves_literal_decimal(self):
        from model_catalog.transform import build_graph, EX
        from rdflib import Literal
        from rdflib.namespace import XSD
        graph = build_graph(self.normalize({"pricing": {"prompt": "0.000000123456789"}}))
        self.assertIn(Literal("0.123456789", datatype=XSD.decimal), list(graph.objects(None, EX.priceAmount)))

    def test_long_context_price_override_is_not_lost(self):
        tables = self.normalize({"pricing": {"prompt": "0.000002", "overrides": [
            {"min_prompt_tokens": 272000, "prompt": "0.000004"}]}})
        self.assertEqual(len(tables["prices"]), 2)
        override = next(p for p in tables["prices"] if p["tier"] == "override")
        self.assertEqual(override["amount"], "4")
        self.assertEqual(override["min_prompt_tokens"], 272000)

    def test_discount_applies_to_base_and_override_prices(self):
        tables = self.normalize({"pricing": {"prompt": "0.000005", "discount": "0.2", "overrides": [
            {"min_prompt_tokens": 100000, "prompt": "0.000010"}]}})
        self.assertEqual({p["tier"]: p["amount"] for p in tables["prices"]}, {"base": "4", "override": "8"})
        self.assertTrue(all(p["discount"] == "0.2" for p in tables["prices"]))
        free = self.normalize({"pricing": {"prompt": "0.000005", "discount": "1"}})
        self.assertEqual(free["prices"][0]["amount"], "0")
        undiscounted = self.normalize({"pricing": {"prompt": "0.000005", "discount": None}})
        self.assertEqual(undiscounted["prices"][0]["amount"], "5")
        surcharge = self.normalize({"pricing": {"prompt": "0.000005", "discount": "-0.2"}})
        self.assertEqual(surcharge["prices"][0]["amount"], "6")
        with self.assertRaises(ValueError):
            self.normalize({"pricing": {"prompt": "0.000005", "discount": "1.2"}})

    def test_endpoint_schema_rejects_malformed_root_and_rows(self):
        from model_catalog.collect import validate_endpoints
        for payload in (None, [], {"data": {"endpoints": [None]}}, {"data": {"endpoints": [42]}}):
            with self.assertRaises(ValueError):
                validate_endpoints(payload)

    def test_changed_official_page_does_not_inherit_old_qualifiers(self):
        from model_catalog.official_sources import extract_official
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "source.html").write_text("<p>1,050,000 context window 128,000 max output tokens Text tokens Per 1M tokens Input $2.00 Cached input $0.20 Output $10.00</p>")
            manifest = {"documents": [{"id": "openai-sol", "file": "source.html", "url": "https://example.org/source", "sha256": "new-snapshot"}]}
            with patch("model_catalog.official_sources.BRONZE", Path(directory)):
                facts, warnings = extract_official(manifest)
            self.assertEqual(len(facts), 1)
            self.assertNotIn("2026-11-21", facts[0]["conditions"])
            self.assertNotIn("272", facts[0]["conditions"])
            self.assertNotIn("description", facts[0]["facts"])

    def test_distinct_endpoint_configurations_do_not_merge_by_tag(self):
        rows = [{"provider_name": "Baseten", "tag": "baseten/fp8", "name": "Baseten", "supported_parameters": params,
                 "pricing": {"prompt": "0.000001"}} for params in (["tools"], ["tools", "temperature"])]
        tables = self.normalize(endpoints={"anthropic/claude-opus-test": {"data": {"endpoints": rows}}})
        self.assertEqual(len(tables["offerings"]), 3)

    def test_pagination_deduplicates_ids_and_preserves_response_bytes(self):
        import json
        from model_catalog.collect import fetch_catalog
        from model_catalog.common import digest
        pages = [json.dumps({"data": [{"id": "x/a"}], "links": {"next": "?cursor=two"}}).encode(),
                 json.dumps({"data": [{"id": "x/a"}, {"id": "x/b"}]}).encode()]
        def fetcher(url):
            return pages[1] if "cursor=two" in url else pages[0]
        with tempfile.TemporaryDirectory() as directory:
            with patch("model_catalog.collect.BRONZE", Path(directory)):
                payload, documents = fetch_catalog(fetcher)
            self.assertEqual(len(payload["data"]), 2)
            for document in documents:
                self.assertEqual(digest(Path(directory, document["file"]).read_bytes()), document["sha256"])

    def test_publisher_card_adds_license_and_parameter_count_with_source(self):
        from model_catalog.normalize import normalize
        url = "https://huggingface.co/api/models/meta-llama/Test"
        tables = normalize({"data": [{"id": "meta-llama/test", "name": "Test", "hugging_face_id": "meta-llama/Test"}]}, {},
                           {"retrieved_at": "2026-10-05T00:00:00Z", "catalog_url": "https://openrouter.ai/api/v1/models",
                            "documents": [{"url": url, "kind": "model_card", "sha256": "example", "retrieved_at": "2026-10-05T00:00:00Z"}]},
                           model_cards={"meta-llama/Test": {"safetensors": {"total": 70000000000}, "cardData": {"license": "llama3.3"}}})
        facts = {row["predicate"]: row for row in tables["observations"]}
        self.assertEqual(facts["parameterCount"]["value"], "70000000000")
        self.assertEqual(facts["license"]["value"], "llama3.3")
        doc = next(d for d in tables["documents"] if d["id"] == facts["license"]["document_id"])
        self.assertEqual(doc["url"], url)


if __name__ == "__main__":
    unittest.main()
