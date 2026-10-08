"""Reviewed company/platform identities, replayed from original source bytes."""
import json
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, urlparse

from .common import BRONZE, RES, ROOT, atomic_write, digest, fetch, now, read_json, uri, write_json, provider_kind


def candidates():
    return read_json(RES / 'wikidata-organization-mappings.json')['entities']


def claim_values(entity, prop):
    return [r.get('mainsnak', {}).get('datavalue', {}).get('value')
            for r in entity.get('claims', {}).get(prop, []) if r.get('rank') != 'deprecated']


def official_match(entity, websites):
    for value in claim_values(entity, 'P856'):
        if not isinstance(value, str):
            continue
        actual = urlparse(value)
        for expected in websites:
            reviewed = urlparse(expected)
            domain = (actual.hostname or '').lower().removeprefix('www.')
            expected_domain = (reviewed.hostname or '').lower().removeprefix('www.')
            path = reviewed.path.rstrip('/')
            if actual.scheme in ('http', 'https') and domain == expected_domain and (
                    not path or actual.path.rstrip('/') == path or actual.path.startswith(path + '/')):
                return value
    return None


def verify_entity(local, candidate, entity):
    reasons = []
    reviewed_locals = {uri('organization', r['key']): r['name'] for r in candidate['locals']}
    if local.get('id') not in reviewed_locals or local.get('name') != reviewed_locals.get(local.get('id')):
        reasons.append('local ID/name differs from reviewed mapping')
    if provider_kind(local.get('id', '')) != candidate['entity_kind']:
        reasons.append('local company/platform kind differs')
    if entity.get('id') != candidate['qid']:
        reasons.append('Wikidata QID differs; redirects must be reviewed explicitly')
    names = {v.get('value') for v in entity.get('labels', {}).values()}
    names.update(a.get('value') for aliases in entity.get('aliases', {}).values() for a in aliases)
    if not names.intersection(candidate['names']):
        reasons.append('Wikidata label/alias differs')
    instance_ids = {v.get('id') for v in claim_values(entity, 'P31') if isinstance(v, dict)}
    if not instance_ids.intersection(candidate['instance_of']):
        reasons.append('reviewed Wikidata instance-of type absent')
    if not official_match(entity, candidate['websites']):
        reasons.append('reviewed official website/domain/path absent')
    return reasons


def snapshot(content, prefix, url):
    path = BRONZE / 'documents' / (prefix + '-' + digest(content) + '.json')
    atomic_write(path, content)
    return {'url': url, 'sha256': digest(content), 'snapshot_file': str(path.relative_to(ROOT)), 'retrieved_at': now()}


def checked_payload(source, expected_url):
    if source['url'] != expected_url:
        raise ValueError('identity source URL differs')
    path = (ROOT / source['snapshot_file']).resolve()
    if not path.is_relative_to((BRONZE / 'documents').resolve()):
        raise ValueError('identity snapshot outside Bronze documents')
    content = path.read_bytes()
    if digest(content) != source['sha256']:
        raise ValueError('identity snapshot SHA-256 mismatch')
    return json.loads(content)


def dbpedia_url(qid):
    query = ('SELECT ?entity WHERE { ?entity <http://www.w3.org/2002/07/owl#sameAs> '
             '<http://www.wikidata.org/entity/' + qid + '> } LIMIT 50')
    return 'https://dbpedia.org/sparql?' + urlencode({'query': query, 'format': 'application/sparql-results+json'})


def collect_links():
    def one(candidate):
        qid = candidate['qid']
        url = 'https://www.wikidata.org/wiki/Special:EntityData/' + qid + '.json'
        record = {'qid': qid}
        try:
            record['source'] = snapshot(fetch(url), 'wikidata-' + qid, url)
            payload = checked_payload(record['source'], url)
            entity = payload.get('entities', {}).get(qid, {})
            local = candidate['locals'][0]
            reasons = verify_entity({'id': uri('organization', local['key']), 'name': local['name']}, candidate, entity)
            if reasons:
                record['warning'] = '; '.join(reasons)
            else:
                try:
                    endpoint = dbpedia_url(qid)
                    record['dbpedia_source'] = snapshot(fetch(endpoint, {'Accept': 'application/sparql-results+json'}),
                                                       'dbpedia-' + qid, endpoint)
                except (RuntimeError, ValueError) as exc:
                    record['dbpedia_warning'] = str(exc)
        except (RuntimeError, ValueError, KeyError) as exc:
            record['warning'] = str(exc)
        print('Identity ' + qid + ': ' + record.get('warning', 'collected'), flush=True)
        return record
    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(one, candidates()))
    write_json(BRONZE / 'external_lookups.json', records)
    return records


def verified_links(tables, records):
    locals_by_id = {r['id']: r for r in tables['organizations']}
    records_by_id = {r['qid']: r for r in records}
    links, decisions = [], []
    for candidate in candidates():
        qid = candidate['qid']
        record = records_by_id.get(qid, {})
        expected_url = 'https://www.wikidata.org/wiki/Special:EntityData/' + qid + '.json'
        try:
            source = record['source']
            entity = checked_payload(source, expected_url).get('entities', {}).get(qid, {})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            decisions.append({'qid': qid, 'status': 'rejected', 'reasons': ['unverifiable source: ' + str(exc)]})
            continue
        targets = [('http://www.wikidata.org/entity/' + qid, source)]
        if record.get('dbpedia_source'):
            try:
                db_source = record['dbpedia_source']
                payload = checked_payload(db_source, dbpedia_url(qid))
                targets.extend((r['entity']['value'], db_source)
                    for r in payload.get('results', {}).get('bindings', [])
                    if r.get('entity', {}).get('type') == 'uri'
                    and r['entity']['value'].startswith('http://dbpedia.org/resource/'))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                decisions.append({'qid': qid, 'status': 'dbpedia_rejected', 'reasons': [str(exc)]})
        for reviewed in candidate['locals']:
            ident = uri('organization', reviewed['key'])
            local = locals_by_id.get(ident)
            reasons = verify_entity(local, candidate, entity) if local else ['local entity absent from current catalog']
            decisions.append({'local_key': reviewed['key'], 'qid': qid, 'entity_kind': candidate['entity_kind'],
                              'status': 'rejected' if reasons else 'accepted', 'reasons': reasons})
            if reasons:
                continue
            for target, evidence in targets:
                reason = 'Reviewed exact local ID/name, Wikidata QID/label/instance-of and official website: ' + official_match(entity, candidate['websites'])
                if target.startswith('http://dbpedia.org/'):
                    reason += '; DBpedia independently publishes owl:sameAs to verified QID'
                links.append({'subject': ident, 'target': target, 'source_url': evidence['url'],
                              'sha256': evidence['sha256'], 'snapshot_file': evidence['snapshot_file'],
                              'retrieved_at': evidence['retrieved_at'], 'reason': reason})
    return links, decisions
