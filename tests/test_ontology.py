"""Regression checks for the ontology's logical class axioms."""
import unittest
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import OWL


ROOT = Path(__file__).resolve().parents[1]
EX = Namespace("https://brodsmaster.github.io/semantic-web-ai-models/data/aimodels.ttl#")


class OntologyTests(unittest.TestCase):
    def test_incompatible_entity_kinds_are_disjoint(self):
        graph = Graph().parse(ROOT / "res/ontology.ttl", format="turtle")
        asserted_pairs = {
            frozenset((subject, target))
            for subject, target in graph.subject_objects(OWL.disjointWith)
        }
        expected_pairs = {
            frozenset((EX.AIModel, EX.Organization)),
            frozenset((EX.AIModel, EX.PriceSpecification)),
            frozenset((EX.Evaluation, EX.Benchmark)),
        }
        self.assertTrue(
            expected_pairs.issubset(asserted_pairs),
            f"Missing disjoint class axioms: {expected_pairs - asserted_pairs}",
        )


if __name__ == "__main__":
    unittest.main()
