"""Offline fixtures are synthetic; they are never part of the published sample."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def fixture():
    person = {"id": "https://openalex.org/A1", "display_name": "Example Author",
              "orcid": "https://orcid.org/0000-0001-0000-0001"}
    topic = {"id": "https://openalex.org/T1", "display_name": "Example AI Topic",
             "subfield": {"id": "https://openalex.org/subfields/1702", "display_name": "Artificial Intelligence"},
             "field": {"id": "https://openalex.org/fields/17", "display_name": "Computer Science"},
             "domain": {"id": "https://openalex.org/domains/3", "display_name": "Physical Sciences"}}
    papers = []
    for i in [1, 2]:
        inst = {"id": f"https://openalex.org/I{i}", "display_name": f"Example Institution {i}",
                "ror": f"https://ror.org/example{i}", "country_code": "VN", "type": "education"}
        papers.append({"id": f"https://openalex.org/W{i}", "display_name": f"Example paper {i}",
                       "publication_year": 2024, "publication_date": "2024-01-02", "cited_by_count": 5,
                       "doi": None, "type": "article", "open_access": {"is_oa": True},
                       "authorships": [{"author": person, "author_position": "first",
                                       "is_corresponding": False, "institutions": [inst]}],
                       "topics": [dict(topic, score=0.9)], "primary_topic": topic,
                       "primary_location": {"source": {"id": "https://openalex.org/S1", "display_name": "Example Journal", "type": "journal"}},
                       "referenced_works": ["https://openalex.org/W2"] if i == 1 else []})
    sources = [{"id": "https://openalex.org/S1", "display_name": "Example Journal", "type": "journal",
                "host_organization": "https://openalex.org/P1", "host_organization_name": "Example Publisher"}]
    return papers, sources


class PipelineTests(unittest.TestCase):
    def test_pipeline_modules_exist(self):
        for name in ("common", "clean_data", "transform", "link_entities", "validate", "ask", "collect_data"):
            with self.subTest(name=name):
                self.assertIsNotNone(importlib.util.find_spec(name), f"Missing pipeline stage: {name}")

    def modules(self):
        if importlib.util.find_spec("clean_data") is None:
            self.skipTest("Pipeline is not implemented yet")
        import clean_data, transform, common
        return clean_data, transform, common

    def test_deduplicates_and_preserves_contextual_affiliations(self):
        clean, transform, common = self.modules()
        from rdflib import RDF, XSD, Literal
        papers, sources = fixture()
        tables, report = clean.normalize(papers + papers[:1], sources, [])
        self.assertEqual(len(tables["papers"]), 2)
        self.assertEqual(len(tables["people"]), 1)
        self.assertEqual(len(tables["authorships"]), 2)
        self.assertEqual(report["duplicate_works"], 1)
        graph = transform.build_graph(tables)
        ex = common.EX
        author = common.resource("person", "https://openalex.org/A1")
        self.assertEqual(len(list(graph.subjects(ex.authorPerson, author))), 2)
        self.assertEqual(len(list(graph.objects(author, ex.affiliatedInstitution))), 0)
        for i in [1, 2]:
            paper = common.resource("paper", f"https://openalex.org/W{i}")
            role = next(graph.objects(paper, ex.hasAuthorship))
            self.assertEqual(set(graph.objects(role, ex.affiliatedInstitution)),
                             {common.resource("institution", f"https://openalex.org/I{i}")})
            self.assertIn((paper, ex.publicationYear, Literal(2024, datatype=XSD.gYear)), graph)
        self.assertEqual(len(set(graph.objects(None, RDF.type))), 10)

    def test_missing_author_id_never_creates_an_anonymous_person(self):
        clean, transform, common = self.modules()
        papers, sources = fixture()
        papers[0]["authorships"].append({"author": {"display_name": "Unknown"}, "institutions": []})
        tables, report = clean.normalize(papers, sources, [])
        self.assertEqual(len(tables["people"]), 1)
        self.assertEqual(report["skipped_authors_without_id"], 1)

    def test_proceedings_collection_is_not_exported_as_a_research_paper(self):
        clean, _, _ = self.modules()
        papers, sources = fixture()
        collection = dict(papers[0], id="https://openalex.org/W3", type="paratext",
                          display_name="Proceedings collection", is_paratext=True)
        tables, report = clean.normalize(papers + [collection], sources, [])
        self.assertEqual(len(tables["papers"]), 2)
        self.assertEqual(report.get("skipped_out_of_scope_works"), 1)

    def test_dbpedia_link_requires_exact_wikidata_identity(self):
        self.modules()
        import link_entities
        bindings = [{"entity": {"value": "http://dbpedia.org/resource/Example_University"},
                     "wd": {"value": "http://www.wikidata.org/entity/Q1"}},
                    {"entity": {"value": "http://dbpedia.org/resource/Wrong_University"},
                     "wd": {"value": "http://www.wikidata.org/entity/Q2"}}]
        mapping = link_entities.exact_dbpedia_links(bindings, {"Q1"})
        self.assertEqual(mapping, {"Q1": ["http://dbpedia.org/resource/Example_University"]})

    def test_wikidata_uses_its_supported_json_format(self):
        self.modules()
        import link_entities
        self.assertEqual(getattr(link_entities, "SPARQL_FORMATS", {}).get("Wikidata"), "json")

    def test_non_json_endpoint_response_is_an_actionable_network_error(self):
        _, _, common = self.modules()
        import io
        from unittest.mock import patch
        with patch.object(common, "urlopen", return_value=io.BytesIO(b"<html>Not JSON</html>")):
            with self.assertRaisesRegex(RuntimeError, "Non-JSON"):
                common.fetch_json("https://example.org/sparql")

    def test_sparql_request_can_negotiate_the_correct_result_media_type(self):
        _, _, common = self.modules()
        import io
        from unittest.mock import patch
        with patch.object(common, "urlopen", return_value=io.BytesIO(b'{"results":{"bindings":[]}}')) as boundary:
            common.fetch_json("https://example.org/sparql", accept="application/sparql-results+json")
            request = boundary.call_args.args[0]
            self.assertEqual(request.get_header("Accept"), "application/sparql-results+json")

    def test_collection_of_150_papers_does_not_repeat_the_first_page(self):
        _, _, common = self.modules()
        import collect_data
        import contextlib
        import io
        from unittest.mock import patch
        def endpoint(url, params=None, **kwargs):
            size, page = params["per_page"], params["page"]
            start = (page - 1) * size
            return {"results": [{"id": f"https://openalex.org/W{index}"}
                                 for index in range(start + 1, start + size + 1)]}
        with tempfile.TemporaryDirectory() as tmp, patch.object(collect_data, "BRONZE", Path(tmp)), \
             patch.object(collect_data, "fetch_json", side_effect=endpoint), contextlib.redirect_stdout(io.StringIO()):
            collect_data.collect(limit=150, enrich_limit=0)
            works = common.read_json(Path(tmp) / "openalex_works.json")
            self.assertEqual(len({work["id"] for work in works}), 150)

    def test_full_pipeline_roundtrip_and_cqs(self):
        clean, transform, common = self.modules()
        import validate
        from rdflib import Graph
        papers, sources = fixture()
        tables, _ = clean.normalize(papers, sources, [])
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            common.write_tables(p, tables)
            graph = transform.build_graph(common.read_tables(p))
            output = p / "example.ttl"
            graph.serialize(output, format="turtle")
            loaded = Graph().parse(output)
            self.assertEqual(len(loaded), len(graph))
            loaded.parse(ROOT / "res" / "ontology.ttl")
            for query in sorted((ROOT / "queries").glob("cq*.rq")):
                self.assertIsNotNone(list(loaded.query(query.read_text())))
            results = {q.name: list(loaded.query(q.read_text())) for q in (ROOT / "queries").glob("cq*.rq")}
            self.assertEqual(len(results["cq01_top_papers.rq"]), 2)
            self.assertEqual({str(row[1]) for row in results["cq02_authorship_affiliations.rq"]},
                             {"Example paper 1", "Example paper 2"})
            self.assertEqual([int(row[2]) for row in results["cq03_institution_productivity.rq"]], [1, 1])
            self.assertEqual(int(results["cq04_topic_hierarchy.rq"][0][-1]), 2)
            self.assertEqual(str(results["cq05_sources_publishers.rq"][0][3]), "Example Publisher")
            self.assertEqual(int(results["cq06_open_access_by_year.rq"][0][-1]), 2)
            self.assertEqual(results["cq07_external_links.rq"], [])
            self.assertEqual(str(results["cq08_references.rq"][0][-1]), "Example paper 2")
            self.assertEqual(results["cq09_collaboration.rq"], [])
            self.assertEqual(len(results["cq10_identifiers_provenance.rq"]), 2)
            report = validate.check_graph(loaded, reasoning=True)
            self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
