"""Export verified company/platform identities from Wikidata, DBpedia and OpenAlex."""
import argparse

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, OWL, XSD

from .common import BASE, BRONZE, RES, digest, read_json, read_tables, uri, write_json, write_tables

from .wikidata_links import collect_links, verified_links

EX = Namespace(BASE)
PROV = Namespace("http://www.w3.org/ns/prov#")


def export_links(lookups, openalex_lookups=None):
    graph, evidence = Graph(), []
    tables = read_tables()
    identity_links, identity_decisions = verified_links(tables, lookups)
    for row in identity_links:
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
        "wikidata_decisions": identity_decisions,
        "linked_local_entities": len({r["subject"] for r in evidence}),
        "wikidata_links": sum(r["target"].startswith("http://www.wikidata.org/") for r in evidence),
        "dbpedia_links": sum(r["target"].startswith("http://dbpedia.org/") for r in evidence),
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
