"""Verify organization identities by Wikidata official websites and DBpedia sameAs."""
import argparse
import json
from urllib.parse import urlencode, urlparse

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, OWL

from .common import BASE, BRONZE, RES, digest, fetch, now, read_json, read_tables, uri, write_json, write_tables

# Reviewed candidate identifiers; an official-site match is still mandatory.
CANDIDATES = {
    "developer:anthropic": ("Q116758847", {"anthropic.com"}),
    "developer:google": ("Q95", {"google.com"}),
    "developer:meta-llama": ("Q380", {"meta.com", "facebook.com"}),
    "developer:qwen": ("Q1359568", {"alibabagroup.com", "alibaba.com"}),
}
EX = Namespace(BASE)
PROV = Namespace("http://www.w3.org/ns/prov#")


def official_match(entity, domains):
    urls = [claim.get("mainsnak", {}).get("datavalue", {}).get("value", "")
            for claim in entity.get("claims", {}).get("P856", [])]
    return next((url for url in urls if isinstance(url, str) and urlparse(url).hostname
                 and urlparse(url).hostname.removeprefix("www.") in domains), None)


def collect_links():
    lookups = []
    for key, (qid, domains) in CANDIDATES.items():
        url = "https://www.wikidata.org/wiki/Special:EntityData/" + qid + ".json"
        record = {"local_id": uri("organization", key), "qid": qid, "source_url": url, "retrieved_at": now()}
        try:
            content = fetch(url)
            payload = json.loads(content)
            entity = payload["entities"].get(qid, {})
            site = official_match(entity, domains)
            record.update({"wikidata": payload, "sha256": digest(content), "verified_site": site or ""})
            if not site:
                record["warning"] = "Candidate official website not confirmed; no identity link emitted"
            else:
                query = "SELECT ?entity WHERE { ?entity <http://www.w3.org/2002/07/owl#sameAs> <http://www.wikidata.org/entity/" + qid + "> } LIMIT 10"
                endpoint = "https://dbpedia.org/sparql?" + urlencode({"query": query, "format": "application/sparql-results+json"})
                try:
                    response = fetch(endpoint, {"Accept": "application/sparql-results+json"})
                    record["dbpedia"] = json.loads(response)
                    record["dbpedia_url"] = endpoint
                    record["dbpedia_sha256"] = digest(response)
                except (RuntimeError, ValueError) as exc:
                    record["dbpedia_warning"] = str(exc)
        except (RuntimeError, ValueError, KeyError) as exc:
            record["warning"] = str(exc)
        lookups.append(record)
    write_json(BRONZE / "external_lookups.json", lookups)
    return lookups


def export_links(lookups):
    graph, evidence = Graph(), []
    known = {row["id"] for row in read_tables()["organizations"]}
    for lookup in lookups:
        if not lookup.get("verified_site") or lookup["local_id"] not in known:
            continue
        targets = [("http://www.wikidata.org/entity/" + lookup["qid"], lookup["source_url"],
                    "Wikidata P856 matches reviewed organization domain: " + lookup["verified_site"])]
        for row in (lookup.get("dbpedia") or {}).get("results", {}).get("bindings", []):
            target = row.get("entity", {}).get("value", "")
            if target.startswith("http://dbpedia.org/resource/"):
                targets.append((target, lookup["dbpedia_url"], "DBpedia owl:sameAs to independently verified Wikidata QID"))
        for target, source, reason in targets:
            subject = URIRef(lookup["local_id"])
            graph.add((subject, OWL.sameAs, URIRef(target)))
            ident = URIRef(uri("external-link", digest([str(subject), target, source])))
            graph.add((ident, RDF.type, EX.ExternalLink))
            graph.add((ident, EX.linkSubject, subject))
            graph.add((ident, EX.linkTarget, URIRef(target)))
            graph.add((ident, PROV.wasDerivedFrom, URIRef(source)))
            graph.add((ident, EX.description, Literal(reason)))
            evidence.append({"id": str(ident), "subject": str(subject), "target": target,
                             "source_url": source, "reason": reason, "retrieved_at": lookup["retrieved_at"]})
    graph.serialize(RES / "model-links.nt", format="nt", encoding="utf-8")
    write_tables({"external_links": evidence})
    if (RES / "model-coverage.json").exists():
        coverage = read_json(RES / "model-coverage.json")
        coverage["tables"]["external_links"] = len(evidence)
        write_json(RES / "model-coverage.json", coverage)
    warning_fields = {"local_id", "qid", "source_url", "retrieved_at", "warning", "dbpedia_warning"}
    write_json(RES / "model-link-report.json", {"links": len(evidence), "warnings": [
        {key: value for key, value in row.items() if key in warning_fields}
        for row in lookups if row.get("warning") or row.get("dbpedia_warning")]})
    print(f"Verified external links: {len(evidence)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    export_links(read_json(BRONZE / "external_lookups.json") if args.offline else collect_links())


if __name__ == "__main__":
    main()
