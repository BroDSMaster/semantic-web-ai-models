"""Reviewed identities must be replayable and distinguish platforms from companies."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from model_catalog.common import digest, uri
from model_catalog import transform
from rdflib import URIRef
from rdflib.namespace import RDF


class WikidataLinksTests(unittest.TestCase):
    def setUp(self):
        from model_catalog import wikidata_links
        self.module = wikidata_links
        self.candidate = {'qid': 'Q725967', 'names': ['Azure'], 'entity_kind': 'service',
                          'instance_of': ['Q241317'], 'websites': ['https://azure.microsoft.com/'],
                          'locals': [{'key': 'host:Azure', 'name': 'Azure'}]}
        self.local = {'id': uri('organization', 'host:Azure'), 'name': 'Azure'}
        self.entity = {'id': 'Q725967', 'labels': {'en': {'value': 'Azure'}}, 'claims': {
            'P31': [{'mainsnak': {'datavalue': {'value': {'id': 'Q241317'}}}}],
            'P856': [{'mainsnak': {'datavalue': {'value': 'https://azure.microsoft.com/'}}}]}}

    def test_correct_platform_identity_is_accepted(self):
        self.assertEqual(self.module.verify_entity(self.local, self.candidate, self.entity), [])

    def test_wrong_id_name_kind_domain_or_local_name_is_rejected(self):
        for field in ['id', 'name', 'kind', 'domain', 'local']:
            entity, local = copy.deepcopy(self.entity), dict(self.local)
            if field == 'id': entity['id'] = 'Q2283'
            if field == 'name': entity['labels']['en']['value'] = 'Microsoft'
            if field == 'kind': entity['claims']['P31'][0]['mainsnak']['datavalue']['value']['id'] = 'Q4830453'
            if field == 'domain': entity['claims']['P856'][0]['mainsnak']['datavalue']['value'] = 'https://azure.microsoft.com.evil.test/'
            if field == 'local': local['name'] = 'Microsoft'
            with self.subTest(field=field):
                self.assertTrue(self.module.verify_entity(local, self.candidate, entity))

    def test_shared_domain_requires_reviewed_product_path(self):
        candidate = {**self.candidate, 'websites': ['https://aws.amazon.com/bedrock/']}
        entity = copy.deepcopy(self.entity)
        entity['claims']['P856'][0]['mainsnak']['datavalue']['value'] = 'https://aws.amazon.com/'
        self.assertTrue(self.module.verify_entity(self.local, candidate, entity))

    def test_tampered_or_wrong_source_cannot_create_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bronze = root / 'src/data/bronze'
            (bronze / 'documents').mkdir(parents=True)
            content = json.dumps({'entities': {'Q725967': self.entity}}).encode()
            path = bronze / 'documents/wikidata.json'
            path.write_bytes(content)
            source = {'url': 'https://www.wikidata.org/wiki/Special:EntityData/Q725967.json',
                      'sha256': digest(content), 'snapshot_file': str(path.relative_to(root)),
                      'retrieved_at': '2026-10-08T00:00:00Z'}
            record = {'qid': 'Q725967', 'source': source}
            with patch.object(self.module, 'ROOT', root), patch.object(self.module, 'BRONZE', bronze), \
                    patch.object(self.module, 'candidates', return_value=[self.candidate]):
                rows, decisions = self.module.verified_links({'organizations': [self.local]}, [record])
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['target'], 'http://www.wikidata.org/entity/Q725967')
                path.write_bytes(content + b' ')
                self.assertEqual(self.module.verified_links({'organizations': [self.local]}, [record])[0], [])

    def test_azure_is_service_and_hostedby_does_not_infer_organization(self):
        from model_catalog.normalize import normalize
        from owlrl import DeductiveClosure, OWLRL_Semantics
        model = {'id': 'anthropic/test', 'name': 'Test'}
        tables = normalize({'data': [model]}, {'anthropic/test': {'data': {'endpoints': [
            {'provider_name': 'Azure', 'name': 'Azure', 'tag': 'azure'}]}}},
            {'retrieved_at': '2026-10-08T00:00:00Z', 'catalog_url': 'https://openrouter.ai/api/v1/models'})
        graph = transform.build_graph(tables)
        azure = URIRef(self.local['id'])
        self.assertIn((azure, RDF.type, transform.SCHEMA.Service), graph)
        graph.parse(Path(__file__).resolve().parents[1] / 'res/ontology.ttl')
        DeductiveClosure(OWLRL_Semantics).expand(graph)
        self.assertNotIn((azure, RDF.type, transform.EX.Organization), graph)


if __name__ == '__main__':
    unittest.main()
