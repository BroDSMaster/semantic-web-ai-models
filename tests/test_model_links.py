"""Reject ambiguous identities even when their names resemble an approved model."""
import sys
import unittest
import tempfile
import json
from urllib.parse import urlencode
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from model_catalog.model_links import verify_identity, checked_payload, verified_model_links
from model_catalog.common import digest


def claim(value):
    return {"mainsnak": {"datavalue": {"value": value}}}


class ModelIdentityTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {"source_id": "openai/gpt-4", "label": "GPT-4",
                          "qid": "Q116709136", "developer_qid": "Q21708200",
                          "developer_id": "developer:openai",
                          "official_urls": ["https://openai.com/gpt-4"],
                          "type_qid": "Q131406845"}
        self.model = {"id": "https://example.org/aimodels/resource/model/openrouter%3Aopenai%2Fgpt-4", "source_id": "openai/gpt-4", "name": "OpenAI: GPT-4",
                      "developer_id": "https://example.org/aimodels/resource/organization/developer%3Aopenai"}
        self.entity = {"id": "Q116709136", "labels": {"en": {"value": "GPT-4"}},
                       "claims": {"P178": [claim({"id": "Q21708200"})],
                                  "P31": [claim({"id": "Q131406845"})],
                                  "P856": [claim("https://openai.com/gpt-4")]}}

    def test_exact_model_with_developer_type_and_official_url_is_accepted(self):
        self.assertEqual(verify_identity(self.model, self.candidate, self.entity), [])

    def test_wrong_developer_is_rejected(self):
        self.entity["claims"]["P178"] = [claim({"id": "Q999"})]
        self.assertIn("developer", " ".join(verify_identity(self.model, self.candidate, self.entity)))

    def test_family_entity_is_rejected(self):
        self.entity["labels"]["en"]["value"] = "GPT"
        self.assertTrue(verify_identity(self.model, self.candidate, self.entity))

    def test_same_domain_but_wrong_official_model_page_is_rejected(self):
        self.entity["claims"]["P856"] = [claim("https://openai.com/gpt-3")]
        self.assertTrue(verify_identity(self.model, self.candidate, self.entity))

    def test_batch_free_snapshot_and_other_versions_are_rejected(self):
        for slug in ["openai/gpt-4:batch", "openai/gpt-4:free", "openai/gpt-4-0314", "openai/gpt-4-turbo"]:
            with self.subTest(slug=slug):
                self.model["source_id"] = slug
                self.assertTrue(verify_identity(self.model, self.candidate, self.entity))

    def test_wrong_local_developer_is_rejected(self):
        self.model["developer_id"] = "https://example.org/aimodels/resource/organization/developer%3Aanthropic"
        self.assertTrue(verify_identity(self.model, self.candidate, self.entity))

    def test_missing_type_or_website_is_rejected(self):
        for prop in ("P31", "P856"):
            entity = {**self.entity, "claims": {k: v for k, v in self.entity["claims"].items() if k != prop}}
            self.assertTrue(verify_identity(self.model, self.candidate, entity))

    def test_wrong_local_uri_is_rejected(self):
        self.model["id"] = "https://example.org/aimodels/resource/model/wrong"
        self.assertTrue(verify_identity(self.model, self.candidate, self.entity))

    def test_tampered_snapshot_cannot_be_used_as_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "bronze/documents"
            folder.mkdir(parents=True)
            path = folder / "lookup.json"
            original = b'{"verified": true}'
            path.write_bytes(original)
            source = {"snapshot_file": "bronze/documents/lookup.json", "sha256": digest(original)}
            with patch("model_catalog.model_links.ROOT", root), patch("model_catalog.model_links.BRONZE", root / "bronze"):
                self.assertEqual(checked_payload(source), {"verified": True})
                path.write_bytes(b'{"verified": false}')
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    checked_payload(source)

    def test_evidence_path_outside_documents_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            checked_payload({"snapshot_file": "README.md", "sha256": "irrelevant"})

    def test_export_replays_catalog_and_target_evidence_instead_of_trusting_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bronze = root / "bronze"
            (bronze / "documents").mkdir(parents=True)
            res = root / "res"
            res.mkdir()
            (res / "model-identity-mappings.json").write_text(json.dumps({"models": [self.candidate]}))
            def source(name, payload, url):
                content = json.dumps(payload).encode()
                path = bronze / "documents" / name
                path.write_bytes(content)
                return {"snapshot_file": str(path.relative_to(root)), "sha256": digest(content),
                        "url": url, "retrieved_at": "2026-10-08T00:00:00Z"}
            catalog = source("catalog.json", {"data": [{"id": "openai/gpt-4", "name": "OpenAI: GPT-4"}]}, "https://openrouter.ai/api/v1/models")
            (bronze / "manifest.json").write_text(json.dumps({"catalog_url": catalog["url"], "documents": [
                {"url": catalog["url"], "sha256": catalog["sha256"], "retrieved_at": catalog["retrieved_at"], "file": "documents/catalog.json"}]}))
            wd = source("wikidata.json", {"entities": {"Q116709136": self.entity}}, "https://www.wikidata.org/wiki/Special:EntityData/Q116709136.json")
            record = {"source_id": "openai/gpt-4", "qid": "Q116709136", "wikidata_source": wd}
            with patch("model_catalog.model_links.ROOT", root), patch("model_catalog.model_links.BRONZE", bronze), patch("model_catalog.model_links.RES", res):
                links, decisions = verified_model_links({"models": [self.model]}, [record])
                self.assertEqual([r["target"] for r in links], ["http://www.wikidata.org/entity/Q116709136"])
                self.assertEqual(decisions[0]["status"], "accepted")
                query = "SELECT ?entity WHERE { ?entity <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/Q116709136> } LIMIT 20"
                dburl = "https://dbpedia.org/sparql?" + urlencode({"query": query, "format": "application/sparql-results+json"})
                db = source("dbpedia.json", {"results": {"bindings": [{"entity": {"type": "uri", "value": "http://dbpedia.org/resource/GPT-4"}}]}}, dburl)
                record["dbpedia_source"] = db
                self.assertEqual(len(verified_model_links({"models": [self.model]}, [record])[0]), 2)
                record["dbpedia_source"] = {**db, "url": dburl.replace("Q116709136", "Q999")}
                links, decisions = verified_model_links({"models": [self.model]}, [record])
                self.assertEqual(len(links), 1)
                self.assertIn("query", decisions[0]["dbpedia_warning"])
                record.pop("dbpedia_source")
                # A cache flag cannot override a changed official identity claim.
                bad = {**self.entity, "claims": {**self.entity["claims"], "P178": [claim({"id": "Q999"})]}}
                record["wikidata_source"] = source("wikidata-wrong.json", {"entities": {"Q116709136": bad}}, wd["url"])
                record["verified"] = True
                self.assertEqual(verified_model_links({"models": [self.model]}, [record])[0], [])
                record["wikidata_source"] = wd
                changed_model = {**self.model, "name": "OpenAI: GPT-4 Turbo"}
                self.assertEqual(verified_model_links({"models": [changed_model]}, [record])[0], [])

    def test_hugging_face_metadata_replays_original_bytes_and_exact_api_id(self):
        from model_catalog.model_cards import verified_cards
        with tempfile.TemporaryDirectory() as directory:
            bronze = Path(directory)
            (bronze / "documents").mkdir()
            path = bronze / "documents/hf.json"
            content = b'{"id": "meta-llama/Test"}'
            path.write_bytes(content)
            doc = {"kind": "model_card", "file": "documents/hf.json", "sha256": digest(content),
                   "url": "https://huggingface.co/api/models/meta-llama/Test"}
            with patch("model_catalog.model_cards.BRONZE", bronze):
                self.assertIn("meta-llama/Test", verified_cards({"documents": [doc]}))
                wrong_url = {**doc, "url": "https://huggingface.co/api/models/meta-llama/Wrong"}
                with self.assertRaisesRegex(ValueError, "ID differs"):
                    verified_cards({"documents": [wrong_url]})
                path.write_bytes(b'{"id": "meta-llama/Wrong"}')
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    verified_cards({"documents": [doc]})
