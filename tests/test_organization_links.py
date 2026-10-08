"""OpenAlex organization links require exact, replayable identity evidence."""
import json
import inspect
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from rdflib import Graph, URIRef
from rdflib.namespace import OWL

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from model_catalog import organization_links
except ImportError:
    organization_links = None

from model_catalog.common import digest, uri


class OpenAlexOrganizationLinkTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "local_key": "developer:openai",
            "local_name": "OpenAI",
            "openalex_id": "I4210161460",
            "display_name": "OpenAI (United States)",
            "homepage_domains": ["openai.com"],
            "ror": "https://ror.org/05wx9n238",
            "type": "company"
        }
        self.organization = {"id": uri("organization", "developer:openai"), "name": "OpenAI"}
        self.entity = {
            "id": "https://openalex.org/I4210161460",
            "display_name": "OpenAI (United States)",
            "ror": "https://ror.org/05wx9n238",
            "homepage_url": "https://openai.com/",
            "type": "company",
            "ids": {"openalex": "https://openalex.org/I4210161460", "ror": "https://ror.org/05wx9n238", "wikidata": None}
        }

    def test_exact_name_id_homepage_ror_and_type_are_required(self):
        self.assertIsNotNone(organization_links, "OpenAlex organization linking is not implemented")
        self.assertEqual(organization_links.verify_institution(self.organization, self.candidate, self.entity), [])
        changes = {
            "local name": ({**self.organization, "name": "Open AI"}, self.candidate, self.entity),
            "OpenAlex ID": (self.organization, self.candidate, {**self.entity, "id": "https://openalex.org/I999"}),
            "display name": (self.organization, self.candidate, {**self.entity, "display_name": "OpenAI Lab"}),
            "homepage": (self.organization, self.candidate, {**self.entity, "homepage_url": "https://example.com"}),
            "ROR": (self.organization, self.candidate, {**self.entity, "ror": "https://ror.org/wrong"}),
            "type": (self.organization, self.candidate, {**self.entity, "type": "education"})
        }
        for field, arguments in changes.items():
            with self.subTest(field=field):
                self.assertTrue(organization_links.verify_institution(*arguments))

    def test_verified_link_is_rebuilt_from_checksum_bound_source(self):
        self.assertIsNotNone(organization_links, "OpenAlex organization linking is not implemented")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bronze, res = root / "bronze", root / "res"
            (bronze / "documents").mkdir(parents=True)
            res.mkdir()
            (res / "openalex-organization-mappings.json").write_text(
                json.dumps({"organizations": [self.candidate]}), encoding="utf-8")
            content = json.dumps(self.entity).encode()
            evidence = bronze / "documents/openalex.json"
            evidence.write_bytes(content)
            source = {"url": "https://api.openalex.org/institutions/I4210161460",
                      "sha256": digest(content), "snapshot_file": "bronze/documents/openalex.json",
                      "retrieved_at": "2026-10-08T00:00:00Z"}
            record = {"local_key": "developer:openai", "openalex_id": "I4210161460", "source": source}
            tables = {"organizations": [self.organization]}
            with patch.object(organization_links, "ROOT", root), patch.object(organization_links, "BRONZE", bronze), patch.object(organization_links, "RES", res):
                links, decisions = organization_links.verified_openalex_links(tables, [record])
                self.assertEqual([(row["subject"], row["target"]) for row in links], [
                    (self.organization["id"], "https://openalex.org/I4210161460")])
                self.assertEqual(decisions[0]["status"], "accepted")
                record["source"] = {**source, "url": "https://api.openalex.org/institutions/I999"}
                self.assertEqual(organization_links.verified_openalex_links(tables, [record])[0], [])

    def test_link_export_writes_same_as_and_evidence_for_verified_openalex_identity(self):
        self.assertIsNotNone(organization_links, "OpenAlex organization linking is not implemented")
        from model_catalog import link
        self.assertEqual(list(inspect.signature(link.export_links).parameters),
                         ["lookups", "openalex_lookups"],
                         "link export must only accept organization identity sources")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bronze, res = root / "bronze", root / "res"
            (bronze / "documents").mkdir(parents=True)
            res.mkdir()
            (res / "openalex-organization-mappings.json").write_text(
                json.dumps({"organizations": [self.candidate]}), encoding="utf-8")
            content = json.dumps(self.entity).encode()
            path = bronze / "documents/openalex.json"
            path.write_bytes(content)
            record = {"local_key": "developer:openai", "openalex_id": "I4210161460", "source": {
                "url": "https://api.openalex.org/institutions/I4210161460", "sha256": digest(content),
                "snapshot_file": "bronze/documents/openalex.json", "retrieved_at": "2026-10-08T00:00:00Z"}}
            tables = {"organizations": [self.organization], "models": []}
            with patch.object(link, "RES", res), patch.object(link, "read_tables", return_value=tables), \
                    patch.object(link, "write_tables"), patch.object(organization_links, "ROOT", root), \
                    patch.object(organization_links, "BRONZE", bronze), patch.object(organization_links, "RES", res):
                link.export_links([], [record])
            graph = Graph().parse(res / "linked_output.nt", format="nt")
            subject = URIRef(self.organization["id"])
            target = URIRef("https://openalex.org/I4210161460")
            self.assertIn((subject, OWL.sameAs, target), graph)
            self.assertTrue(any(graph.triples((None, link.EX.linkTarget, target))))


if __name__ == "__main__":
    unittest.main()
