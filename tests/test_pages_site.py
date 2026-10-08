"""GitHub Pages publication must be complete, public and reproducible."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from model_catalog.common import BASE, PUBLIC_SITE


class PagesSiteTests(unittest.TestCase):
    def test_public_namespace_uses_the_repository_pages_url(self):
        self.assertEqual(PUBLIC_SITE, "https://brodsmaster.github.io/semantic-web-ai-models/")
        self.assertEqual(BASE, PUBLIC_SITE + "data/aimodels.ttl#")

    def test_site_builder_creates_pages_catalog_licenses_and_rdf_distribution(self):
        from scripts.build_site import build

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            build(output)
            required = [
                "index.html", "models/index.html", "organizations/index.html",
                "ontology/index.html", "sparql/index.html", "dataset/index.html",
                "data/catalog.json", "data/aimodels.ttl", "data/ontology.ttl",
                "data/dataset-metadata.ttl", "data/linked-output.nt",
                "assets/styles.css", "assets/app.js", "LICENSE.txt", "DATA_LICENSE.txt",
            ]
            for relative in required:
                self.assertTrue((output / relative).is_file(), relative)

            catalog = json.loads((output / "data/catalog.json").read_text())
            self.assertEqual(catalog["site"], PUBLIC_SITE)
            self.assertEqual(catalog["stats"]["models"], 481)
            self.assertEqual(catalog["stats"]["external_links"], 14)
            self.assertTrue(catalog["models"])
            self.assertTrue(catalog["organizations"])

            rdf_text = (output / "data/aimodels.ttl").read_text()
            self.assertNotIn("https://example.org/aimodels/", rdf_text)
            self.assertIn(BASE, rdf_text)
            self.assertGreater(len(Graph().parse(data=rdf_text, format="turtle")), 300000)

            metadata = Graph().parse(output / "data/dataset-metadata.ttl", format="turtle")
            self.assertTrue(metadata)


if __name__ == "__main__":
    unittest.main()
