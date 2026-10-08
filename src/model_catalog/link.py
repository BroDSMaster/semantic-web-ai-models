"""Verify organization identities by Wikidata official websites and DBpedia sameAs."""
import argparse
import json
from urllib.parse import urlencode, urlparse

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, OWL, XSD

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


def export_links(lookups, openalex_lookups=None):
    graph, evidence = Graph(), []
    tables = read_tables()
    known = {row["id"] for row in tables["organizations"]}
    for lookup in lookups:
        candidate = next(((qid, domains) for key, (qid, domains) in CANDIDATES.items()
                          if uri("organization", key) == lookup.get("local_id")), None)
        if not candidate or lookup.get("qid") != candidate[0] or lookup["local_id"] not in known:
            continue
        entity = (lookup.get("wikidata") or {}).get("entities", {}).get(candidate[0], {})
        site = official_match(entity, candidate[1])
        if entity.get("id") != candidate[0] or not site:
            continue
        targets = [("http://www.wikidata.org/entity/" + lookup["qid"], lookup["source_url"],
                    "Wikidata P856 matches reviewed organization domain: " + site)]
        for row in (lookup.get("dbpedia") or {}).get("results", {}).get("bindings", []):
            target = row.get("entity", {}).get("value", "")
            if row.get("entity", {}).get("type") == "uri" and target.startswith("http://dbpedia.org/resource/"):
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
    from .organization_links import verified_openalex_links
    openalex_links, openalex_decisions = verified_openalex_links(tables, openalex_lookups or [])
    for row in openalex_links:
        subject, target = URIRef(row["subject"]), URIRef(row["target"])
        graph.add((subject, OWL.sameAs, target))
        ident = URIRef(uri("external-link", digest([row["subject"], row["target"], row["source_url"]])))
        graph.add((ident, RDF.type, EX.ExternalLink))
        graph.add((ident, EX.linkSubject, subject))
        graph.add((ident, EX.linkTarget, target))
        graph.add((ident, PROV.wasDerivedFrom, URIRef(row["source_url"])))
        for prop, value in [(EX.description, row["reason"]), (EX.sha256, row["sha256"]),
                            (EX.snapshotFile, row["snapshot_file"]), (EX.observedAt, row["retrieved_at"])]:
            graph.add((ident, prop, Literal(value, datatype=XSD.dateTime if prop == EX.observedAt else None)))
        evidence.append({"id": str(ident), **row})
    graph.serialize(RES / "linked_output.nt", format="nt", encoding="utf-8")
    write_tables({"external_links": evidence})
    if (RES / "coverage.json").exists():
        coverage = read_json(RES / "coverage.json")
        coverage["tables"]["external_links"] = len(evidence)
        write_json(RES / "coverage.json", coverage)
    warning_fields = {"local_id", "qid", "source_url", "retrieved_at", "warning", "dbpedia_warning"}
    write_json(RES / "linking-report.json", {"links": len(evidence),
        "openalex_organization_links": len(openalex_links),
        "openalex_decisions": openalex_decisions, "warnings": [
        {key: value for key, value in row.items() if key in warning_fields}
        for row in lookups if row.get("warning") or row.get("dbpedia_warning")]})
    print(f"Verified external links: {len(evidence)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    from .organization_links import collect_openalex_links
    openalex_cache = BRONZE / "openalex_lookups.json"
    openalex = (read_json(openalex_cache) if openalex_cache.exists() else []) if args.offline else collect_openalex_links()
    export_links(read_json(BRONZE / "external_lookups.json") if args.offline else collect_links(), openalex)


if __name__ == "__main__":
    main()
