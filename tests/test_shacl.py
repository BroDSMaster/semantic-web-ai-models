"""SHACL catches broken RDF while preserving valid platform hosts and zero prices."""
import sys
import tempfile
import unittest
from pathlib import Path
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, OWL, XSD

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from model_catalog.transform import EX, PROV, SCHEMA


class ShaclTests(unittest.TestCase):
    def setUp(self):
        from model_catalog.shacl import validate_shacl
        self.validate = validate_shacl
        self.graph = Graph().parse(ROOT / 'tests/fixtures/shacl-valid.ttl')
        self.price = URIRef('https://example.test/price')
        self.offering = URIRef('https://example.test/offering')

    def check(self, graph):
        return self.validate(graph, output_dir=None)

    def test_valid_graph_including_azure_and_zero_price(self):
        self.assertTrue(self.check(self.graph)['conforms'])

    def test_external_repository_uri_does_not_require_imported_external_types(self):
        self.assertTrue(self.check(self.graph)['conforms'])
        self.graph.set((URIRef('https://example.test/model'), EX.hasRepository, URIRef('https://evil.test/demo/model')))
        self.assertFalse(self.check(self.graph)['conforms'])

    def test_bad_price_datatype_and_negative_amount_are_rejected(self):
        for amount in [Literal('five'), Literal('-1', datatype=XSD.decimal)]:
            with self.subTest(amount=amount):
                self.graph.set((self.price, EX.priceAmount, amount))
                report = self.check(self.graph)
                self.assertFalse(report['conforms'])
                self.assertTrue(any(r['path'] == str(EX.priceAmount) for r in report['results']))

    def test_missing_or_multiple_models_and_wrong_provider_class(self):
        for fault in ['missing', 'multiple', 'provider']:
            graph = Graph() + self.graph
            if fault == 'missing': graph.remove((self.offering, EX.offersModel, None))
            if fault == 'multiple': graph.add((self.offering, EX.offersModel, URIRef('https://example.test/model2')))
            if fault == 'provider': graph.set((self.offering, EX.hostedBy, URIRef('https://example.test/untyped')))
            with self.subTest(fault=fault):
                self.assertFalse(self.check(graph)['conforms'])

    def test_observation_must_have_exactly_one_literal_or_resource_value(self):
        node = URIRef('https://example.test/observation')
        self.graph.add((node, EX.resourceValue, URIRef('https://example.test/other')))
        self.assertFalse(self.check(self.graph)['conforms'])
        self.graph.remove((node, EX.resourceValue, None))
        self.graph.remove((node, EX.literalValue, None))
        self.assertFalse(self.check(self.graph)['conforms'])

    def test_external_link_requires_evidence_and_matching_sameas(self):
        link = URIRef('https://example.test/link')
        self.graph.remove((URIRef('https://example.test/azure'), OWL.sameAs, None))
        self.assertFalse(self.check(self.graph)['conforms'])
        self.graph = Graph().parse(ROOT / 'tests/fixtures/shacl-valid.ttl')
        self.graph.remove((link, EX.sha256, None))
        self.assertFalse(self.check(self.graph)['conforms'])

    def test_model_sameas_without_evidence_is_rejected(self):
        self.graph.add((URIRef('https://example.test/model'), OWL.sameAs, URIRef('https://example.test/model-external')))
        self.assertFalse(self.check(self.graph)['conforms'])

    def test_provenance_datatypes_and_orphan_prices_are_rejected(self):
        for fault in ['date', 'source', 'orphan', 'score', 'checksum', 'tokens']:
            graph = Graph() + self.graph
            if fault == 'date': graph.set((self.price, EX.observedAt, Literal('yesterday')))
            if fault == 'source': graph.set((self.price, PROV.wasDerivedFrom, URIRef('https://example.test/missing-doc')))
            if fault == 'orphan': graph.remove((self.offering, EX.hasPrice, self.price))
            if fault == 'score': graph.set((URIRef('https://example.test/evaluation'), EX.score, Literal('high')))
            if fault == 'checksum': graph.set((URIRef('https://example.test/document'), EX.sha256, Literal('broken')))
            if fault == 'tokens': graph.add((URIRef('https://example.test/model'), EX.contextLength, Literal('200k')))
            with self.subTest(fault=fault):
                self.assertFalse(self.check(graph)['conforms'])

    def test_reports_are_written_for_nonconformant_graph(self):
        self.graph.remove((self.offering, EX.offersModel, None))
        with tempfile.TemporaryDirectory() as directory:
            report = self.validate(self.graph, output_dir=Path(directory))
            self.assertFalse(report['conforms'])
            self.assertTrue((Path(directory) / 'shacl-report.json').exists())
            rdf = Graph().parse(Path(directory) / 'shacl-report.ttl')
            self.assertTrue(rdf)


if __name__ == '__main__':
    unittest.main()
